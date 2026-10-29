"""备份恢复稳定命令入口；实现位于 infrastructure.persistence。"""

from app.infrastructure.persistence.backup import (
    backup_once,
    daily_backup,
    main,
    restore_backup,
)

__all__ = ["backup_once", "daily_backup", "restore_backup", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
