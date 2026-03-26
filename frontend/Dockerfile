FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# In development mode:
CMD ["npm", "run", "dev"]
