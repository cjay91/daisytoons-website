#!/usr/bin/env bash
# Proves a backup can be restored: back up the running Compose stack's database to the local
# object store, restore it into a fresh database, and compare the two.
#
# Needs: docker compose up, with some data in it (the smoke checkout adds an order).
set -euo pipefail

network=$(docker compose ps -q db | xargs docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}')
psql() { docker compose exec -T db psql -U daisytoons -d "$1" -tAc "$2"; }

docker build -q -t daisytoons-backup deploy/backup > /dev/null
run() {
  docker run --rm --network "$network" \
    -e DATABASE_URL=postgresql://daisytoons:daisytoons@db:5432/daisytoons \
    -e BACKUP_BUCKET=daisytoons-backups \
    -e BACKUP_S3_ENDPOINT=http://storage:8333 \
    -e AWS_ACCESS_KEY_ID=dev -e AWS_SECRET_ACCESS_KEY=dev -e AWS_DEFAULT_REGION=us-east-1 \
    daisytoons-backup "$@"
}

run aws s3 --endpoint-url http://storage:8333 mb s3://daisytoons-backups > /dev/null 2>&1 || true
run backup.sh

psql daisytoons "drop database if exists daisytoons_restore_check" > /dev/null
psql daisytoons "create database daisytoons_restore_check" > /dev/null
run restore.sh latest postgresql://daisytoons:daisytoons@db:5432/daisytoons_restore_check

fail=0
for table in products inventory orders order_items stock_adjustments staff customers alembic_version; do
  live=$(psql daisytoons "select count(*) from $table")
  restored=$(psql daisytoons_restore_check "select count(*) from $table")
  echo "$table: $live live, $restored restored"
  [ "$live" = "$restored" ] || fail=1
done
psql daisytoons "drop database daisytoons_restore_check" > /dev/null
if [ "$fail" -ne 0 ]; then
  echo "Restored database doesn't match" >&2
  exit 1
fi
echo "Backup restored and matches the live database"
