# Build stage
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy public directory first (explicitly)
COPY public/ ./public/

# Copy source files
COPY src/ ./src/

# Copy configuration files
COPY postcss.config.js tailwind.config.js ./

# Verify files are copied
RUN echo "=== Checking files ===" && \
    ls -la && \
    echo "=== Checking public directory ===" && \
    ls -la public/ && \
    echo "=== Checking index.html ===" && \
    cat public/index.html

# Build the app
RUN npm run build

# Production stage
FROM node:18-alpine

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

WORKDIR /app

# Install serve to run the built app
RUN npm install -g serve

# Copy built app from builder stage
COPY --from=builder --chown=nextjs:nodejs /app/build ./build

# Switch to non-root user
USER nextjs

# Expose port
EXPOSE 3000

# Start the app
CMD ["serve", "-s", "build", "-l", "3000"] 