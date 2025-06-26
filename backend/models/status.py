from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class StatusResponse(BaseModel):
    """Response model for status API endpoint"""
    last_polled_at: Optional[str] = None
    is_polling: bool = False
    total_alarms: int = 0
    uptime: Optional[str] = None
    version: str = "1.0.0" 