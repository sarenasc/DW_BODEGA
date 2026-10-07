# Frontend WMS: compila el sitio estatico y lo sirve con nginx, que ademas reenvia /api al backend.
FROM node:22-alpine AS compilacion
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=compilacion /src/out /usr/share/nginx/html
EXPOSE 80
