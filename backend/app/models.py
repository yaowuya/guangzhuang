"""标题阅读的显式持久模型；不引入审核、正文或图片存储对象。"""

from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint, text
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


class Article(Base):
    """原文链接对应的一条资讯；只保存标题元信息，不保存文章或图片。"""

    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False)
    first_entry_id: Mapped[int] = mapped_column(ForeignKey("source_entries.id"), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_url: Mapped[str] = mapped_column(Text(collation="BINARY"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    search_text: Mapped[str] = mapped_column(Text, nullable=False)
    # 未知日期就是 NULL，不能用 updated_at 或采集时间补造。
    reported_date: Mapped[date | None] = mapped_column(Date)
    category_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    region: Mapped[str | None] = mapped_column(Text)
    product_type: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    image_credit: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("dedup_url", name="uq_article_dedup_url"),
        CheckConstraint("length(trim(title)) > 0 AND length(trim(original_url)) > 0 AND length(trim(dedup_url)) > 0", name="ck_article_identity"),
        CheckConstraint("json_valid(category_codes) AND json_type(category_codes) = 'array'", name="ck_article_categories"),
        Index("ix_article_reported_id", reported_date.desc(), id.desc()),
    )


class Bookmark(Base):
    """单人收藏引用资讯本身；取消只删关系，条目更新不重置收藏时间。"""

    __tablename__ = "bookmarks"
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (Index("ix_bookmark_created", created_at.desc(), article_id.desc()),)
