"""交互生成 Compose 所需 Argon2id 摘要与 CSRF 密钥文件。"""

import argparse
from getpass import getpass
import os
from pathlib import Path
import secrets

from argon2 import PasswordHasher


def write_private(path: Path, value: str, *, force: bool) -> None:
    """以 0600 临时文件原子写入秘密，默认拒绝覆盖。"""
    if path.exists() and not force:
        raise SystemExit(f"秘密已存在，拒绝覆盖：{path}")
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value.rstrip() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """交互确认密码后写入私密摘要和 CSRF 密钥；默认拒绝覆盖已有文件。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="deploy/secrets")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    password = getpass("本地单人登录密码：")
    confirmation = getpass("再次输入密码：")
    if not password or password != confirmation:
        raise SystemExit("两次密码不一致或为空")

    directory = Path(args.directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    write_private(directory / "password.hash", PasswordHasher().hash(password), force=args.force)
    write_private(directory / "csrf.key", secrets.token_urlsafe(48), force=args.force)
    print(f"已生成秘密目录：{directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
