FROM node:24.19.0-alpine3.24 AS deps
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:24.19.0-alpine3.24 AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false
COPY . .
# Restore only the exact dependency set installed from package-lock.json;
# guard against host node_modules leaking into the image.
COPY --from=deps /app/node_modules ./node_modules
RUN node -e 'const pinned = require("./package.json").dependencies.next; const next = require("next/package.json").version; const swc = require("@next/swc-linux-" + process.arch + "-musl/package.json").version; if (pinned !== next || pinned !== swc) { throw new Error("Next.js/SWC must match package.json (" + [pinned, next, swc].join(", ") + ")"); }'
RUN mkdir -p .next/cache && npm run build

FROM node:24.19.0-alpine3.24 AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false
# The standalone runtime only needs node. Remove npm/npx and their bundled package
# tree from the final image to reduce attack surface and avoid shipping build tooling.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx && \
    addgroup -S nextjs && adduser -S nextjs -G nextjs
COPY --from=build /app/public ./public
COPY --from=build --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
