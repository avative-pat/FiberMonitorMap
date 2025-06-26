# Fiber Network Monitoring System

A real-time, map-based visualization system for monitoring Calix AXOS fiber network alarms. Integrates with Calix SMx and Sonar to provide comprehensive network monitoring with interactive mapping and alerting.

## Features

- **Real-time Alarm Monitoring**: Polls Calix SMx every 90 seconds for active alarms
- **Interactive Map Visualization**: Mapbox-based map with color-coded alarm markers
- **Advanced Sonar Integration**: Three-query GraphQL approach for comprehensive data enrichment
- **Customer Data Enrichment**: Associates alarms with customer accounts, addresses, and service information
- **Rules Engine**: Automatically detects incidents (fiber cuts, power outages, etc.)
- **Responsive Web Interface**: Works on desktop and mobile devices
- **Filtering & Search**: Filter alarms by PON port, acknowledgment status, and age
- **Alert System**: Real-time alerts for network incidents

## Architecture

- **Backend**: Python FastAPI with Redis storage
- **Frontend**: React with Mapbox GL JS
- **Deployment**: Docker containers for easy setup
- **Data Store**: Redis for alarm and alert storage
- **Data Enrichment**: Multi-query Sonar GraphQL integration

## Quick Start

### Development Environment

1. **Clone the repository**
   ```bash
   git clone https://github.com/avative-pat/FiberMonitorMap.git
   cd FiberMonitorMap
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start the application**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - Health Check: http://localhost:8000/health

### Production Deployment

#### Prerequisites

- Docker and Docker Compose installed on your server
- At least 2GB RAM and 1 CPU core available
- Network access to Calix SMx and Sonar APIs
- Mapbox access token

#### Step-by-Step Production Deployment

1. **Prepare your server**
   ```bash
   # Update system packages
   sudo apt update && sudo apt upgrade -y
   
   # Install Docker (if not already installed)
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   
   # Install Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

2. **Clone and configure the application**
   ```bash
   git clone https://github.com/avative-pat/FiberMonitorMap.git
   cd FiberMonitorMap
   
   # Copy and configure environment variables
   cp .env.example .env
   nano .env  # Edit with your production settings
   ```

3. **Deploy using the automated script**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

4. **Alternative: Manual deployment**
   ```bash
   # Build and start services
   docker-compose -f docker-compose.prod.yml up -d --build
   
   # Check service status
   docker-compose -f docker-compose.prod.yml ps
   
   # View logs
   docker-compose -f docker-compose.prod.yml logs -f
   ```

#### Production Configuration

**Environment Variables (.env file)**
```bash
# Calix SMx Configuration
CALIX_SMX_HOST=your-smx-host
CALIX_SMX_USERNAME=your-username
CALIX_SMX_PASSWORD=your-password

# Sonar GraphQL Configuration
SONAR_GRAPHQL_URL=https://your-sonar-instance.com/api/graphql
SONAR_API_TOKEN=your-sonar-token

# Mapbox Configuration
MAPBOX_ACCESS_TOKEN=your-mapbox-token

# Redis Configuration
REDIS_URL=redis://redis:6379

# Application Settings
LOG_LEVEL=INFO
ENVIRONMENT=production
```

#### SSL/HTTPS Setup (Optional)

1. **Generate SSL certificates**
   ```bash
   mkdir -p ssl
   # Add your SSL certificates to the ssl/ directory
   # cert.pem and key.pem
   ```

2. **Update nginx.conf**
   - Uncomment the HTTPS server block
   - Update server_name with your domain
   - Ensure SSL certificate paths are correct

3. **Start with nginx reverse proxy**
   ```bash
   docker-compose --profile production up -d
   ```

#### Monitoring and Maintenance

**View application logs**
```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
```

**Update the application**
```bash
# Pull latest changes
git pull origin main

# Redeploy
./deploy.sh
```

**Backup Redis data**
```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec redis redis-cli BGSAVE

# Copy backup file
docker cp fiber-monitor-redis-prod:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb
```

**Resource monitoring**
```bash
# Check container resource usage
docker stats

# Check disk usage
docker system df
```

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `CALIX_SMX_HOST` | Calix SMx host URL | Yes | - |
| `CALIX_SMX_USERNAME` | Calix SMx username | Yes | - |
| `CALIX_SMX_PASSWORD` | Calix SMx password | Yes | - |
| `SONAR_GRAPHQL_URL` | Sonar GraphQL API URL | Yes | - |
| `SONAR_API_TOKEN` | Sonar API authentication token | Yes | - |
| `MAPBOX_ACCESS_TOKEN` | Mapbox access token for maps | Yes | - |
| `REDIS_URL` | Redis connection URL | No | `redis://redis:6379` |
| `LOG_LEVEL` | Application log level | No | `INFO` |
| `ENVIRONMENT` | Environment (development/production) | No | `development` |

### Docker Configuration

The application includes multiple Docker configurations:

- **`docker-compose.yml`**: Development setup with volume mounts
- **`docker-compose.prod.yml`**: Production setup with resource limits
- **`nginx.conf`**: Reverse proxy configuration for production

## API Endpoints

- `GET /alarms` - Get all active alarms with enriched customer and location data
- `GET /alerts` - Get current system alerts
- `GET /status` - Get polling status
- `POST /poll` - Manually trigger alarm poll
- `GET /health` - Health check endpoint

## Data Enrichment Process

The system enriches raw SMx alarm data with comprehensive customer and location information through a sophisticated three-query Sonar GraphQL approach:

### 1. Inventory Item Query
Retrieves basic inventory information including device model, manufacturer, and associated entities.

### 2. Address Details Query
When an inventory item is associated with an address, retrieves detailed location information including coordinates and customer association.

### 3. Customer Account Query
When an address has an associated customer account, retrieves customer details including name, account type, and status.

### Enriched Data Fields
- **Location**: Latitude, longitude, full address, address components
- **Customer**: Account ID, name, type (Residential/Business), status
- **Device**: Model name, manufacturer, inventory status, overall status
- **Service**: Service name and associated account service information

## Sonar GraphQL Integration

The system uses a sophisticated three-query approach to maximize data enrichment:

### Query 1: Inventory Item Details
```graphql
query GetInventoryItemDetails($itemId: Int64Bit!) {
  inventory_items(id: $itemId) {
    entities {
      id
      latitude
      longitude
      account_service_id
      account_service {
        id
        name_override
        account {
          id
          name
          account_type { name }
          account_status { name }
        }
        service {
          id
          name
        }
      }
      inventory_model {
        model_name
        manufacturer { name }
      }
      inventoryitemable {
        id
        __typename
      }
      status
      overall_status
    }
  }
}
```

### Query 2: Address Details (when applicable)
```graphql
query GetAddressDetails($addressId: Int64Bit!) {
  addresses(id: $addressId) {
    entities {
      id
      line1
      line2
      city
      subdivision
      zip
      latitude
      longitude
      addressable {
        id
        __typename
      }
    }
  }
}
```

### Query 3: Customer Details (when applicable)
```graphql
query GetCustomerDetails($accountId: Int64Bit!) {
  accounts(id: $accountId) {
    entities {
      id
      name
      account_type { name }
      account_status { name }
    }
  }
}
```

## Data Flow

1. **Alarm Polling**: System polls Calix SMx for raw alarm data
2. **ONT Identification**: Identifies ONTs with `sonar_item_` prefix
3. **Inventory Lookup**: Queries Sonar for inventory item details
4. **Address Enrichment**: If inventory item is associated with an address, retrieves address details
5. **Customer Enrichment**: If address has associated customer account, retrieves customer details
6. **Data Merging**: Combines all available data with proper priority handling
7. **Redis Storage**: Stores enriched alarms in Redis for fast access
8. **API Delivery**: Provides enriched data through REST API endpoints

## Troubleshooting

### Common Issues

**Application won't start**
```bash
# Check Docker logs
docker-compose logs

# Verify environment variables
docker-compose config
```

**Redis connection issues**
```bash
# Check Redis container
docker-compose exec redis redis-cli ping

# Check Redis logs
docker-compose logs redis
```

**API connectivity issues**
```bash
# Test backend health
curl http://localhost:8000/health

# Check backend logs
docker-compose logs backend
```

**Frontend not loading**
```bash
# Check frontend logs
docker-compose logs frontend

# Verify API URL configuration
docker-compose exec frontend env | grep REACT_APP_API_URL
```

### Performance Optimization

- **Memory**: Ensure at least 2GB RAM available
- **CPU**: Allocate at least 1 CPU core
- **Storage**: Use SSD storage for Redis data
- **Network**: Ensure stable network connectivity to APIs

## Development

### Local Development Setup

1. **Clone and setup**
   ```bash
   git clone https://github.com/avative-pat/FiberMonitorMap.git
   cd FiberMonitorMap
   cp .env.example .env
   ```

2. **Start development environment**
   ```bash
   docker-compose up -d
   ```

3. **Make changes and rebuild**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Recent Improvements

- **Enhanced Sonar Integration**: Implemented three-query GraphQL approach for comprehensive data enrichment
- **Customer Data Association**: Added ability to link alarms with customer accounts and service information
- **Improved Location Accuracy**: Better coordinate handling with fallback logic
- **Address Component Access**: Individual address fields for detailed location information
- **Account Type Classification**: Customer type identification (Residential/Business)
- **Robust Error Handling**: Graceful handling of missing or null data
- **Code Cleanup**: Removed unused fields and improved data model consistency
- **Production Deployment**: Added comprehensive Docker production setup with nginx reverse proxy
- **Automated Deployment**: Created deployment script for easy server setup 