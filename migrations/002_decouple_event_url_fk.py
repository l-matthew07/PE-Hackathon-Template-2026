"""Decouple event.url_id from URL foreign key to retain log records."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.sql(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'event_url_id_fkey'
                  AND table_name = 'event'
            ) THEN
                ALTER TABLE event DROP CONSTRAINT event_url_id_fkey;
            END IF;
        END $$;
        """
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'event_url_id_fkey'
                  AND table_name = 'event'
            ) THEN
                ALTER TABLE event
                ADD CONSTRAINT event_url_id_fkey
                FOREIGN KEY (url_id) REFERENCES url (id);
            END IF;
        END $$;
        """
    )
