#!/bin/bash

# FiberMonitorMap Production Deployment Script
# This script sets up the FiberMonitorMap application on a production server

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="fiber-monitor"
DOCKER_COMPOSE_FILE="docker-compose.yml"
ENV_FILE=".env"

echo -e "${GREEN}🚀 Starting FiberMonitorMap Production Deployment${NC}"

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}❌ This script should not be run as root${NC}"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker and Docker Compose are installed${NC}"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Please edit .env file with your production settings before continuing${NC}"
        echo -e "${YELLOW}⚠️  Press Enter when you're ready to continue...${NC}"
        read -r
    else
        echo -e "${RED}❌ .env.example file not found. Please create a .env file manually.${NC}"
        exit 1
    fi
fi

# Create SSL directory if using nginx
if [ -f "nginx.conf" ]; then
    mkdir -p ssl
    echo -e "${YELLOW}⚠️  SSL directory created. Add your SSL certificates to the ssl/ directory if using HTTPS${NC}"
fi

# Stop existing containers if running
echo -e "${GREEN}🛑 Stopping existing containers...${NC}"
docker-compose down --remove-orphans || true

# Pull latest images
echo -e "${GREEN}📥 Pulling latest images...${NC}"
docker-compose pull

# Build images
echo -e "${GREEN}🔨 Building application images...${NC}"
docker-compose build --no-cache

# Start services
echo -e "${GREEN}🚀 Starting services...${NC}"
docker-compose up -d

# Wait for services to be healthy
echo -e "${GREEN}⏳ Waiting for services to be healthy...${NC}"
sleep 30

# Check service health
echo -e "${GREEN}🔍 Checking service health...${NC}"

# Check Redis
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✅ Redis is healthy${NC}"
else
    echo -e "${RED}❌ Redis is not responding${NC}"
    exit 1
fi

# Check Backend
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend API is healthy${NC}"
else
    echo -e "${RED}❌ Backend API is not responding${NC}"
    exit 1
fi

# Check Frontend
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend is healthy${NC}"
else
    echo -e "${RED}❌ Frontend is not responding${NC}"
    exit 1
fi

# Show running containers
echo -e "${GREEN}📊 Running containers:${NC}"
docker-compose ps

# Show logs
echo -e "${GREEN}📋 Recent logs:${NC}"
docker-compose logs --tail=20

echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${GREEN}🌐 Application URLs:${NC}"
echo -e "   Frontend: http://localhost:3000"
echo -e "   Backend API: http://localhost:8000"
echo -e "   Health Check: http://localhost:8000/health"

# Optional: Start with nginx reverse proxy
if [ -f "nginx.conf" ]; then
    echo -e "${YELLOW}💡 To use nginx reverse proxy, run:${NC}"
    echo -e "   docker-compose --profile production up -d"
    echo -e "   Then access via: http://localhost"
fi

echo -e "${GREEN}📝 Useful commands:${NC}"
echo -e "   View logs: docker-compose logs -f"
echo -e "   Stop services: docker-compose down"
echo -e "   Restart services: docker-compose restart"
echo -e "   Update application: ./deploy.sh" 