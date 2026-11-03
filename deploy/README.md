# Docker Compose 部署、升级与恢复手册

生产只跟踪一个根 `Dockerfile` 和一个根 `docker-compose.yml`。Dockerfile 的 `frontend-builder` 先编译前端，`runtime` 再把 dist 复制到 `/srv/app/static`；同一 Dockerfile 的 `gateway` target 固化 Caddyfile。每次发布的 `IMAGE_TAG` 必须精确等于待发布干净提交的完整 Git SHA。API 不发布宿主端口，公网流量只进入 Caddy。

> 当前 Windows 测试不等于目标 Linux 已验收。腾讯云 SSH 主机指纹未带外确认前，不执行远端命令。

## 服务与持久数据

| 服务 | 类型 | 说明 |
| --- | --- | --- |
| `secrets-init` | 一次性 | 受限 root 把 file secrets 复制到命名卷，固定 UID/GID 10001、0400 |
| `migrate` | 一次性 | 每次 `up` 前幂等执行 Alembic `upgrade head` |
| `api` | 常驻 | 单 Uvicorn worker，仅在 Compose 网络暴露 8000 |
| `worker` | 常驻 | 单实例串行来源任务、日程与在线备份 |
| `web-validate` | 按需 | 无网络、无固定 IP，验证新 web 镜像内的 Caddyfile |
| `web` | 常驻 | Caddy HTTPS/安全头网关；所有站点请求原样反向代理给 FastAPI |

命名卷 `runtime-secrets` 只读提供容器内秘密，`app-data` 保存 SQLite，`app-backups` 保存最近备份；`caddy-data` 和 `caddy-config` 保存证书与 Caddy 状态。SQLite 卷必须位于本机磁盘，不能放在 NFS/SMB。

Compose 对 file secret 的 uid/gid/mode 不做重映射。API/worker 不直接挂 file secret；`secrets-init` 在无网络环境中复制到 `runtime-secrets` 后，API/worker 才以非 root UID 10001 读取。所有运维命令经 `deploy/compose.sh` 清除宿主同名导出变量，使显式 env 文件成为发布配置的唯一插值来源。

## 首次部署

### 1. 准备域名、发布标签和秘密

```bash
set -Eeuo pipefail
cp deploy/env.example deploy/.env
# 编辑 DOMAIN、ACME_EMAIL，并把 IMAGE_TAG 设为 `git rev-parse HEAD` 的完整输出。

python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python deploy/init_secrets.py
```

Windows 的最后两行改用 `.venv/Scripts/python.exe -m pip install -e .` 和 `.venv/Scripts/python.exe deploy/init_secrets.py`。生成器以 `0700` 目录和 `0600` 临时文件原子落盘；`deploy/.env` 与 `deploy/secrets/` 已被 Git 忽略，秘密不得写入镜像层、日志或版本库。

### 2. 校验配置并构建

```bash
set -Eeuo pipefail
IMAGE_TAG=$(sed -n 's/^IMAGE_TAG=//p' deploy/.env)
RELEASE_REV=$(git rev-parse HEAD)
test "$IMAGE_TAG" = "$RELEASE_REV"
git diff --quiet
git diff --cached --quiet
test -z "$(git ls-files --others --exclude-standard)"
git ls-files --error-unmatch \
  Dockerfile docker-compose.yml deploy/Caddyfile >/dev/null
compose() { sh deploy/compose.sh deploy/.env docker-compose.yml "$@"; }
compose config --quiet
compose build --pull
compose run --rm --no-deps web-validate
```

构建会执行：

- 唯一 Dockerfile 的 Node stage 执行 frozen install、typecheck、build 和 artifact check；
- Python stage 按完整 `constraints.lock` 构建 wheel，并把 dist 复制到后端静态目录；
- `runtime` target 同时服务 API 和 SPA，`gateway` target 固化 Caddyfile；回滚两个版本镜像即可同时回滚应用和网关；
- 最终 runtime 不包含 Node/pnpm/node_modules 或测试目录。

### 3. 启动与检查

```bash
set -Eeuo pipefail
compose() { sh deploy/compose.sh deploy/.env docker-compose.yml "$@"; }
compose up -d
compose ps
compose logs --tail=200 secrets-init migrate api worker web

IMAGE_TAG=$(sed -n 's/^IMAGE_TAG=//p' deploy/.env)
printf 'IMAGE_TAG=%s\nGIT_REV=%s\n' "$IMAGE_TAG" "$(git rev-parse HEAD)" > deploy/release-state.env
chmod 600 deploy/release-state.env
```

`secrets-init` 和 `migrate` 应以 0 退出，`api` 和 `web` 应变为 healthy。随后通过 `https://${DOMAIN}` 正常登录并检查标题、收藏、来源状态和更新任务。不要把容器启动成功当作真实来源或 E2E 已通过。

## 升级

每次发布使用干净提交的完整 Git SHA，因此标签天然不可复用。升级脚本块使用 `set -Eeuo pipefail`；任一构建、验证、备份或迁移失败都会停止，不会继续启动新服务。

```bash
set -Eeuo pipefail
rollback_compose() { sh deploy/compose.sh deploy/.env.rollback deploy/docker-compose.rollback.yml "$@"; }
next_compose() { sh deploy/compose.sh deploy/.env.next docker-compose.yml "$@"; }
cleanup_next() { rm -f deploy/.env.next; }
trap cleanup_next EXIT

. deploy/release-state.env
OLD_TAG=$IMAGE_TAG
OLD_REV=$GIT_REV
NEW_REV=$(git rev-parse HEAD)
NEW_TAG=$NEW_REV
git cat-file -e "${OLD_REV}^{commit}"
git diff --quiet
git diff --cached --quiet
test -z "$(git ls-files --others --exclude-standard)"
test -n "$OLD_TAG" && test "$OLD_TAG" != "$NEW_TAG"

# 旧环境始终保持不变；新 tag 只写到临时 next 环境。
cp deploy/.env deploy/.env.rollback
cp deploy/.env deploy/.env.next
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${NEW_TAG}/" deploy/.env.next
git show "$OLD_REV:docker-compose.yml" > deploy/docker-compose.rollback.yml
printf 'PHASE=prepared\nOLD_TAG=%s\nOLD_REV=%s\n' "$OLD_TAG" "$OLD_REV" > deploy/rollback-state.env
chmod 600 deploy/.env.rollback deploy/.env.next deploy/docker-compose.rollback.yml deploy/rollback-state.env

# 新镜像预构建失败时，旧 env 和旧服务完全不变。
next_compose config --quiet
next_compose build --pull
next_compose run --rm --no-deps web-validate

# 只有新镜像和Caddy均通过后才停写；失败时prepared阶段可直接重启旧服务。
rollback_compose stop api worker
BACKUP_PATH=$(rollback_compose run --rm --no-deps worker \
  python -m app.backup create \
  --database /data/intelligence.sqlite3 \
  --directory "/backups/releases/${OLD_REV}" | sed -n 's/^backup=//p')
test -n "$BACKUP_PATH"
BACKUP_SHA=$(rollback_compose run --rm --no-deps worker \
  python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' \
  "$BACKUP_PATH")
test -n "$BACKUP_SHA"
printf 'PHASE=backed_up\nOLD_TAG=%s\nOLD_REV=%s\nBACKUP_PATH=%s\nBACKUP_SHA=%s\n' \
  "$OLD_TAG" "$OLD_REV" "$BACKUP_PATH" "$BACKUP_SHA" > deploy/rollback-state.env

next_compose run --rm --no-deps migrate
next_compose up -d api worker web
next_compose logs --tail=200 secrets-init migrate api worker web

mv deploy/.env.next deploy/.env
trap - EXIT
printf 'IMAGE_TAG=%s\nGIT_REV=%s\n' "$NEW_TAG" "$NEW_REV" > deploy/release-state.env
chmod 600 deploy/release-state.env
```

### 升级失败后的精确回滚

```bash
set -Eeuo pipefail
. deploy/rollback-state.env
cp deploy/.env.rollback deploy/.env
rm -f deploy/.env.next
rollback_compose() { sh deploy/compose.sh deploy/.env deploy/docker-compose.rollback.yml "$@"; }
rollback_compose stop api worker

if [ "$PHASE" = backed_up ]; then
  CURRENT_SHA=$(rollback_compose run --rm --no-deps worker \
    python -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' \
    "$BACKUP_PATH")
  test "$CURRENT_SHA" = "$BACKUP_SHA"
  rollback_compose run --rm --no-deps worker \
    python -m app.backup restore \
    --backup "$BACKUP_PATH" \
    --database /data/intelligence.sqlite3 \
    --lease /data/application.lock \
    --confirm '已确认损失备份后的写入'
elif [ "$PHASE" != prepared ]; then
  echo "未知回滚阶段：$PHASE" >&2
  exit 1
fi

# prepared表示尚未迁移，只重启旧服务；backed_up则已核验hash并恢复旧schema备份。
rollback_compose up -d --no-deps --no-build api worker web
rollback_compose logs --tail=200 api worker web
printf 'IMAGE_TAG=%s\nGIT_REV=%s\n' "$OLD_TAG" "$OLD_REV" > deploy/release-state.env
chmod 600 deploy/release-state.env
```

升级前快照保存在 `/backups/releases/<OLD_REV>/`，worker 的日常轮换不会递归覆盖；回滚前必须匹配记录的 SHA-256。`prepared` 阶段从未迁移，只恢复旧 env/服务；`backed_up` 阶段按记录备份恢复旧 schema。回滚后通过 HTTPS 核验业务数据。不要直接复制运行中的 SQLite 文件，也不要临时依赖未经验证的 Alembic downgrade。

## 主动备份与离线恢复

恢复会覆盖当前数据库。**所选备份创建之后产生的标题更新、收藏和任务记录都会丢失。** 固定确认文本为：

```text
已确认损失备份后的写入
```

```bash
set -Eeuo pipefail
compose() { sh deploy/compose.sh deploy/.env docker-compose.yml "$@"; }
compose stop api worker
RESTORE_OUTPUT=$(compose run --rm --no-deps worker \
  python -m app.backup restore \
  --backup /backups/backup-YYYY-MM-DD.sqlite3 \
  --database /data/intelligence.sqlite3 \
  --lease /data/application.lock \
  --confirm '已确认损失备份后的写入')
printf '%s\n' "$RESTORE_OUTPUT"
compose run --rm --no-deps migrate
compose up -d api worker web
compose logs --tail=200 api worker web
```

恢复程序先验证输入备份，并取得独占 application lease：

- 当前运行库有效时，输出 `pre_restore=<path>`；该文件是经过 schema/integrity 校验的一致性快照，可用于同一恢复流程回退。
- 当前运行库损坏时，`pre_restore` 只是原始主文件和 sidecar 的取证副本，**不能**作为有效 `--backup`；应保留并使用另一份已验证备份。
- 当前运行库缺失时，输出 `pre_restore=none`，没有可回退的旧库。

恢复后必须人工核验至少一条已知收藏、来源许可状态和任务详情。只有第一种“原运行库有效”的情况，检查失败时才能把已验证的 `pre_restore` 作为 `--backup` 再运行恢复；另外两种情况不得照搬该回退动作。

## 秘密轮换

更新宿主 `deploy/secrets/` 后，显式重建运行时秘密卷内容并重启读取者：

```bash
set -Eeuo pipefail
compose() { sh deploy/compose.sh deploy/.env docker-compose.yml "$@"; }
compose run --rm --no-deps secrets-init
compose up -d --force-recreate api worker
```

## 安全与运维约束

- `api` 和 `worker` 以 UID/GID 10001、只读根文件系统、无 Linux capabilities 运行。
- Caddy 固定使用 Compose 地址 `172.30.0.2`，后端仅在 socket peer 匹配该地址时信任 `X-BI-Client-IP`。若修改 `APP_SUBNET`，必须同时修改 `CADDY_IPV4` 并重新验证。
- Caddy 覆盖客户端代理头，提供 CSP、HSTS、nosniff、Referrer-Policy 和 Permissions-Policy。
- 只有 Caddy 发布 80/443；不得把后端 8000 暴露到公网。
- 不运行多个 worker。文件锁是故障兜底，不是水平扩缩策略。
- `docker compose down -v` 会删除业务数据、运行时秘密和证书卷，生产环境禁止执行。

## 仍需在目标 Linux 验证

上线前必须验证 Docker Compose 展开、冷镜像构建、Caddy validate、Linux `flock`、UID/卷权限、secrets-init capabilities、SIGTERM 停机、Caddy ACME、真实来源 DNS/TLS、07:30 常驻调度、损坏/缺失数据库恢复演练和真实 UI→API→SQLite E2E。Docker Desktop 只能近似部分行为，不能替代目标云主机证据。
