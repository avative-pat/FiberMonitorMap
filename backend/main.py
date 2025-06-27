from dotenv import load_dotenv
import os
# Load .env file from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
print(f"[DEBUG] SMX_API_URL={os.getenv('SMX_API_URL')}")
print(f"[DEBUG] SMX_AUTH_HEADER={os.getenv('SMX_AUTH_HEADER')}")
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import redis.asyncio as redis

from services.alarm_service import AlarmService
from services.sonar_service import SonarService
from services.rules_engine import RulesEngine
from models.alarm import Alarm, AlarmResponse
from models.alert import Alert, AlertResponse
from models.status import StatusResponse

# Configure logging
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Fiber Network Monitoring System",
    description="Real-time monitoring system for Calix AXOS fiber network alarms",
    version="1.0.0",
    openapi_version="3.1.0"
)

# Add CORS middleware
# For development, allow all origins from local network
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001", 
    "http://127.0.0.1:3001",
    "http://192.168.75.43:3000",  # Your specific network IP
]

# Add any additional origins from environment variable
if os.getenv("CORS_ORIGINS"):
    cors_origins.extend(os.getenv("CORS_ORIGINS").split(","))

# For development, allow all origins (remove this in production)
if os.getenv("ENVIRONMENT", "development") == "development":
    cors_origins = ["*"]

print(f"🌐 CORS Origins configured: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
redis_client = None
alarm_service = None
sonar_service = None
rules_engine = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global redis_client, alarm_service, sonar_service, rules_engine
    
    try:
        # Initialize Redis connection
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        logger.info(f"Connecting to Redis at: {redis_url}")
        redis_client = redis.from_url(redis_url)
        
        # Test Redis connection
        await redis_client.ping()
        logger.info("✅ Redis connection successful")
        
        # Initialize services
        alarm_service = AlarmService(redis_client)
        sonar_service = SonarService()
        rules_engine = RulesEngine(redis_client)
        logger.info("✅ Services initialized successfully")
        
        # Start the alarm polling scheduler (but don't fail startup if it fails)
        try:
            await alarm_service.start_polling()
            logger.info("✅ Alarm polling started successfully")
        except Exception as e:
            logger.warning(f"⚠️ Failed to start alarm polling: {e}")
            logger.info("Application will start without alarm polling - it can be started manually later")
            
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        # Don't raise the exception - let the app start anyway
        # The health check will indicate if there are issues

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if alarm_service:
        await alarm_service.stop_polling()
    if redis_client:
        await redis_client.close()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        redis_status = "unknown"
        if redis_client:
            try:
                await redis_client.ping()
                redis_status = "healthy"
            except Exception as e:
                redis_status = f"unhealthy: {str(e)}"
        else:
            redis_status = "not_initialized"
        
        # Check alarm service status
        alarm_service_status = "unknown"
        if alarm_service:
            alarm_service_status = "healthy" if alarm_service.is_polling_active() else "not_polling"
        else:
            alarm_service_status = "not_initialized"
        
        return {
            "status": "healthy" if redis_status == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "redis": redis_status,
                "alarm_service": alarm_service_status
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/alarms", response_model=List[AlarmResponse])
async def get_alarms():
    """Get all currently active alarms"""
    if not alarm_service:
        raise HTTPException(status_code=503, detail="Alarm service not initialized")
    
    try:
        alarms = await alarm_service.get_all_alarms()
        return alarms
    except Exception as e:
        logger.error(f"Error fetching alarms: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alarms")

@app.get("/alerts", response_model=List[AlertResponse])
async def get_alerts():
    """Get current system alerts"""
    if not rules_engine:
        raise HTTPException(status_code=503, detail="Rules engine not initialized")
    
    try:
        alerts = await rules_engine.get_current_alerts()
        return alerts
    except Exception as e:
        logger.error(f"Error fetching alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alerts")

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get polling status and last poll time"""
    if not alarm_service:
        raise HTTPException(status_code=503, detail="Alarm service not initialized")
    
    try:
        last_poll = await alarm_service.get_last_poll_time()
        return StatusResponse(
            last_polled_at=last_poll,
            is_polling=alarm_service.is_polling_active(),
            total_alarms=await alarm_service.get_alarm_count()
        )
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch status")

@app.post("/poll")
async def manual_poll(background_tasks: BackgroundTasks):
    """Manually trigger alarm polling"""
    try:
        background_tasks.add_task(alarm_service.poll_alarms)
        return {"message": "Polling started", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Error starting manual poll: {e}")
        raise HTTPException(status_code=500, detail="Failed to start polling")

@app.post("/sync")
async def full_sync(background_tasks: BackgroundTasks):
    """Trigger a full backend sync: immediate SMx call and re-enrichment of all alarms"""
    if not alarm_service:
        raise HTTPException(status_code=503, detail="Alarm service not initialized")
    
    try:
        background_tasks.add_task(alarm_service.full_sync_alarms)
        return {
            "message": "Full sync started", 
            "timestamp": datetime.utcnow().isoformat(),
            "description": "Fetching fresh data from SMx and re-enriching all alarms"
        }
    except Exception as e:
        logger.error(f"Error starting full sync: {e}")
        raise HTTPException(status_code=500, detail="Failed to start full sync")

@app.get("/test-mock-alarms")
async def test_mock_alarms():
    """Test endpoint to get raw mock alarms without enrichment"""
    try:
        mock_alarms = alarm_service._get_mock_alarms()
        return {"alarms": mock_alarms, "count": len(mock_alarms)}
    except Exception as e:
        logger.error(f"Error getting mock alarms: {e}")
        raise HTTPException(status_code=500, detail="Failed to get mock alarms")

@app.get("/test-alarm-parsing")
async def test_alarm_parsing():
    """Test endpoint to check if mock alarms can be parsed correctly"""
    try:
        from models.alarm import Alarm, EnrichedAlarm
        
        mock_alarms = alarm_service._get_mock_alarms()
        parsed_alarms = []
        
        for i, raw_alarm in enumerate(mock_alarms):
            try:
                # Test parsing raw alarm
                alarm = Alarm(**raw_alarm)
                parsed_alarms.append({
                    "index": i,
                    "sequenceNum": alarm.sequenceNum,
                    "description": alarm.description,
                    "status": "parsed_successfully"
                })
            except Exception as e:
                parsed_alarms.append({
                    "index": i,
                    "sequenceNum": raw_alarm.get("sequenceNum", "unknown"),
                    "error": str(e),
                    "status": "parse_failed"
                })
        
        return {
            "total_mock_alarms": len(mock_alarms),
            "parsed_alarms": parsed_alarms,
            "successful_parses": len([a for a in parsed_alarms if a["status"] == "parsed_successfully"])
        }
    except Exception as e:
        logger.error(f"Error testing alarm parsing: {e}")
        raise HTTPException(status_code=500, detail="Failed to test alarm parsing")

if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Get local IP addresses for logging - more robust method
    def get_local_ip():
        try:
            # Try to connect to a remote address to get local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                # Doesn't actually connect, just gets local IP
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                # Fallback: try hostname resolution
                hostname = socket.gethostname()
                return socket.gethostbyname(hostname)
            except Exception:
                # Final fallback: return localhost
                return "127.0.0.1"
    
    local_ip = get_local_ip()
    
    print(f"🚀 Starting Fiber Monitor Backend...")
    print(f"📡 Server will be available at:")
    print(f"   Local: http://localhost:8000")
    print(f"   Network: http://{local_ip}:8000")
    print(f"   Health check: http://localhost:8000/health")
    print(f"🌐 CORS enabled for development (all origins allowed)")
    print(f"⏰ Polling interval: {os.getenv('POLL_INTERVAL', '90')} seconds")
    print(f"📊 API Documentation: http://localhost:8000/docs")
    print("-" * 50)
    
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Bind to all network interfaces
        port=8000,
        log_level="info",
        access_log=True
    ) 