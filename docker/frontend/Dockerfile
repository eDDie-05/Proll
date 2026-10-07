# Builds the React app, then copies the static bundle into the shared volume served by nginx.
FROM node:24-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM alpine:3.20
COPY --from=build /app/dist /dist
# Replace the published bundle atomically-ish on each deploy, then exit.
CMD ["sh", "-c", "rm -rf /srv/frontend/* && cp -r /dist/. /srv/frontend/ && echo 'Frontend published.'"]
