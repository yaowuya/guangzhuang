"""第七张业务表：仅存会话摘要与 UTC 生命周期时间。"""

from alembic import op
import sqlalchemy as sa

revision = "0004_sessions"
down_revision = "0003_jobs"
branch_labels = None
depends_on = None


def upgrade():
    """会话摘要唯一，过期索引用于清理；不读取部署密码或建立默认账户。"""
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_digest", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_digest", name="uq_session_digest"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])


def downgrade():
    """只卸载会话表；仅在获准的测试或回滚流程调用。"""
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")
