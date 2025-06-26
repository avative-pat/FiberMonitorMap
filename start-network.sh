#!/bin/bash

# Fiber Monitor Network Startup Script
# This script starts the backend and frontend for local network access

echo "🚀 Starting Fiber Monitor for Network Access..."
echo ""

# Function to get local IP address
get_local_ip() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - try multiple methods
        local_ip=$(ipconfig getifaddr en0 2>/dev/null)
        if [ -z "$local_ip" ]; then
            local_ip=$(ipconfig getifaddr en1 2>/dev/null)
        fi
        if [ -z "$local_ip" ]; then
            local_ip=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
        fi
        if [ -z "$local_ip" ]; then
            local_ip="127.0.0.1"
        fi
        echo "$local_ip"
    else
        # Linux
        hostname -I | awk '{print $1}' 2>/dev/null || echo "127.0.0.1"
    fi
}

LOCAL_IP=$(get_local_ip)

echo "📡 Network Information:"
echo "   Your local IP: $LOCAL_IP"
echo "   Backend will be available at: http://$LOCAL_IP:8000"
echo "   Frontend will be available at: http://$LOCAL_IP:3000"
echo ""

# Check if Redis is running
echo "🔍 Checking Redis..."
if ! redis-cli ping >/dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   brew services start redis"
    echo "   or"
    echo "   redis-server"
    echo ""
    exit 1
else
    echo "✅ Redis is running"
fi

echo ""
echo "🌐 Starting Backend..."
echo "   Backend will be accessible from any device on your network"
echo "   API Documentation: http://$LOCAL_IP:8000/docs"
echo ""

# Start backend in background
cd backend
source venv/bin/activate
python main.py &
BACKEND_PID=$!
cd ..

echo "✅ Backend started (PID: $BACKEND_PID)"
echo ""

# Wait a moment for backend to start
sleep 3

# Check if backend is running
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "✅ Backend is responding"
else
    echo "❌ Backend failed to start properly"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "🌐 Starting Frontend..."
echo "   Frontend will be accessible from any device on your network"
echo "   Set REACT_APP_API_URL=http://$LOCAL_IP:8000 to connect to backend"
echo ""

# Set environment variable for frontend
export REACT_APP_API_URL="http://$LOCAL_IP:8000"

# Start frontend
cd frontend
npm start &
FRONTEND_PID=$!
cd ..

echo "✅ Frontend started (PID: $FRONTEND_PID)"
echo ""

# Wait a moment for frontend to start
sleep 5

echo "🎉 Fiber Monitor is now running!"
echo ""
echo "📱 Access from other devices on your network:"
echo "   Frontend: http://$LOCAL_IP:3000"
echo "   Backend API: http://$LOCAL_IP:8000"
echo "   API Docs: http://$LOCAL_IP:8000/docs"
echo "   Health Check: http://$LOCAL_IP:8000/health"
echo ""
echo "🛑 To stop both services, press Ctrl+C"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo "✅ Services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Keep script running
wait 