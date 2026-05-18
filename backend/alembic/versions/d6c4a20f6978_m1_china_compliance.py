"""M1_china_compliance

Revision ID: d6c4a20f6978
Revises: a1b2c3d4e5f6
Create Date: 2026-05-08 10:37:26.373092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6c4a20f6978'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table, col):
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(conn)
    return col in [c["name"] for c in insp.get_columns(table)]


def _has_table(conn, table):
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(conn)
    return insp.has_table(table)


def upgrade() -> None:
    """Upgrade schema — idempotent (handles pre-existing tables from create_all)."""
    conn = op.get_bind()

    # ── New tables (created idempotently) ──────────────────────────────────────
    if not _has_table(conn, 'labor_cost_indices'):
        op.create_table(
            'labor_cost_indices',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('region', sa.String(length=100), nullable=False),
            sa.Column('profession', sa.String(length=50), nullable=False),
            sa.Column('base_year', sa.String(length=10), nullable=False),
            sa.Column('period', sa.String(length=20), nullable=False),
            sa.Column('index_value', sa.Float(), nullable=False),
            sa.Column('source', sa.String(length=100), nullable=False),
            sa.Column('note', sa.String(length=255), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('region', 'profession', 'base_year', 'period',
                                name='uq_lci_region_prof_base_period'),
        )
        op.create_index('ix_lci_lookup', 'labor_cost_indices',
                        ['region', 'profession', 'period'], unique=False)

    if not _has_table(conn, 'pricing_standards'):
        op.create_table(
            'pricing_standards',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('name_zh', sa.String(length=255), nullable=False),
            sa.Column('name_en', sa.String(length=255), nullable=False),
            sa.Column('year', sa.Integer(), nullable=False),
            sa.Column('region', sa.String(length=100), nullable=False),
            sa.Column('profession', sa.String(length=50), nullable=False),
            sa.Column('coding_rule_json', sa.Text(), nullable=False),
            sa.Column('fee_structure_json', sa.Text(), nullable=False),
            sa.Column('rounding_rule', sa.String(length=50), nullable=False),
            sa.Column('effective_date', sa.String(length=20), nullable=False),
            sa.Column('superseded_by_id', sa.Integer(), nullable=True),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('is_active', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(),
                      server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code', 'region', name='uq_pricing_standard_code_region'),
        )

    if not _has_table(conn, 'calc_rule_dict'):
        op.create_table(
            'calc_rule_dict',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('pricing_standard_id', sa.Integer(), nullable=False),
            sa.Column('profession', sa.String(length=50), nullable=False),
            sa.Column('chapter', sa.String(length=255), nullable=False),
            sa.Column('section', sa.String(length=255), nullable=False),
            sa.Column('code_pattern', sa.String(length=20), nullable=False),
            sa.Column('item_name', sa.String(length=255), nullable=False),
            sa.Column('standard_unit', sa.String(length=50), nullable=False),
            sa.Column('rule_text', sa.Text(), nullable=False),
            sa.Column('work_content', sa.Text(), nullable=False),
            sa.Column('feature_template_json', sa.Text(), nullable=False),
            sa.Column('note', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['pricing_standard_id'], ['pricing_standards.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_crd_std_pattern', 'calc_rule_dict',
                        ['pricing_standard_id', 'code_pattern'], unique=False)

    if not _has_table(conn, 'fee_structures'):
        op.create_table(
            'fee_structures',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('pricing_standard_id', sa.Integer(), nullable=False),
            sa.Column('parent_id', sa.Integer(), nullable=True),
            sa.Column('fee_code', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('formula', sa.String(length=50), nullable=False),
            sa.Column('base_code', sa.String(length=100), nullable=False),
            sa.Column('default_rate', sa.Float(), nullable=False),
            sa.Column('is_competitive', sa.Integer(), nullable=False),
            sa.Column('is_leaf', sa.Integer(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(['parent_id'], ['fee_structures.id']),
            sa.ForeignKeyConstraint(['pricing_standard_id'], ['pricing_standards.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('pricing_standard_id', 'fee_code',
                                name='uq_fee_structure_std_code'),
        )
        op.create_index('ix_fee_structure_std', 'fee_structures',
                        ['pricing_standard_id'], unique=False)

    if not _has_table(conn, 'other_items'):
        op.create_table(
            'other_items',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('project_id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('sub_category', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('unit', sa.String(length=50), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('unit_price', sa.Float(), nullable=False),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.Column('is_fixed', sa.Integer(), nullable=False),
            sa.Column('tax_mode', sa.String(length=20), nullable=False),
            sa.Column('note', sa.Text(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_other_item_category', 'other_items', ['category'], unique=False)
        op.create_index('ix_other_item_project', 'other_items', ['project_id'], unique=False)

    # ── boq_items new columns ──────────────────────────────────────────────────
    for col_name, col_def in [
        ('code_segments_json', sa.Column('code_segments_json', sa.Text(), nullable=False, server_default='{}')),
        ('feature_json',       sa.Column('feature_json',       sa.Text(), nullable=False, server_default='{}')),
        ('calc_rule',          sa.Column('calc_rule',          sa.Text(), nullable=False, server_default='')),
        ('calc_formula',       sa.Column('calc_formula',       sa.Text(), nullable=False, server_default='')),
        ('work_content',       sa.Column('work_content',       sa.Text(), nullable=False, server_default='')),
        ('is_provisional',     sa.Column('is_provisional',     sa.Integer(), nullable=False, server_default='0')),
        ('parent_division_id', sa.Column('parent_division_id', sa.Integer(), nullable=True)),
        ('pricing_standard_id',sa.Column('pricing_standard_id',sa.Integer(), nullable=True)),
    ]:
        if not _has_column(conn, 'boq_items', col_name):
            op.add_column('boq_items', col_def)

    # ── projects new columns ───────────────────────────────────────────────────
    for col_name, col_def in [
        ('pricing_standard_id', sa.Column('pricing_standard_id', sa.Integer(), nullable=True)),
        ('profession',          sa.Column('profession',          sa.String(50), nullable=False, server_default='building')),
        ('tax_method',          sa.Column('tax_method',          sa.String(20), nullable=False, server_default='general')),
        ('labor_index_period',  sa.Column('labor_index_period',  sa.String(20), nullable=False, server_default='')),
    ]:
        if not _has_column(conn, 'projects', col_name):
            op.add_column('projects', col_def)

    # ── quota_items new columns ────────────────────────────────────────────────
    for col_name, col_def in [
        ('labor_fee',             sa.Column('labor_fee',             sa.Float(), nullable=False, server_default='0.0')),
        ('material_fee',          sa.Column('material_fee',          sa.Float(), nullable=False, server_default='0.0')),
        ('machine_fee',           sa.Column('machine_fee',           sa.Float(), nullable=False, server_default='0.0')),
        ('labor_index_base',      sa.Column('labor_index_base',      sa.Float(), nullable=False, server_default='1.0')),
        ('pricing_standard_id',   sa.Column('pricing_standard_id',   sa.Integer(), nullable=True)),
        ('profession',            sa.Column('profession',            sa.String(50),  nullable=False, server_default='')),
        ('region',                sa.Column('region',                sa.String(100), nullable=False, server_default='')),
        ('conversion_rules_json', sa.Column('conversion_rules_json', sa.Text(), nullable=False, server_default='{}')),
        ('unit_constraint_json',  sa.Column('unit_constraint_json',  sa.Text(), nullable=False, server_default='{}')),
    ]:
        if not _has_column(conn, 'quota_items', col_name):
            op.add_column('quota_items', col_def)

    # ── index on quota_items (idempotent via try/except) ─────────────────────
    try:
        op.create_index('ix_quota_item_std_prof', 'quota_items',
                        ['pricing_standard_id', 'profession'], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'quota_items', type_='foreignkey')
    op.drop_index('ix_quota_item_std_prof', table_name='quota_items')
    op.drop_column('quota_items', 'unit_constraint_json')
    op.drop_column('quota_items', 'conversion_rules_json')
    op.drop_column('quota_items', 'region')
    op.drop_column('quota_items', 'profession')
    op.drop_column('quota_items', 'pricing_standard_id')
    op.drop_column('quota_items', 'labor_index_base')
    op.drop_column('quota_items', 'machine_fee')
    op.drop_column('quota_items', 'material_fee')
    op.drop_column('quota_items', 'labor_fee')
    op.drop_constraint(None, 'projects', type_='foreignkey')
    op.drop_column('projects', 'labor_index_period')
    op.drop_column('projects', 'tax_method')
    op.drop_column('projects', 'profession')
    op.drop_column('projects', 'pricing_standard_id')
    op.drop_constraint(None, 'boq_items', type_='foreignkey')
    op.drop_constraint(None, 'boq_items', type_='foreignkey')
    op.drop_column('boq_items', 'pricing_standard_id')
    op.drop_column('boq_items', 'parent_division_id')
    op.drop_column('boq_items', 'is_provisional')
    op.drop_column('boq_items', 'work_content')
    op.drop_column('boq_items', 'calc_formula')
    op.drop_column('boq_items', 'calc_rule')
    op.drop_column('boq_items', 'feature_json')
    op.drop_column('boq_items', 'code_segments_json')
    op.drop_index('ix_other_item_project', table_name='other_items')
    op.drop_index('ix_other_item_category', table_name='other_items')
    op.drop_table('other_items')
    op.drop_index('ix_fee_structure_std', table_name='fee_structures')
    op.drop_table('fee_structures')
    op.drop_index('ix_crd_std_pattern', table_name='calc_rule_dict')
    op.drop_table('calc_rule_dict')
    op.drop_table('pricing_standards')
    op.drop_index('ix_lci_lookup', table_name='labor_cost_indices')
    op.drop_table('labor_cost_indices')
    # ### end Alembic commands ###
