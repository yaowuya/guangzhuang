# 美妆情报台部署与恢复运行手册

> 本文件记录未来 Linux + Docker Compose 目标环境的操作契约；当前 Windows 开发测试不等于这些命令已在目标服务器执行。

## 离线恢复前提

恢复会覆盖当前 SQLite 数据库。**所选备份创建之后产生的标题更新、收藏和任务记录都会丢失。** 操作员必须先确认维护窗口，并使用固定确认文本：

```text
已确认损失备份后的写入
```

恢复程序不会代替人工停止服务。先停止所有会写数据库的进程：

```bash
docker compose -f deploy/compose.yaml stop api worker
```

确认 API 与 worker 已停止，且没有其它进程打开数据库。不要停止 Caddy 来代替停写，也不要在运行容器内直接复制 SQLite 文件。

## 备份与恢复

1. 记录当前数据库、目标备份及预计损失窗口。
2. 在独立的一次性后端容器中执行恢复（实际卷路径以 Compose 为准）：

```bash
docker compose -f deploy/compose.yaml run --rm --no-deps worker \
  python -m app.backup restore \
  --backup /backups/backup-YYYY-MM-DD.sqlite3 \
  --database /data/intelligence.sqlite3 \
  --lease /data/application.lock \
  --confirm '已确认损失备份后的写入'
```

恢复命令会：

- 校验备份完整性、七张业务表和 Alembic 版本；
- 尝试取得独占 application lease，仍有 API/worker 时拒绝；
- 先在 `/data/pre-restore/` 保存当前库的一致性安全快照；
- 校验 staged 数据库后原子替换运行库；
- 输出 `pre_restore=...` 路径供人工回滚。

3. 对恢复后的数据库应用兼容迁移：

```bash
docker compose -f deploy/compose.yaml run --rm --no-deps worker \
  alembic -c /app/alembic.ini upgrade head
```

4. 启动服务并检查，而不是直接宣称恢复成功：

```bash
docker compose -f deploy/compose.yaml up -d api worker
docker compose -f deploy/compose.yaml logs --tail=200 api worker
```

通过同源 HTTPS 登录后，人工核验标题、收藏、来源许可状态、当前/最近任务及更新时间。至少读取一条恢复前已知收藏和一个任务详情。

## 恢复后的回滚

若恢复后检查失败：

1. 再次停止 `api worker`；
2. 记录当前失败状态和损失窗口；
3. 使用上一步输出的 `pre_restore` 文件作为 `--backup` 再运行相同恢复命令；
4. 重新执行 Alembic 升级和业务读取检查。

不得删除 pre-restore 文件后再开始验证，不得把同机七份备份描述为异地灾难恢复。正式发布仍要求目标 Linux 的 Compose、HTTPS、文件锁、真实来源、07:30 日程和恢复演练证据全部通过。
