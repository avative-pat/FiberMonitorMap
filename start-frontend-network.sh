#!/bin/bash

# Start Frontend for Network Access
echo "🌐 Starting Frontend for Network Access..."

# Get local IP address
LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)

if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="192.168.75.43"  # Fallback to your known IP
fi

echo "📡 Using API URL: http://$LOCAL_IP:8000"
echo "🌐 Frontend will be available at: http://$LOCAL_IP:3000"
echo ""

# Set environment variable and start frontend
cd frontend
REACT_APP_API_URL="http://$LOCAL_IP:8000" HOST=0.0.0.0 npm start 