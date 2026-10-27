#!/bin/sh
# Restore a backup into a database.
#
#   restore.sh latest <target database URL>
#   restore.sh daisytoons-2026-10-27T210000Z.dump <target database URL>
#
# The target's existing tables are replaced. To check a backup without touching the live
# shop, restore into a new, empty database (see deploy/README.md).
set -eu

if [ $# -ne 2 ]; then
  echo "Usage: restore.sh <backup name | latest> <target database URL>" >&2
  exit 2
fi
name=$1
target=$2
s3() { aws s3 --endpoint-url "$BACKUP_S3_ENDPOINT" "$@"; }

if [ "$name" = latest ]; then
  name=$(s3 ls "s3://$BACKUP_BUCKET/db/" | sort | tail -n 1 | awk '{print $4}')
  if [ -z "$name" ]; then
    echo "No backups found in s3://$BACKUP_BUCKET/db/" >&2
    exit 1
  fi
fi

file="/tmp/$name"
echo "Restoring $name"
s3 cp --only-show-errors "s3://$BACKUP_BUCKET/db/$name" "$file"
pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error --dbname="$target" "$file"
rm -f "$file"
echo "Restored $name"
