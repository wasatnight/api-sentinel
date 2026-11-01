"""Restrict outbound monitoring to GET and HEAD."""
import sqlalchemy as sa
from alembic import op

revision = "12ab34cd56ef"
down_revision = "7c2755bf91f2"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT count(*) FROM services WHERE method NOT IN ('GET','HEAD')")).scalar():
        raise RuntimeError("Review existing services with unsupported methods before upgrading; no services were modified.")
    op.drop_constraint("ck_service_method", "services", type_="check")
    op.create_check_constraint("ck_service_method", "services", "method IN ('GET','HEAD')")


def downgrade():
    op.drop_constraint("ck_service_method", "services", type_="check")
    op.create_check_constraint("ck_service_method", "services", "method IN ('GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS')")
