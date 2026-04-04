"""Add unique constraint on url.original_url."""

import peewee as pw
from peewee_migrate import Migrator


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.sql(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_name = 'url'
                  AND constraint_name = 'url_original_url_key'
            ) THEN
                ALTER TABLE url
                ADD CONSTRAINT url_original_url_key UNIQUE (original_url);
            END IF;
        END $$;
        """
    )


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    migrator.sql(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE table_name = 'url'
                  AND constraint_name = 'url_original_url_key'
            ) THEN
                ALTER TABLE url DROP CONSTRAINT url_original_url_key;
            END IF;
        END $$;
        """
    )
