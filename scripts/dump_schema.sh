#!/usr/bin/env sh
# Обновляет db/bookstore_schema.sql выгрузкой из базы в контейнере db (правило из CLAUDE.md:
# файл схемы не правится руками). Запуск после миграций: sh scripts/dump_schema.sh
#
# --restrict-key фиксирует ключ строки \restrict: иначе он случайный и меняется при каждой выгрузке.
# alembic_version — служебная таблица Alembic, к схеме магазина не относится.
set -eu

cd "$(dirname "$0")/.."
docker compose exec -T db sh -c \
    'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --schema-only \
        --restrict-key=bookstore --exclude-table=public.alembic_version' \
    > db/bookstore_schema.sql
echo "db/bookstore_schema.sql обновлён"
