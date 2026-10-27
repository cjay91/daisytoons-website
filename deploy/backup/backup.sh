#!/bin/sh
# Dump the database and upload it to the backup bucket, then delete backups older than
# BACKUP_KEEP_DAYS. Run nightly by cron in the backup container; safe to run by hand:
#   docker compose -f deploy/docker-compose.prod.yml exec backup backup.sh
#
# Needs: DATABASE_URL (postgresql://...), BACKUP_BUCKET, BACKUP_S3_ENDPOINT,
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY. Optional: BACKUP_KEEP_DAYS (default 30),
# BACKUP_PING_URL (pinged after a good backup, for an alert when backups stop).
set -eu

keep_days=${BACKUP_KEEP_DAYS:-30}
stamp=$(date -u +%Y-%m-%dT%H%M%SZ)
file="/tmp/daisytoons-$stamp.dump"
s3() { aws s3 --endpoint-url "$BACKUP_S3_ENDPOINT" "$@"; }

echo "Backing up the database to s3://$BACKUP_BUCKET/db/daisytoons-$stamp.dump"
# Custom format: compressed, and pg_restore can restore all of it or single tables.
pg_dump --format=custom --no-owner --no-privileges --dbname="$DATABASE_URL" --file="$file"
s3 cp --only-show-errors "$file" "s3://$BACKUP_BUCKET/db/daisytoons-$stamp.dump"
size=$(wc -c < "$file")
rm -f "$file"
echo "Uploaded $size bytes"

cutoff=$(date -u -d "@$(( $(date +%s) - keep_days * 86400 ))" +%Y-%m-%d)
s3 ls "s3://$BACKUP_BUCKET/db/" | while read -r day _time _size name; do
  if [ -n "$name" ] && [ "$day" \< "$cutoff" ]; then
    echo "Deleting old backup $name"
    s3 rm --only-show-errors "s3://$BACKUP_BUCKET/db/$name"
  fi
done

if [ -n "${BACKUP_PING_URL:-}" ]; then
  wget -q -O /dev/null "$BACKUP_PING_URL" || echo "Could not ping $BACKUP_PING_URL"
fi
echo "Backup done"
