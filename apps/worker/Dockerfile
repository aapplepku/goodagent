FROM python:3.12-slim-trixie@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.15@sha256:a5727064a0de127bdb7c9d3c1383f3a9ac307d9f2d8a391edc7896c54289ced0 /uv /usr/local/bin/uv

WORKDIR /app

# Keep installed sources authoritative; avoid generated per-build import caches.
ENV UV_COMPILE_BYTECODE=0
ENV UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
COPY alembic.ini ./
COPY scripts ./scripts
COPY packages/backend ./packages/backend

ARG LEARNED_SEARCH=0
RUN if [ "$LEARNED_SEARCH" = "1" ]; then uv sync --frozen --all-packages --no-dev --all-extras; else uv sync --frozen --all-packages --no-dev; fi

FROM python:3.12-slim-trixie@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS runtime
LABEL org.opencontainers.image.licenses="Apache-2.0"
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip* /usr/local/bin/pip*
COPY infra/docker/harden-debian.sh /usr/local/sbin/harden-debian
COPY infra/docker/prune-runtime-acl.sh /usr/local/sbin/prune-runtime-acl
RUN sh /usr/local/sbin/harden-debian && rm /usr/local/sbin/harden-debian
COPY --from=build /app /app
RUN mkdir -p /app/.opencommerce/assets && chown -R 10001:10001 /app/.opencommerce
COPY --from=build /app/LICENSE /app/NOTICE /app/THIRD_PARTY_NOTICES.md /usr/share/doc/open-commerce-agent/
COPY security/third-party/learned-search /usr/share/doc/open-commerce-agent/learned-search/

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "open_commerce.worker.main"]
