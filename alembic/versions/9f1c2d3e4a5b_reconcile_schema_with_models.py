"""reconcile schema with models

The migration history never added most of the columns that the ORM models
declare, so a database provisioned with ``alembic upgrade head`` could not run
the application (missing soft-delete columns, AT assignment validity columns,
and three catalogue tables).

This revision is intentionally **idempotent**: every operation inspects the
current schema first. That makes it safe both for

* a brand new database (``alembic upgrade head`` from empty), and
* an existing database that was created with ``Base.metadata.create_all``
  (the developer/production databases, which already have most of it).

Revision ID: 9f1c2d3e4a5b
Revises: 2b1e39f5565d
"""

from alembic import op
import sqlalchemy as sa

revision = "9f1c2d3e4a5b"
down_revision = "2b1e39f5565d"
branch_labels = None
depends_on = None


# ── Tables that carry the soft-delete column family ──────────────────────────
# Column names are taken verbatim from models.py.
SOFT_DELETE_TABLES = [
    "action_plan_tracking",
    "at_assignments",
    "client_names",
    "commercial_advisors",
    "customers",
    "designers",
    "distributor_plants",
    "formado_types",
    "industrial_sectors",
    "inferior_closure_types",
    "infrastructure_surveys",
    "machine_types",
    "machines",
    "plant_names",
    "products",
    "quality_at_topics",
    "quality_topics",
    "technical_advisors",
    "technical_surveys",
    "technical_surveys_2",
    "technical_visits_2",
    "visit_topics",
    "visit_types",
]


def _inspector():
    return sa.inspect(op.get_bind())


def _table_names(insp) -> list:
    return list(insp.get_table_names())


def _column_names(insp, table: str) -> set:
    return {c["name"] for c in insp.get_columns(table)}


def _add_column_if_missing(insp, table: str, column: sa.Column) -> bool:
    """Add ``column`` to ``table`` when absent. Returns True when added."""
    if table not in _table_names(insp):
        return False
    if column.name in _column_names(insp, table):
        return False
    op.add_column(table, column)
    return True


def _index_names(insp, table: str) -> set:
    try:
        return {i["name"] for i in insp.get_indexes(table)}
    except Exception:
        return set()


def _create_index_if_missing(insp, name: str, table: str, columns: list, unique: bool = False):
    if table not in _table_names(insp):
        return False
    if name in _index_names(insp, table):
        return False
    op.create_index(name, table, columns, unique=unique)
    return True


def _column_kwargs(insp, table: str, name: str) -> dict:
    """Read existing column metadata so re-created indexes match the model."""
    for c in insp.get_columns(table):
        if c["name"] == name:
            return c
    return {}


# ── Upgrade ──────────────────────────────────────────────────────────────────
def upgrade() -> None:
    insp = _inspector()
    existing_tables = _table_names(insp)

    # 1. Missing catalogue tables ------------------------------------------------
    if "contact_names" not in existing_tables:
        op.create_table(
            "contact_names",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("inactivation_reason", sa.Text(), nullable=True),
            sa.Column("inactivated_by_id", sa.Integer(), nullable=True),
            sa.Column("inactivated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_contact_names_name", "contact_names", ["name"], unique=True)
        insp = _inspector()

    if "member_sectors" not in existing_tables:
        op.create_table(
            "member_sectors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("inactivation_reason", sa.Text(), nullable=True),
            sa.Column("inactivated_by_id", sa.Integer(), nullable=True),
            sa.Column("inactivated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_member_sectors_name", "member_sectors", ["name"], unique=True)
        insp = _inspector()

    if "meeting_minutes" not in existing_tables:
        op.create_table(
            "meeting_minutes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("fecha", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=True, server_default=sa.text("'Borrador'")),
            sa.Column("form_data", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("inactivation_reason", sa.Text(), nullable=True),
            sa.Column("inactivated_by_id", sa.Integer(), nullable=True),
            sa.Column("inactivated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        insp = _inspector()

    # 2. Soft-delete column family ---------------------------------------------
    # NOTE: is_active is created with server_default=true and the default is kept
    # on purpose. SQLite cannot ALTER COLUMN ... DROP DEFAULT, and leaving the
    # default in place is harmless (models.py also declares a Python-level
    # default of True) while making the column safe for existing rows that were
    # inserted by older code paths.
    for table in SOFT_DELETE_TABLES:
        if table not in _table_names(insp):
            continue
        _add_column_if_missing(
            insp, table, sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true())
        )
        _add_column_if_missing(insp, table, sa.Column("inactivation_reason", sa.Text(), nullable=True))
        _add_column_if_missing(insp, table, sa.Column("inactivated_by_id", sa.Integer(), nullable=True))
        _add_column_if_missing(insp, table, sa.Column("inactivated_at", sa.DateTime(), nullable=True))
        insp = _inspector()

    # 3. at_assignments validity columns ---------------------------------------
    if "at_assignments" in _table_names(insp):
        _add_column_if_missing(
            insp, "at_assignments",
            sa.Column("status", sa.String(), nullable=True, server_default=sa.text("'Activo'")),
        )
        _add_column_if_missing(insp, "at_assignments", sa.Column("valid_from", sa.DateTime(), nullable=True))
        _add_column_if_missing(insp, "at_assignments", sa.Column("valid_to", sa.DateTime(), nullable=True))
        insp = _inspector()

    # 4. action_plan_tracking.et_number ---------------------------------------
    if "action_plan_tracking" in _table_names(insp):
        _add_column_if_missing(insp, "action_plan_tracking", sa.Column("et_number", sa.String(), nullable=True))
        insp = _inspector()

    # 5. at_assignments.customer_name must NOT be unique ----------------------
    # The original schema created it UNIQUE; the application keeps *version rows*
    # per customer, so a unique index breaks the very first re-assignment.
    if "at_assignments" in _table_names(insp):
        for idx in insp.get_indexes("at_assignments"):
            cols = idx.get("column_names") or []
            if idx.get("unique") and cols == ["customer_name"]:
                op.drop_index(idx["name"], table_name="at_assignments")
                op.create_index("ix_at_assignments_customer_name", "at_assignments", ["customer_name"])
        insp = _inspector()

    # 6. at_assignments.customer_name has no index at all in some schemas -----
    _create_index_if_missing(insp, "ix_at_assignments_customer_name", "at_assignments", ["customer_name"])
    insp = _inspector()

    # 7. Drop the orphan technical_visits table -------------------------------
    # No model, no route and no data reference it; it was superseded by
    # technical_visits_2.
    if "technical_visits" in _table_names(insp):
        op.drop_table("technical_visits")
        insp = _inspector()

    # 8. Foreign keys that were never indexed ---------------------------------
    fk_indexes = [
        ("ix_machines_customer_id", "machines", ["customer_id"]),
        ("ix_technical_surveys_machine_id", "technical_surveys", ["machine_id"]),
        ("ix_technical_surveys_2_customer_id", "technical_surveys_2", ["customer_id"]),
        ("ix_technical_surveys_2_machine_id", "technical_surveys_2", ["machine_id"]),
        ("ix_infrastructure_surveys_customer_id", "infrastructure_surveys", ["customer_id"]),
        ("ix_action_plan_tracking_source_visit_id", "action_plan_tracking", ["source_visit_id"]),
        ("ix_at_assignments_inactivated_by_id", "at_assignments", ["inactivated_by_id"]),
    ]
    for name, table, cols in fk_indexes:
        _create_index_if_missing(insp, name, table, cols)

    # 9. Composite indexes for the measured hot query patterns ----------------
    composite_indexes = [
        # WHERE is_active = 1 ORDER BY name
        ("ix_customers_is_active_name", "customers", ["is_active", "name"]),
        ("ix_products_is_active_name", "products", ["is_active", "name"]),
        ("ix_machines_is_active_serial", "machines", ["is_active", "serial_number"]),
        # AT assignment "currently valid" lookups
        ("ix_at_assignments_customer_valid_to", "at_assignments", ["customer_name", "valid_to"]),
        ("ix_at_assignments_advisor_valid_to", "at_assignments", ["technical_advisor", "valid_to"]),
        # tracking list: is_active + created_at DESC
        ("ix_action_plan_tracking_active_created", "action_plan_tracking", ["is_active", "created_at"]),
        # trash listing: restored_at IS NULL [AND entity_type] ORDER BY deleted_at DESC
        ("ix_trash_items_restored_entity_deleted", "trash_items", ["restored_at", "entity_type", "deleted_at"]),
        # dashboard/visits: fecha range + status counts
        ("ix_technical_visits_2_fecha_status", "technical_visits_2", ["fecha", "status"]),
        ("ix_technical_visits_2_status_fecha", "technical_visits_2", ["status", "fecha"]),
        ("ix_technical_surveys_2_status_fecha", "technical_surveys_2", ["status", "fecha"]),
        ("ix_meeting_minutes_status_fecha", "meeting_minutes", ["status", "fecha"]),
    ]
    for name, table, cols in composite_indexes:
        _create_index_if_missing(insp, name, table, cols)


# ── Downgrade ────────────────────────────────────────────────────────────────
def downgrade() -> None:
    """Reverse only the additive, unambiguous parts.

    Dropping the soft-delete columns would destroy soft-delete state, so this
    intentionally keeps them and removes just what this revision created for
    convenience: the added indexes and the three catalogue tables.
    """
    insp = _inspector()

    drop_indexes = [
        ("ix_meeting_minutes_status_fecha", "meeting_minutes"),
        ("ix_technical_surveys_2_status_fecha", "technical_surveys_2"),
        ("ix_technical_visits_2_status_fecha", "technical_visits_2"),
        ("ix_technical_visits_2_fecha_status", "technical_visits_2"),
        ("ix_trash_items_restored_entity_deleted", "trash_items"),
        ("ix_action_plan_tracking_active_created", "action_plan_tracking"),
        ("ix_at_assignments_advisor_valid_to", "at_assignments"),
        ("ix_at_assignments_customer_valid_to", "at_assignments"),
        ("ix_machines_is_active_serial", "machines"),
        ("ix_products_is_active_name", "products"),
        ("ix_customers_is_active_name", "customers"),
        ("ix_at_assignments_inactivated_by_id", "at_assignments"),
        ("ix_action_plan_tracking_source_visit_id", "action_plan_tracking"),
        ("ix_infrastructure_surveys_customer_id", "infrastructure_surveys"),
        ("ix_technical_surveys_2_machine_id", "technical_surveys_2"),
        ("ix_technical_surveys_2_customer_id", "technical_surveys_2"),
        ("ix_technical_surveys_machine_id", "technical_surveys"),
        ("ix_machines_customer_id", "machines"),
    ]
    for name, table in drop_indexes:
        if table in _table_names(insp) and name in _index_names(insp, table):
            op.drop_index(name, table_name=table)

    for table in ("meeting_minutes", "member_sectors", "contact_names"):
        if table in _table_names(insp):
            op.drop_table(table)
