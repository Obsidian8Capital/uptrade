#!/bin/bash
set -e
pg_isready -U "${POSTGRES_USER:-uptrade}" -d "${POSTGRES_DB:-uptrade}"
