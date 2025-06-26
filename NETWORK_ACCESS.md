# Network Access Setup

This guide explains how to run the Fiber Monitor system so it can be accessed from other devices on your local network.

## Quick Start

1. **Make sure Redis is running:**
   ```bash
   brew services start redis
   ```

2. **Run the network startup script:**
   ```bash
   ./start-network.sh
   ```

This script will:
- Start the backend on all network interfaces (0.0.0.0:8000)
- Start the frontend with the correct API URL
- Display your local IP address for network access
- Show URLs for accessing from other devices

## Manual Setup

If you prefer to start services manually:

### Backend Setup

1. **Start the backend:**
   ```bash
   cd backend
   source venv/bin/activate
   python main.py
   ```

The backend will:
- Bind to all network interfaces (0.0.0.0:8000)
- Enable CORS for development (allows all origins)
- Display your local IP address in the startup logs

### Frontend Setup

1. **Set the API URL to your local IP:**
   ```bash
   export REACT_APP_API_URL=http://YOUR_LOCAL_IP:8000
   ```

2. **Start the frontend:**
   ```bash
   cd frontend
   npm start
   ```

## Accessing from Other Devices

Once running, you can access the system from any device on your local network:

- **Frontend:** `http://YOUR_LOCAL_IP:3000`
- **Backend API:** `http://YOUR_LOCAL_IP:8000`
- **API Documentation:** `http://YOUR_LOCAL_IP:8000/docs`
- **Health Check:** `http://YOUR_LOCAL_IP:8000/health`

## Finding Your Local IP

### macOS
```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

### Linux
```bash
hostname -I
```

### Windows
```bash
ipconfig | findstr "IPv4"
```

## Troubleshooting

### Backend not accessible from network
- Check if firewall is blocking port 8000
- Ensure backend is binding to 0.0.0.0 (not just localhost)
- Check backend logs for any errors

### Frontend can't connect to backend
- Verify REACT_APP_API_URL is set to the correct IP
- Check that backend is running and accessible
- Ensure CORS is properly configured

### Redis connection issues
- Make sure Redis is running: `redis-cli ping`
- Check Redis configuration in backend
- Verify Redis is accessible from the network if needed

## Security Notes

⚠️ **Important:** This configuration is for development only!

- CORS is set to allow all origins (`*`)
- Backend binds to all network interfaces
- No authentication is required

For production deployment:
- Configure specific CORS origins
- Use proper authentication
- Consider using a reverse proxy
- Restrict network access as needed 