"""ASGI 稳定入口；实现位于 presentation.http。"""

from app.presentation.http.app import create_app

__all__ = ["create_app"]
