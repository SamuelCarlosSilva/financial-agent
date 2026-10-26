# check=skip=SecretsUsedInArgOrEnv
# (o ENV FINAGENT_API_KEY abaixo é só um padrão vazio para o envsubst; a chave real vem do
# ambiente do container, nunca da imagem)
# Build do bundle estático
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Nginx sem root servindo dist/ e fazendo o proxy de /api (contracts/proxy.md)
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
ENV API_UPSTREAM=http://api:8000 \
    FINAGENT_API_KEY=
EXPOSE 8080
