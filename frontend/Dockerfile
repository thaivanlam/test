# --- Build stage: produces the static bundle in /app/dist ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
# npm ci installs exactly what package-lock.json records, rather than
# re-resolving ranges as npm install may.
RUN npm ci
COPY . .
RUN npm run build

# --- Runtime stage: static files only ---
# The bundle is plain HTML, CSS and JavaScript, so the runtime needs a web
# server, not Node. nginx:alpine replaces node:20-alpine plus a global
# `serve` install.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 3000
