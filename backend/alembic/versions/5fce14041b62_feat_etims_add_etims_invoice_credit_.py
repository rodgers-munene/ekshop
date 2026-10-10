"""feat(etims): add eTIMS invoice, credit note, and queue tables

Revision ID: 5fce14041b62
Revises: e1f2a3b4c5d6
Create Date: 2026-10-10 16:12:30.157867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5fce14041b62'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - eTIMS tables only. Uses VARCHAR + CHECK instead of ENUM to avoid type conflicts."""

    # etims_invoices
    op.create_table(
        'etims_invoices',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_group_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('order_groups.id', ondelete='RESTRICT'), nullable=False, unique=True),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cu_invoice_number', sa.String(50), unique=True, nullable=True),
        sa.Column('cu_serial_number', sa.String(50), nullable=True),
        sa.Column('kra_qr_code', sa.Text, nullable=True),
        sa.Column('kra_signature', sa.Text, nullable=True),
        sa.Column('kra_validation_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('seller_tin', sa.String(20), nullable=False),
        sa.Column('seller_name', sa.String(200), nullable=False),
        sa.Column('seller_address', sa.Text, nullable=False),
        sa.Column('seller_device_id', sa.String(50), nullable=False),
        sa.Column('buyer_tin', sa.String(20), nullable=True),
        sa.Column('buyer_name', sa.String(200), nullable=False),
        sa.Column('buyer_address', sa.Text, nullable=False),
        sa.Column('invoice_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('invoice_type', sa.String(20), nullable=False, server_default='invoice'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='KES'),
        sa.Column('exchange_rate', sa.Numeric(10, 6), nullable=False, server_default='1.0'),
        sa.Column('subtotal', sa.String(20), nullable=False),
        sa.Column('tax_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('discount_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('delivery_fee', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('total', sa.String(20), nullable=False),
        sa.Column('vat_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_etims_invoices_order_group_id', 'etims_invoices', ['order_group_id'])
    op.create_index('ix_etims_invoices_cu_invoice_number', 'etims_invoices', ['cu_invoice_number'])
    op.create_index('ix_etims_invoices_status', 'etims_invoices', ['status'])
    op.create_index('ix_etims_invoices_created_at', 'etims_invoices', ['created_at'])

    # CHECK constraints for enum-like columns
    op.create_check_constraint(
        'ck_etims_invoices_invoice_type',
        'etims_invoices',
        "invoice_type IN ('invoice', 'credit_note', 'debit_note')"
    )
    op.create_check_constraint(
        'ck_etims_invoices_status',
        'etims_invoices',
        "status IN ('pending', 'submitted', 'validated', 'rejected', 'cancelled')"
    )

    # etims_invoice_items
    op.create_table(
        'etims_invoice_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('invoice_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('etims_invoices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order_item_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('order_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('item_code', sa.String(50), nullable=True),
        sa.Column('item_name', sa.String(200), nullable=False),
        sa.Column('item_description', sa.Text, nullable=True),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit_of_measure', sa.String(20), nullable=False, server_default='pcs'),
        sa.Column('unit_price', sa.String(20), nullable=False),
        sa.Column('discount_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('tax_rate', sa.Numeric(5, 4), nullable=False, server_default='0.16'),
        sa.Column('tax_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('line_total', sa.String(20), nullable=False),
        sa.Column('hs_code', sa.String(20), nullable=True),
        sa.Column('tax_category', sa.String(20), nullable=False, server_default='standard'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_etims_invoice_items_invoice_id', 'etims_invoice_items', ['invoice_id'])
    op.create_index('ix_etims_invoice_items_order_item_id', 'etims_invoice_items', ['order_item_id'])

    # etims_credit_notes
    op.create_table(
        'etims_credit_notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('original_invoice_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('etims_invoices.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('order_group_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('order_groups.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('return_request_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('return_requests.id', ondelete='SET NULL'), nullable=True),
        sa.Column('cu_credit_note_number', sa.String(50), unique=True, nullable=True),
        sa.Column('cu_serial_number', sa.String(50), nullable=True),
        sa.Column('kra_qr_code', sa.Text, nullable=True),
        sa.Column('kra_signature', sa.Text, nullable=True),
        sa.Column('kra_validation_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_cu_invoice_number', sa.String(50), nullable=False),
        sa.Column('original_cu_serial_number', sa.String(50), nullable=False),
        sa.Column('reason', sa.String(100), nullable=False),
        sa.Column('reason_detail', sa.Text, nullable=True),
        sa.Column('total_amount', sa.String(20), nullable=False),
        sa.Column('tax_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='KES'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('validated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_etims_credit_notes_original_invoice_id', 'etims_credit_notes', ['original_invoice_id'])
    op.create_index('ix_etims_credit_notes_order_group_id', 'etims_credit_notes', ['order_group_id'])
    op.create_index('ix_etims_credit_notes_cu_credit_note_number', 'etims_credit_notes', ['cu_credit_note_number'])
    op.create_index('ix_etims_credit_notes_status', 'etims_credit_notes', ['status'])

    op.create_check_constraint(
        'ck_etims_credit_notes_status',
        'etims_credit_notes',
        "status IN ('pending', 'submitted', 'validated', 'rejected', 'cancelled')"
    )

    # etims_credit_note_items
    op.create_table(
        'etims_credit_note_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('credit_note_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('etims_credit_notes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_invoice_item_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('etims_invoice_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('item_name', sa.String(200), nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('unit_of_measure', sa.String(20), nullable=False, server_default='pcs'),
        sa.Column('unit_price', sa.String(20), nullable=False),
        sa.Column('tax_rate', sa.Numeric(5, 4), nullable=False, server_default='0.16'),
        sa.Column('tax_amount', sa.String(20), nullable=False, server_default='0.00'),
        sa.Column('line_total', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index('ix_etims_credit_note_items_credit_note_id', 'etims_credit_note_items', ['credit_note_id'])

    # etims_queue
    op.create_table(
        'etims_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_type', sa.String(20), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_etims_queue_status_priority', 'etims_queue', ['status', 'priority'])
    op.create_index('ix_etims_queue_next_retry_at', 'etims_queue', ['next_retry_at'])
    op.create_index('ix_etims_queue_document', 'etims_queue', ['document_type', 'document_id'])

    op.create_check_constraint(
        'ck_etims_queue_document_type',
        'etims_queue',
        "document_type IN ('invoice', 'credit_note', 'debit_note')"
    )
    op.create_check_constraint(
        'ck_etims_queue_status',
        'etims_queue',
        "status IN ('pending', 'processing', 'completed', 'failed', 'dead_letter')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_etims_queue_document', table_name='etims_queue')
    op.drop_index('ix_etims_queue_next_retry_at', table_name='etims_queue')
    op.drop_index('ix_etims_queue_status_priority', table_name='etims_queue')
    op.drop_table('etims_queue')

    op.drop_index('ix_etims_credit_note_items_credit_note_id', table_name='etims_credit_note_items')
    op.drop_table('etims_credit_note_items')

    op.drop_index('ix_etims_credit_notes_status', table_name='etims_credit_notes')
    op.drop_index('ix_etims_credit_notes_cu_credit_note_number', table_name='etims_credit_notes')
    op.drop_index('ix_etims_credit_notes_order_group_id', table_name='etims_credit_notes')
    op.drop_index('ix_etims_credit_notes_original_invoice_id', table_name='etims_credit_notes')
    op.drop_table('etims_credit_notes')

    op.drop_index('ix_etims_invoice_items_order_item_id', table_name='etims_invoice_items')
    op.drop_index('ix_etims_invoice_items_invoice_id', table_name='etims_invoice_items')
    op.drop_table('etims_invoice_items')

    op.drop_index('ix_etims_invoices_created_at', table_name='etims_invoices')
    op.drop_index('ix_etims_invoices_status', table_name='etims_invoices')
    op.drop_index('ix_etims_invoices_cu_invoice_number', table_name='etims_invoices')
    op.drop_index('ix_etims_invoices_order_group_id', table_name='etims_invoices')
    op.drop_table('etims_invoices')