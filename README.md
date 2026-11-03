# 全球美妆研发情报台

面向个人研发经理的标题情报 MVP。后端是 FastAPI 分层单体，前端是 Vue 3 特性目录；唯一根 Dockerfile 在构建阶段编译前端并复制到后端静态目录，Docker Compose 编排 API、worker、迁移任务和 Caddy HTTPS 网关。

> 每天早上，看见全球化妆品的前沿。

## 目录结构

```text
.
├── Dockerfile                     # 唯一多阶段构建：frontend-builder/python-builder/runtime/gateway
├── docker-compose.yml             # 唯一 Compose 编排入口
├── pyproject.toml                 # 后端依赖与测试配置
├── app/                           # 后端应用
│   ├── core/                      # 配置与跨层异常
│   ├── domain/                    # 纯业务值对象、分类和固定来源身份
│   ├── application/               # 用例、事务、查询和任务编排
│   ├── infrastructure/            # SQLite、配置、feed 与安全 HTTP 适配器
│   ├── presentation/http/         # FastAPI 组合、路由、依赖与错误映射
│   ├── runtime/                   # 独立 worker 进程实现
│   ├── main.py                    # 稳定 ASGI 入口
│   ├── worker.py                  # 稳定 worker 命令入口
│   └── backup.py                  # 稳定备份恢复命令入口
├── alembic/                       # 数据库迁移
├── config/                        # 固定来源和分类配置
├── tests/                         # 后端 unit/integration 测试
├── frontend/
│   ├── src/app/                  # Vue 组合根、路由和运行时装配
│   ├── src/features/             # auth/headlines 等业务特性
│   ├── src/shared/               # HTTP 契约和可复用基础设施
│   └── tests/unit/               # 镜像源码职责的单元测试
├── deploy/                       # Caddy、环境示例、Compose 包装器和运行手册
├── docs/                         # 架构说明及历史调研
└── fp-docs/                      # FeaturePilot canonical 需求、设计、任务和执行记录
```

依赖方向和模块接口见 [架构说明](<docs/architecture.md>)。

## 本地验证

```bash
# 在仓库根目录，使用本项目的 Python 虚拟环境
python -m pytest -q
python -m compileall -q app tests alembic
python -m pip check

cd frontend
pnpm run test:unit
pnpm run typecheck
pnpm run build
pnpm run check:artifact
```

## 生产部署

使用唯一 Compose 入口：

```bash
set -Eeuo pipefail
cp deploy/env.example deploy/.env
# 设置真实 DOMAIN/ACME_EMAIL，并把 IMAGE_TAG 设为待发布干净提交的完整 Git SHA。
IMAGE_TAG=$(sed -n 's/^IMAGE_TAG=//p' deploy/.env)
test "$IMAGE_TAG" = "$(git rev-parse HEAD)"
git diff --quiet && git diff --cached --quiet
test -z "$(git ls-files --others --exclude-standard)"
compose() { sh deploy/compose.sh deploy/.env docker-compose.yml "$@"; }
compose config --quiet
compose build --pull
compose run --rm --no-deps web-validate
# 只有以上门禁全部通过后才执行：compose up -d
```

首次部署、不可变标签升级/回滚、备份和恢复必须按 [部署手册](<deploy/README.md>) 执行，不使用跳过 preflight 的快捷命令。

## 稳定运行入口

内部模块可继续演进，运维只依赖以下三个入口：

- `uvicorn app.main:create_app --factory ...`
- `python -m app.worker`
- `python -m app.backup create|restore ...`
