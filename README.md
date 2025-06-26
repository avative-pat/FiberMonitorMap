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

## Quick Start

1. Clone the repository
2. Copy `.env.example` to `.env` and configure your settings
3. Run `docker-compose up -d`
4. Access the application at `http://localhost:3000`

## Configuration

See `.env.example` for all available configuration options including:
- Calix SMx API credentials
- Sonar GraphQL API settings
- Mapbox access token
- Redis configuration
- Polling intervals

## API Endpoints

- `GET /alarms` - Get all active alarms with enriched customer and location data
- `GET /alerts` - Get current system alerts
- `GET /status` - Get polling status
- `POST /poll` - Manually trigger alarm poll

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

## Development

See `CONTRIBUTING.md` for development setup and guidelines.

## Recent Improvements

- **Enhanced Sonar Integration**: Implemented three-query GraphQL approach for comprehensive data enrichment
- **Customer Data Association**: Added ability to link alarms with customer accounts and service information
- **Improved Location Accuracy**: Better coordinate handling with fallback logic
- **Address Component Access**: Individual address fields for detailed location information
- **Account Type Classification**: Customer type identification (Residential/Business)
- **Robust Error Handling**: Graceful handling of missing or null data
- **Code Cleanup**: Removed unused fields and improved data model consistency 