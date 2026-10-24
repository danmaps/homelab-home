FROM node:24.22.1-alpine

RUN apk add --no-cache --upgrade docker-cli ca-certificates

WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .

ENV PORT=3499
ENV HOST=0.0.0.0
EXPOSE 3499

CMD ["node", "server.js"]
