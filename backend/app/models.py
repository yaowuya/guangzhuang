"""标题阅读的显式持久模型；不引入审核、正文或图片存储对象。"""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """仅提供 SQLAlchemy 映射元数据，不继承隐含业务字段。"""


class Source(Base):
    """固定站点身份与汇总状态；网站允许不意味着每个入口均获许可。"""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("key", name="uq_source_key"),
        CheckConstraint("length(trim(key)) > 0 AND length(trim(name)) > 0", name="ck_source_identity"),
        CheckConstraint("verification_status IN ('pending','allowed','partial','restricted')", name="ck_source_status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    reason: Mapped[str | None] = mapped_column(Text)


class SourceEntry(Base):
    """单个 RSS／列表入口；许可依据与访问失败分别持久保存。"""

    __tablename__ = "source_entries"
    __table_args__ = (
        UniqueConstraint("source_id", "url", name="uq_source_entry_url"),
        CheckConstraint("length(trim(url)) > 0", name="ck_entry_url"),
        CheckConstraint("kind IN ('rss','public_list')", name="ck_entry_kind"),
        CheckConstraint("verification_status IN ('pending','allowed','restricted')", name="ck_entry_status"),
        CheckConstraint(
            "verification_status = 'pending' OR (verification_reason IS NOT NULL AND "
            "length(trim(verification_reason)) > 0 AND verification_reference IS NOT NULL AND "
            "length(trim(verification_reference)) > 0)", name="ck_entry_evidence",
        ),
        CheckConstraint("NOT enabled OR verification_status = 'allowed'", name="ck_entry_enabled"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    verification_reason: Mapped[str | None] = mapped_column(Text)
    verification_reference: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean(create_constraint=True, name="ck_entry_bool"), nullable=False, default=False, server_default=text("0"))
    # UTC 成功时间只在实际成功处理后更新，访问错误不能抹除许可依据。
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
