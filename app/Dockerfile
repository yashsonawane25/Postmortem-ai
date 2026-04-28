FROM node:20-alpine

WORKDIR /app

COPY package.json .
COPY index.js .

# Non-root user for best practices
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 3000

CMD ["node", "index.js"]
