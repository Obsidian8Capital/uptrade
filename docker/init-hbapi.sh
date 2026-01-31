#!/bin/bash
# Create the hummingbot_api database and user if they don't exist.
# This runs as part of the TimescaleDB entrypoint (mounted into initdb.d).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'hbot') THEN
            CREATE ROLE hbot WITH LOGIN PASSWORD 'hummingbot-api';
        END IF;
    END
    \$\$;

    SELECT 'CREATE DATABASE hummingbot_api OWNER hbot'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'hummingbot_api')\gexec
EOSQL
