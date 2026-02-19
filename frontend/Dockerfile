FROM node:18-alpine
WORKDIR /app
COPY package.json .
COPY src ./src
RUN npm install --silent || true
EXPOSE 3000
CMD ["node", "server.js"]
