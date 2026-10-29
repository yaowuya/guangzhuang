"""标题阅读的显式持久模型；不引入审核、正文或图片存储对象。"""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, JSON, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """SQLite 不保留时区：写入前转 UTC，读取后显式恢复 UTC；拒绝含糊的无时区输入。"""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """只接受明确时区的事件时间，存储为规范 UTC 而非本机时间。"""
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("事件时间必须包含时区")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        """将 SQLite 返回的标准化无时区时间恢复为明确 UTC。"""
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
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
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    __table_args__ = (Index("ix_bookmark_created", created_at.desc(), article_id.desc()),)


class Session(Base):
    """服务端会话只存随机令牌摘要；删除记录即撤销，不存明文凭据。"""

    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_digest: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    __table_args__ = (UniqueConstraint("token_digest", name="uq_session_digest"),)


class UpdateJob(Base):
    """持久更新任务；每日补跑记录本身占用次数，活动索引防止重复入队。"""

    __tablename__ = "update_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    # 日程日期是 Asia/Shanghai 的自然日，与 UTC 事件时间分开保存。
    schedule_date: Mapped[date | None] = mapped_column(Date)
    active_key: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    entries: Mapped[list["EntryResult"]] = relationship(back_populates="job", order_by="EntryResult.id")
    __table_args__ = (
        CheckConstraint("active_key = 1", name="ck_job_active_key"),
        CheckConstraint("trigger IN ('schedule','catchup','refresh','retry')", name="ck_job_trigger"),
        CheckConstraint("state IN ('pending','running','succeeded','partial','failed','interrupted')", name="ck_job_state"),
        CheckConstraint("trigger NOT IN ('schedule','catchup') OR schedule_date IS NOT NULL", name="ck_job_date"),
        CheckConstraint("state IN ('pending','running') OR finished_at IS NOT NULL", name="ck_job_finished"),
        Index("uq_active_job", active_key, unique=True, sqlite_where=text("state IN ('pending','running')")),
        Index("uq_daily_schedule", schedule_date, unique=True, sqlite_where=text("trigger='schedule'")),
        Index("uq_daily_catchup", schedule_date, unique=True, sqlite_where=text("trigger='catchup'")),
    )


class EntryResult(Base):
    """一次任务中一个入口的结果，允许部分成功，不保留原始网页响应。"""

    __tablename__ = "entry_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("update_jobs.id"), nullable=False)
    entry_id: Mapped[int] = mapped_column(ForeignKey("source_entries.id"), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    count_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    count_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    job: Mapped[UpdateJob] = relationship(back_populates="entries")
    __table_args__ = (
        UniqueConstraint("job_id", "entry_id", name="uq_job_entry_result"),
        CheckConstraint("state IN ('pending','running','succeeded','failed','interrupted')", name="ck_result_state"),
        CheckConstraint("count_added >= 0 AND count_updated >= 0", name="ck_result_counts"),
        CheckConstraint("state IN ('pending','running') OR finished_at IS NOT NULL", name="ck_result_finished"),
    )
