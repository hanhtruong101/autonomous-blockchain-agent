FROM node:22-alpine
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --ignore-scripts
COPY apps/web apps/web
COPY packages packages
CMD ["npm", "run", "web:dev"]
