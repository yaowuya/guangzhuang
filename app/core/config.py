"""单机服务的显式配置；私密值从部署挂载文件读取，不附带默认口令。"""

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import urlsplit

from argon2 import Type, extract_parameters
from argon2.exceptions import InvalidHashError


@dataclass(frozen=True)
class Settings:
    """保存当前进程的已确认运行参数；实例化本身不访问网络或数据库。"""

    database_url: str
    public_origin: str
    password_hash: str = field(repr=False)
    csrf_key: str = field(repr=False)
    source_config: Path
    rules_config: Path
    data_dir: Path
    backup_dir: Path
    trusted_gateway_ip: str = ""
    static_dir: Path | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        """校验正式部署凭据与唯一 HTTPS 入口，缺少时拒绝启动。"""
        origin = os.getenv("PUBLIC_ORIGIN", "")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("PUBLIC_ORIGIN 必须为单一 HTTPS 站点")

        password_file = os.getenv("PASSWORD_HASH_FILE")
        csrf_file = os.getenv("CSRF_KEY_FILE")
        if not password_file or not csrf_file:
            raise ValueError("缺少私密密码摘要或会话防护密钥文件配置")
        try:
            password_hash = Path(password_file).read_text(encoding="utf-8").strip()
            csrf_key = Path(csrf_file).read_text(encoding="utf-8").strip()
        except OSError as error:
            raise ValueError("私密配置文件不可读取") from error
        try:
            parameters = extract_parameters(password_hash)
        except InvalidHashError:
            raise ValueError("密码摘要格式无效") from None
        if parameters.type is not Type.ID or len(csrf_key) < 32:
            raise ValueError("私密配置格式不符合单人服务要求")

        data_dir = Path(os.getenv("DATA_DIR", "/data"))
        return cls(
            database_url=os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'intelligence.sqlite3'}"),
            public_origin=origin.rstrip("/"),
            password_hash=password_hash,
            csrf_key=csrf_key,
            source_config=Path(os.getenv("SOURCE_CONFIG", "config/sources.json")),
            rules_config=Path(os.getenv("RULES_CONFIG", "config/classification.json")),
            data_dir=data_dir,
            backup_dir=Path(os.getenv("BACKUP_DIR", "/backups")),
            trusted_gateway_ip=os.getenv("TRUSTED_GATEWAY_IP", ""),
            static_dir=Path(os.getenv("STATIC_DIR", "/srv/app/static")),
        )
