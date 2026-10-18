FROM node:22-trixie-slim@sha256:7b8a0c89c54499bee567618f96578e1a12a800f062fbdbfd1fb6a443fa6f6284 AS build

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY infra/patches ./infra/patches
COPY apps/web/package.json ./apps/web/package.json
COPY packages/sdk-typescript/package.json ./packages/sdk-typescript/package.json

RUN pnpm install --frozen-lockfile

COPY apps/web ./apps/web
COPY packages/sdk-typescript ./packages/sdk-typescript
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md ./

RUN pnpm --filter @open-commerce/web build

COPY scripts/collect-web-notices.mjs ./scripts/collect-web-notices.mjs
COPY security/third-party/next-15.5.27 ./security/third-party/next-15.5.27
COPY security/third-party/sharp-libvips-1.3.4 ./security/third-party/sharp-libvips-1.3.4
COPY security/third-party/react-19.2.8 ./security/third-party/react-19.2.8
RUN node scripts/collect-web-notices.mjs /app/web-legal

FROM node:22-trixie-slim@sha256:7b8a0c89c54499bee567618f96578e1a12a800f062fbdbfd1fb6a443fa6f6284 AS runtime
LABEL org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Only Node is needed to execute the standalone server, not package managers.
RUN rm -rf /usr/local/lib/node_modules /opt/yarn* /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg
COPY infra/docker/harden-debian.sh /usr/local/sbin/harden-debian
COPY infra/docker/prune-runtime-acl.sh /usr/local/sbin/prune-runtime-acl
RUN sh /usr/local/sbin/harden-debian && rm /usr/local/sbin/harden-debian

COPY --from=build --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=node:node /app/apps/web/public ./apps/web/public
COPY --from=build /app/LICENSE /app/NOTICE /app/THIRD_PARTY_NOTICES.md /usr/share/doc/open-commerce-agent/
COPY --from=build /app/web-legal /usr/share/doc/open-commerce-agent/web/

USER node

EXPOSE 3000

CMD ["node", "apps/web/server.js"]
