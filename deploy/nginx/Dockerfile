FROM node:22-alpine AS user-build
WORKDIR /src
COPY user_frontend/package.json user_frontend/package-lock.json ./
RUN npm ci
COPY user_frontend/ ./
RUN npm run build

FROM node:22-alpine AS admin-build
WORKDIR /src
COPY admin_frontend/package.json admin_frontend/package-lock.json ./
RUN npm ci
COPY admin_frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=user-build /src/dist/ /usr/share/nginx/html/
COPY --from=admin-build /src/dist/ /usr/share/nginx/html/admin/
EXPOSE 80 443
