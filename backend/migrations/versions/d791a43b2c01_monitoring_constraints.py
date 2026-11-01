"""Monitoring result constraints."""

from alembic import op

revision = "d791a43b2c01"
down_revision = "485ea6449e71"
branch_labels = None
depends_on = None


def upgrade():
    op.create_check_constraint(
        "ck_expected_status",
        "services",
        "expected_status_min BETWEEN 100 AND 599 AND expected_status_max BETWEEN expected_status_min AND 599",
    )
    op.create_check_constraint("ck_check_attempts", "checks", "attempts BETWEEN 1 AND 2")
    op.create_check_constraint(
        "ck_check_status", "checks", "status IN ('unknown','healthy','degraded','down')"
    )


def downgrade():
    op.drop_constraint("ck_check_status", "checks", type_="check")
    op.drop_constraint("ck_check_attempts", "checks", type_="check")
    op.drop_constraint("ck_expected_status", "services", type_="check")
