FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:alpine@sha256:fed7e14be83cbd2661a75cdc5b872d936cf155d46c327084d30b8df19ae88d72

COPY --from=build /app/dist /usr/share/nginx/html
# nginx image envsubst's templates into conf.d at container start
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV GATEWAY_HOST=gateway

EXPOSE 3000
