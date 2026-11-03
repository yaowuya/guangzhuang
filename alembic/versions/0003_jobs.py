"""持久任务与单入口结果；部分唯一索引是并发和重启后的最终兜底。"""

from alembic import op
import sqlalchemy as sa

revision = "0003_jobs"
down_revision = "0002_articles"
branch_labels = None
depends_on = None


def upgrade():
    """活动任务共用常量键，每日 schedule/catchup 各自最多一条。"""
    op.create_table(
        "update_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schedule_date", sa.Date(), nullable=True),
        sa.Column("active_key", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("active_key = 1", name="ck_job_active_key"),
        sa.CheckConstraint("trigger IN ('schedule','catchup','refresh','retry')", name="ck_job_trigger"),
        sa.CheckConstraint("state IN ('pending','running','succeeded','partial','failed','interrupted')", name="ck_job_state"),
        sa.CheckConstraint("trigger NOT IN ('schedule','catchup') OR schedule_date IS NOT NULL", name="ck_job_date"),
        sa.CheckConstraint("state IN ('pending','running') OR finished_at IS NOT NULL", name="ck_job_finished"),
    )
    op.create_index("uq_active_job", "update_jobs", ["active_key"], unique=True,
                    sqlite_where=sa.text("state IN ('pending','running')"))
    op.create_index("uq_daily_schedule", "update_jobs", ["schedule_date"], unique=True,
                    sqlite_where=sa.text("trigger='schedule'"))
    op.create_index("uq_daily_catchup", "update_jobs", ["schedule_date"], unique=True,
                    sqlite_where=sa.text("trigger='catchup'"))
    op.create_table(
        "entry_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("update_jobs.id"), nullable=False),
        sa.Column("entry_id", sa.Integer(), sa.ForeignKey("source_entries.id"), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("count_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("count_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", "entry_id", name="uq_job_entry_result"),
        sa.CheckConstraint("state IN ('pending','running','succeeded','failed','interrupted')", name="ck_result_state"),
        sa.CheckConstraint("count_added >= 0 AND count_updated >= 0", name="ck_result_counts"),
        sa.CheckConstraint("state IN ('pending','running') OR finished_at IS NOT NULL", name="ck_result_finished"),
    )


def downgrade():
    """只按依赖逆序卸载当前迁移；生产回滚必须先确认备份损失窗口。"""
    op.drop_table("entry_results")
    op.drop_index("uq_daily_catchup", table_name="update_jobs")
    op.drop_index("uq_daily_schedule", table_name="update_jobs")
    op.drop_index("uq_active_job", table_name="update_jobs")
    op.drop_table("update_jobs")
