"""标题与收藏引用；保留原文链接身份而不建立跨媒体事件。"""

from alembic import op
import sqlalchemy as sa

revision = "0002_articles"
down_revision = "0001_sources"
branch_labels = None
depends_on = None


def upgrade():
    """建立必要元信息和独立收藏时间，约束空标题及链接重复。"""
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("first_entry_id", sa.Integer(), sa.ForeignKey("source_entries.id"), nullable=False),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("dedup_url", sa.Text(collation="BINARY"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("reported_date", sa.Date(), nullable=True),
        sa.Column("category_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("product_type", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("image_credit", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dedup_url", name="uq_article_dedup_url"),
        sa.CheckConstraint("length(trim(title)) > 0 AND length(trim(original_url)) > 0 AND length(trim(dedup_url)) > 0", name="ck_article_identity"),
        sa.CheckConstraint("json_valid(category_codes) AND json_type(category_codes) = 'array'", name="ck_article_categories"),
    )
    op.create_index("ix_article_reported_id", "articles", [sa.text("reported_date DESC"), sa.text("id DESC")])
    op.create_table(
        "bookmarks",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_bookmark_created", "bookmarks", [sa.text("created_at DESC"), sa.text("article_id DESC")])


def downgrade():
    """先解除收藏引用再删除资讯，不删除来源身份。"""
    op.drop_index("ix_bookmark_created", table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_index("ix_article_reported_id", table_name="articles")
    op.drop_table("articles")
