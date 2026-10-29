"""Docker Compose、镜像入口和网关安全契约的离线结构测试。"""

from importlib import metadata, util
import os
from pathlib import Path
import stat
import tomllib

import pytest

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[4]
DEPLOY = ROOT / "deploy"
COMPOSE = ROOT / "docker-compose.yml"


def service_block(compose: str, name: str) -> str:
    """读取固定两空格 services 子块，避免用字符串命中其它服务。"""
    marker = f"  {name}:\n"
    start = compose.index(marker) + len(marker)
    tail = compose[start:]
    positions = [position for position in (
        tail.find(f"\n  {candidate}:\n")
        for candidate in ("secrets-init", "migrate", "api", "worker", "web-validate", "web") if candidate != name
    ) if position >= 0]
    end = min(positions) if positions else tail.find("\nnetworks:")
    return tail[:end if end >= 0 else None]


def test_compose_builds_one_dockerfile_and_exposes_only_gateway() -> None:
    """锁定单根构建入口、内部应用端口和秘密初始化/迁移依赖。"""
    compose = COMPOSE.read_text(encoding="utf-8")
    assert not compose.startswith("version:")
    assert not (DEPLOY / "compose.yaml").exists()
    assert [path.relative_to(ROOT).as_posix() for path in ROOT.glob("**/docker-compose.y*ml")] == ["docker-compose.yml"]
    for name in ("secrets-init", "migrate", "api", "worker", "web-validate", "web"):
        assert f"  {name}:\n" in compose
    assert "x-app-image: &app-image" in compose
    assert "x-gateway-image: &gateway-image" in compose
    assert compose.count("dockerfile: Dockerfile") == 2
    assert "target: runtime" in compose and "target: gateway" in compose
    assert "STATIC_DIR: /srv/app/static" in compose
    assert service_block(compose, "api").find("ports:") == -1
    assert service_block(compose, "worker").find("ports:") == -1
    assert "ports:" in service_block(compose, "web")
    assert "PASSWORD_HASH_FILE: /run/secrets/password_hash" in compose
    assert "CSRF_KEY_FILE: /run/secrets/csrf_key" in compose
    assert "runtime-secrets:/run/secrets:ro" in compose
    init = service_block(compose, "secrets-init")
    assert 'user: "0:0"' in init
    assert "network_mode: none" in init
    assert "install -m 0400 -o 10001 -g 10001" in init
    unsupported_secret_fields = {
        line.strip().split(":", 1)[0]
        for line in compose.splitlines()
        if line.strip().startswith(("uid:", "gid:", "mode:"))
    }
    assert not unsupported_secret_fields
    validator = service_block(compose, "web-validate")
    assert "network_mode: none" in validator
    assert 'entrypoint: ["caddy"]' in validator
    assert 'command: ["validate"' in validator
    assert "condition: service_completed_successfully" in compose


def test_constraints_lock_covers_linux_runtime_dependency_closure() -> None:
    """Linux 运行时依赖闭包与构建后端都必须在约束中精确固定版本。"""
    constraints = {}
    for line in (ROOT / "backend/constraints.lock").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, version = line.split("==", 1)
        constraints[canonicalize_name(name)] = version

    environment = default_environment()
    environment.update({"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix"})
    pending = [Requirement(value) for value in metadata.requires("beauty-intelligence-api") or ()]
    seen: set[str] = set()
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate({**environment, "extra": ""}):
            continue
        name = canonicalize_name(requirement.name)
        if name in seen:
            continue
        seen.add(name)
        distribution = metadata.distribution(requirement.name)
        assert constraints.get(name) == distribution.version, name
        pending.extend(Requirement(value) for value in distribution.requires or ())

    build = tomllib.loads((ROOT / "backend/pyproject.toml").read_text(encoding="utf-8"))["build-system"]["requires"]
    assert build == [f"setuptools=={constraints['setuptools']}"]


def test_single_dockerfile_builds_frontend_into_non_root_backend() -> None:
    """前端产物进入非 root runtime，根构建白名单不重新纳入本地数据。"""
    dockerfiles = [path.relative_to(ROOT).as_posix() for path in ROOT.glob("**/Dockerfile")]
    assert dockerfiles == ["Dockerfile"]
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    for stage in ("frontend-builder", "backend-builder", "runtime", "gateway"):
        assert f" AS {stage}" in dockerfile
    assert dockerfile.rfind(" AS runtime") > dockerfile.rfind(" AS gateway")
    assert "USER app:app" in dockerfile
    assert "app.main:create_app" in dockerfile
    assert "COPY backend/app ./app" in dockerfile
    assert "COPY --from=frontend-builder --chown=app:app /build/frontend/dist ./static" in dockerfile
    assert "COPY deploy/Caddyfile /etc/caddy/Caddyfile" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "pnpm run check:artifact" in dockerfile

    root_ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert root_ignore.startswith("*\n") and "backend/*" in root_ignore and "frontend/*" in root_ignore
    for included in ("!backend/app/**", "!frontend/src/**", "!deploy/Caddyfile"):
        assert included in root_ignore
    for excluded in ("**/__pycache__/", "**/node_modules/", "**/dist/", "**/.env"):
        assert excluded in root_ignore
    assert not (ROOT / "backend/.dockerignore").exists()
    assert not (ROOT / "frontend/.dockerignore").exists()


def test_caddy_only_proxies_and_overwrites_client_headers() -> None:
    """网关只反代并清洗身份头，静态查找与页面回退只能由 FastAPI 承担。"""
    caddy = (DEPLOY / "Caddyfile").read_text(encoding="utf-8")
    assert "@api path /api /api/*" in caddy
    assert "reverse_proxy api:8000" in caddy
    assert "uri strip_prefix" not in caddy
    assert "header_up -X-Forwarded-For" in caddy
    assert "header_up X-BI-Client-IP {remote_host}" in caddy
    assert "Content-Security-Policy" in caddy
    for forbidden in ("root *", "file_server", "try_files"):
        assert forbidden not in caddy
    spa = caddy.rsplit("  handle {", 1)[1]
    assert 'header Cache-Control "no-cache"' in spa and "import proxy_app" in spa
    immutable = caddy.split("  handle @immutable {", 1)[1].split("  handle {", 1)[0]
    assert "immutable" in immutable and "import proxy_app" in immutable


def test_example_environment_contains_paths_not_secret_values() -> None:
    """示例仅声明秘密路径，运行时发布状态文件必须被 Git 忽略。"""
    example = (DEPLOY / "env.example").read_text(encoding="utf-8")
    ignored = (DEPLOY / ".gitignore").read_text(encoding="utf-8")
    assert "IMAGE_TAG=replace-with-full-git-sha" in example
    assert "PASSWORD_HASH_FILE=./deploy/secrets/password.hash" in example
    assert "CSRF_KEY_FILE=./deploy/secrets/csrf.key" in example
    assert "$argon2" not in example
    assert "csrf.key=" not in example.lower()
    for name in ("release-state.env", "rollback-state.env", "docker-compose.rollback.yml"):
        assert name in ignored


def test_compose_wrapper_prevents_host_environment_precedence() -> None:
    """包装器清除宿主变量覆盖，并以固定项目根解析所有 Compose 相对路径。"""
    wrapper = (DEPLOY / "compose.sh").read_text(encoding="utf-8")
    for name in ("IMAGE_TAG", "DOMAIN", "PASSWORD_HASH_FILE", "COMPOSE_FILE", "COMPOSE_ENV_FILES"):
        assert name in wrapper
    assert 'unset "$name"' in wrapper
    assert "COMPOSE_DISABLE_ENV_FILE=1 exec docker compose" in wrapper
    assert 'project_dir=$(CDPATH= cd -- "$script_dir/.." && pwd)' in wrapper
    assert '--project-directory "$project_dir"' in wrapper


def test_runbook_is_fail_closed_and_records_reproducible_rollback() -> None:
    """运维步骤遇错停止，并保留旧版本配置、独立备份摘要及回滚阶段。"""
    runbook = (DEPLOY / "README.md").read_text(encoding="utf-8")
    assert runbook.count("set -Eeuo pipefail") >= 5
    assert "set -a; . deploy/.env" not in runbook
    assert runbook.count("sh deploy/compose.sh") >= 5
    assert "backend/Dockerfile" not in runbook and "frontend/Dockerfile" not in runbook
    assert "Dockerfile docker-compose.yml deploy/Caddyfile" in runbook
    assert 'test "$IMAGE_TAG" = "$RELEASE_REV"' in runbook
    assert "git diff --quiet" in runbook and "git diff --cached --quiet" in runbook
    assert "git show \"$OLD_REV:docker-compose.yml\" > deploy/docker-compose.rollback.yml" in runbook
    assert "BACKUP_PATH=$(rollback_compose run" in runbook
    assert '--directory "/backups/releases/${OLD_REV}"' in runbook
    assert "BACKUP_SHA=$(rollback_compose run" in runbook
    assert 'test "$CURRENT_SHA" = "$BACKUP_SHA"' in runbook
    assert "PHASE=prepared" in runbook and "PHASE=backed_up" in runbook
    assert "deploy/.env.next" in runbook and "trap cleanup_next EXIT" in runbook
    assert "--no-deps --no-build api worker web" in runbook
    assert "run --rm --no-deps web-validate" in runbook


def test_secret_generator_is_atomic_private_and_non_overwriting(tmp_path) -> None:
    """秘密以私有临时文件原子写入，默认拒绝覆盖且不遗留临时内容。"""
    path = DEPLOY / "init_secrets.py"
    source = path.read_text(encoding="utf-8")
    assert "directory.mkdir(mode=0o700" in source and "directory.chmod(0o700)" in source
    assert "os.O_EXCL" in source and "os.replace" in source
    spec = util.spec_from_file_location("deploy_init_secrets", path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)

    target = tmp_path / "secret"
    module.write_private(target, "first", force=False)
    assert target.read_text(encoding="utf-8") == "first\n"
    if os.name != "nt":
        assert stat.S_IMODE(target.stat().st_mode) == 0o600
    with pytest.raises(SystemExit):
        module.write_private(target, "second", force=False)
    assert target.read_text(encoding="utf-8") == "first\n"
    assert not list(tmp_path.glob(".*.tmp"))
