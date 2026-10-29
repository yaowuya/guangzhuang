"""后端分层依赖方向和稳定启动入口的架构守卫。"""

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def module_name(path: Path) -> str:
    """把应用根内的 Python 路径转为绝对模块名，用于静态导入解析。"""
    relative = path.relative_to(APP_ROOT).with_suffix("")
    return ".".join(("app", *relative.parts))


def imported_modules(path: Path) -> set[str]:
    """解析绝对、相对和 `from app import x`，不执行被检查模块。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    current_package = module_name(path).rsplit(".", 1)[0]
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level:
            package_parts = current_package.split(".")
            keep = len(package_parts) - node.level + 1
            base = ".".join((*package_parts[:keep], *((node.module or "").split("."))))
        else:
            base = node.module or ""
        if base:
            modules.add(base)
        for alias in node.names:
            if alias.name != "*" and base:
                modules.add(f"{base}.{alias.name}")
    return modules


def assert_forbidden(layer: str, forbidden: tuple[str, ...]) -> None:
    """检查指定层的所有模块，发现禁止导入时报告源码位置与依赖方向。"""
    for path in (APP_ROOT / layer).rglob("*.py"):
        for module in imported_modules(path):
            assert not module.startswith(forbidden), f"{path.relative_to(APP_ROOT)} -> {module}"


def test_dependency_direction_is_inward() -> None:
    """纯层和外部适配层不能反向依赖用例、HTTP 或进程运行时。"""
    assert_forbidden("core", (
        "app.domain", "app.application", "app.infrastructure", "app.presentation", "app.runtime",
        "fastapi", "starlette", "sqlalchemy", "pydantic",
    ))
    assert_forbidden("domain", (
        "app.application", "app.infrastructure", "app.presentation", "app.runtime",
        "fastapi", "starlette", "sqlalchemy", "pydantic", "bs4", "defusedxml",
    ))
    assert_forbidden("infrastructure", ("app.application", "app.presentation", "app.runtime"))
    assert_forbidden("application", ("app.presentation", "app.runtime", "fastapi", "starlette"))


def test_stable_entrypoints_are_thin_adapters() -> None:
    """根入口只允许导入、导出和 `__main__` 调用，不能重新承载实现。"""
    for name in ("main.py", "worker.py", "backup.py"):
        path = APP_ROOT / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        assert not any(isinstance(node, forbidden) for node in tree.body), name

    from app.backup import main as backup_main
    from app.main import create_app
    from app.worker import worker_loop

    assert callable(create_app)
    assert callable(worker_loop)
    assert callable(backup_main)
