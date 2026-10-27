# Nightly database backups to S3-compatible storage (Cloudflare R2 in production).
# pg_dump must be the same major version as the database (Postgres 17).
FROM postgres:17-alpine

RUN apk add --no-cache aws-cli tzdata

COPY backup.sh restore.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh

# 02:30 Sri Lanka time every night. The container's clock runs in that zone (TZ below).
ENV TZ=Asia/Colombo
RUN echo "30 2 * * * /usr/local/bin/backup.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root

CMD ["crond", "-f", "-l", "8"]
