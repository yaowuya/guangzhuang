"""把已构建前端作为同域静态站点提供；/api 始终保留 JSON 语义。"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def install_frontend(app: FastAPI, directory: Path | None) -> None:
    """挂载静态文件并只把非 API 的 GET/HEAD 404 转成 SPA 入口。"""
    if directory is None:
        return
    root = directory.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise ValueError("前端静态产物缺少 index.html")

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.middleware("http")
    async def frontend_files(request: Request, call_next):
        """先提供构建文件，再仅回退页面导航；API、缺失 assets 和显式文件不回退。"""
        path = request.url.path.lstrip("/")
        is_api = path == "api" or path.startswith("api/")
        if request.method in {"GET", "HEAD"} and not is_api and not path.startswith("assets/"):
            candidate = (root / path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                candidate = root
            if candidate.is_file():
                return FileResponse(candidate)

        response = await call_next(request)
        if (
            request.method in {"GET", "HEAD"}
            and not is_api
            and not path.startswith("assets/")
            and response.status_code == 404
            and not Path(path).suffix
        ):
            return FileResponse(index, media_type="text/html")
        return response
