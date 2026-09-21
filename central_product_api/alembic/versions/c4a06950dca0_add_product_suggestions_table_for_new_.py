"""Add product_suggestions table for new-product approval workflow

Revision ID: c4a06950dca0
Revises: 
Create Date: 2026-09-21 22:07:10.354517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a06950dca0'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The application currently bootstraps its legacy tables with
    # SQLAlchemy's metadata. Keep this migration safe for that setup while
    # still allowing a clean Alembic-managed database to create the new table.
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("product_suggestions"):
        return

    op.create_table(
        "product_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("sku", sa.String(length=128), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("sub_category", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("hsn", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("gst_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mrp", sa.Float(), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("purchase_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("pack_size", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("weight", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("batch_number", sa.String(length=128), nullable=True),
        sa.Column("manufacturing_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("serial_number", sa.String(length=128), nullable=True),
        sa.Column("license_certificate_info", sa.Text(), nullable=True),
        sa.Column("ingredients_attributes", sa.Text(), nullable=True),
        sa.Column("product_image", sa.String(length=512), nullable=True),
        sa.Column("product_box_image", sa.String(length=512), nullable=True),
        sa.Column("logo", sa.String(length=512), nullable=True),
        sa.Column("primary_color", sa.String(length=32), nullable=True),
        sa.Column("secondary_color", sa.String(length=32), nullable=True),
        sa.Column("custom_fields", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
        sa.UniqueConstraint("sku"),
        sa.UniqueConstraint("barcode"),
    )
    op.create_index("ix_product_suggestions_product_id", "product_suggestions", ["product_id"])
    op.create_index("ix_product_suggestions_sku", "product_suggestions", ["sku"])
    op.create_index("ix_product_suggestions_barcode", "product_suggestions", ["barcode"])
    op.create_index("ix_product_suggestions_product_name", "product_suggestions", ["product_name"])
    op.create_index("ix_product_suggestions_source_reference", "product_suggestions", ["source_reference"])


def downgrade() -> None:
    """Downgrade schema."""
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("product_suggestions"):
        op.drop_table("product_suggestions")
