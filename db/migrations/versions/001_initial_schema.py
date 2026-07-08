"""Initial schema with PostGIS and FTS

Revision ID: 001
Revises:
Create Date: 2026-07-08
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

scrape_job_status = postgresql.ENUM(
    "pending", "running", "success", "failed", name="scrape_job_status", create_type=False
)
api_key_tier = postgresql.ENUM("free", "pro", "enterprise", name="api_key_tier", create_type=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    scrape_job_status.create(op.get_bind(), checkfirst=True)
    api_key_tier.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("region", sa.String(100), nullable=False, server_default=""),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/Los_Angeles"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("scrape_frequency_minutes", sa.Integer(), nullable=False, server_default="360"),
        sa.Column("selectors", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("default_category", sa.String(64), nullable=False, server_default="music"),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "venues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("location", Geography(geometry_type="POINT", srid=4326), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", "city", name="uq_venues_name_city"),
    )
    op.create_index("ix_venues_location", "venues", ["location"], postgresql_using="gist")

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("venue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("venues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dedupe_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.String(64), nullable=False, server_default="music"),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("price_text", sa.String(128), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_events_start_time", "events", ["start_time"])
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_search_vector", "events", ["search_vector"], postgresql_using="gin")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION events_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.description, '')), 'B');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_search_vector_trigger
        BEFORE INSERT OR UPDATE ON events
        FOR EACH ROW EXECUTE FUNCTION events_search_vector_update();
        """
    )

    op.create_table(
        "scrape_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", scrape_job_status, nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("events_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "bookmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "event_id", name="uq_bookmarks_user_event"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("tier", api_key_tier, nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("bookmarks")
    op.drop_table("scrape_jobs")
    op.execute("DROP TRIGGER IF EXISTS events_search_vector_trigger ON events")
    op.execute("DROP FUNCTION IF EXISTS events_search_vector_update()")
    op.drop_index("ix_events_search_vector", table_name="events")
    op.drop_index("ix_events_category", table_name="events")
    op.drop_index("ix_events_start_time", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_venues_location", table_name="venues")
    op.drop_table("venues")
    op.drop_table("sources")
    api_key_tier.drop(op.get_bind(), checkfirst=True)
    scrape_job_status.drop(op.get_bind(), checkfirst=True)
