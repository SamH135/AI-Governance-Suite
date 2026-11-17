FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
# nginx image envsubst's templates into conf.d at container start
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV GATEWAY_HOST=gateway

EXPOSE 3000
