FROM qdrant/qdrant:v1.19.1@sha256:12364fe851b9f17356fc88189fc06d1b521262e04659ec7345975b00c9246a10
LABEL org.opencontainers.image.licenses="Apache-2.0"

COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/open-commerce-agent/
COPY security/third-party/qdrant-1.19.1/manifest.json /usr/share/doc/open-commerce-agent/qdrant/manifest.json
ADD security/third-party/qdrant-1.19.1/notices.tar.gz /usr/share/doc/open-commerce-agent/qdrant/notices/

ENV QDRANT__TELEMETRY_DISABLED=true
ENV QDRANT__SERVICE__ENABLE_STATIC_CONTENT=false

USER root
COPY infra/docker/harden-debian.sh /usr/local/sbin/harden-debian
COPY infra/docker/prune-runtime-acl.sh /usr/local/sbin/prune-runtime-acl
RUN sh /usr/local/sbin/harden-debian && rm /usr/local/sbin/harden-debian
RUN rm -rf /qdrant/static
RUN mkdir -p /qdrant/storage /qdrant/snapshots && chown -R 1000:1000 /qdrant/storage /qdrant/snapshots
COPY infra/docker/qdrant/healthcheck /usr/local/bin/qdrant-healthcheck
USER 1000:1000

# The upstream shell wrapper exits its interrupted wait before Qdrant finishes
# flushing storage. Let the server receive and finish handling SIGTERM as PID 1.
CMD ["./qdrant"]
