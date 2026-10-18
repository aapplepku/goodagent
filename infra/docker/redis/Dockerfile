FROM redis:7-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499

# Keep the pinned Redis binary while refreshing supported Alpine security fixes.
USER root
RUN apk upgrade --no-cache
# Preserve Redis's upstream terms and bundled notices, not the project's Apache license.
COPY security/third-party/redis-7.4.11/ /usr/share/doc/redis/
USER redis
