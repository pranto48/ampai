# =============================================================================
# Stage 1: Build React/Vite Frontend
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source files and build
COPY . .
RUN npm run build

# =============================================================================
# Stage 2: Serve static files via Nginx
# =============================================================================
FROM nginx:stable-alpine

# Copy custom nginx config if present (optional)
#COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
