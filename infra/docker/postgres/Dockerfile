FROM postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/open-commerce-agent/
COPY security/third-party/postgresql-16.15/COPYRIGHT /usr/share/doc/postgresql/COPYRIGHT

# Compose starts as postgres, so the root-to-postgres switching helper is unused.
RUN apk upgrade --no-cache && rm -f /usr/local/bin/gosu
USER postgres
