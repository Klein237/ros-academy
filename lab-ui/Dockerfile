# Construit le Lab UI puis le sert avec Caddy : aucun Node sur le serveur.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM caddy:2.8
COPY --from=build /app/dist /srv/lab-ui
