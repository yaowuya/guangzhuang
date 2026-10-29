"""创建固定站点与各入口许可数据；回滚先删除外键引用方。"""

from alembic import op
import sqlalchemy as sa

revision = "0001_sources"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """将许可和运行状态分离，并由物理约束防止未获准入口被启用。"""
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.UniqueConstraint("key", name="uq_source_key"),
        sa.CheckConstraint("length(trim(key)) > 0 AND length(trim(name)) > 0", name="ck_source_identity"),
        sa.CheckConstraint("verification_status IN ('pending','allowed','partial','restricted')", name="ck_source_status"),
    )
    op.create_table(
        "source_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("verification_reason", sa.Text(), nullable=True),
        sa.Column("verification_reference", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(create_constraint=True, name="ck_entry_bool"), nullable=False, server_default=sa.text("0")),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_id", "url", name="uq_source_entry_url"),
        sa.CheckConstraint("length(trim(url)) > 0", name="ck_entry_url"),
        sa.CheckConstraint("kind IN ('rss','public_list')", name="ck_entry_kind"),
        sa.CheckConstraint("verification_status IN ('pending','allowed','restricted')", name="ck_entry_status"),
        sa.CheckConstraint(
            "verification_status = 'pending' OR (verification_reason IS NOT NULL AND "
            "length(trim(verification_reason)) > 0 AND verification_reference IS NOT NULL AND "
            "length(trim(verification_reference)) > 0)", name="ck_entry_evidence",
        ),
        sa.CheckConstraint("NOT enabled OR verification_status = 'allowed'", name="ck_entry_enabled"),
    )


def downgrade():
    """仅卸载本版本建立的表，不处理真实来源或用户业务数据。"""
    op.drop_table("source_entries")
    op.drop_table("sources")
