# Development stage
# Using Node.js 22 LTS (Vite 7.2.6 requires Node.js 20.19+ or 22.12+)
FROM node:22-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 3000

# Set environment variables for development (can be overridden by docker-compose)
ENV VITE_API_URL=
ENV VITE_APP_API_URL=

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"] 