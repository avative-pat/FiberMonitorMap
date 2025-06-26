# Build stage
FROM node:18-alpine as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy all source files (this will include public directory)
COPY . .

# Verify files are copied and show directory structure
RUN echo "=== Checking files ===" && \
    ls -la && \
    echo "=== Checking if public directory exists ===" && \
    if [ -d "public" ]; then \
        echo "public directory found:" && \
        ls -la public/ && \
        echo "=== Checking index.html ===" && \
        cat public/index.html; \
    else \
        echo "public directory not found, creating it" && \
        mkdir -p public && \
        echo '<!DOCTYPE html><html><head><title>Fiber Monitor</title></head><body><div id="root"></div></body></html>' > public/index.html; \
    fi

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