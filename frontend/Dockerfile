# =============================================================================
# Stage 1: Build React/Vite Frontend
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app/desktop

# Install packages
COPY desktop/package*.json ./
RUN npm ci

# Copy sources and build the static site
COPY desktop/ ./
RUN npm run build

# =============================================================================
# Stage 2: Serve via Nginx Alpine
# =============================================================================
FROM nginx:stable-alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy build artifacts from builder stage
COPY --from=builder /app/frontend /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

