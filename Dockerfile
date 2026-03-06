FROM node:20-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

ENV PORT=3499
ENV HOST=0.0.0.0
EXPOSE 3499

CMD ["node", "server.js"]
