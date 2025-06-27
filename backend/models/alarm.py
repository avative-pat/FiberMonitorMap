from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class Alarm(BaseModel):
    """Raw alarm data from Calix SMx"""
    # Core alarm fields
    deviceTime: int
    receiveTime: int
    severity: str
    alarmLevel: int
    standing: bool
    alarmReferForClear: str
    deviceType: str
    sourceType: Optional[str] = None
    category: str
    instanceId: str
    description: str
    probableCause: str
    details: Optional[str] = None
    deviceSequenceNumber: str
    alarm: bool
    port: Optional[str] = None
    location: Optional[str] = None
    address: str
    primaryElement: Optional[str] = None
    secondaryElement: Optional[str] = None
    serviceAffecting: str
    subscriber: Optional[str] = None
    userNotes: Optional[str] = None
    ackUser: Optional[str] = None
    sequenceNum: str
    resource: str
    ont_id: Optional[str] = None
    
    # Device-specific fields
    condition_type: Optional[str] = Field(None, alias="condition-type")
    device_name: Optional[str] = Field(None, alias="device-name")
    aid: Optional[str] = None
    shelf_id: Optional[str] = Field(None, alias="shelf-id")
    slot_id: Optional[str] = Field(None, alias="slot-id")
    port_id: Optional[str] = Field(None, alias="port-id")
    ont_type: Optional[str] = Field(None, alias="ont-type")
    ont_port_id: Optional[str] = Field(None, alias="ont-port-id")
    pon_system_id: Optional[str] = Field(None, alias="pon-system-id")
    admin_partition: Optional[str] = Field(None, alias="admin-partition")
    pon_id: Optional[str] = Field(None, alias="pon-id")
    equipment_type: Optional[str] = Field(None, alias="equipment-type")
    alarm_type: Optional[str] = Field(None, alias="alarm-type")
    switched_pon_id: Optional[str] = Field(None, alias="switched-pon-id")
    switched_channel_termination: Optional[str] = Field(None, alias="switched-channel-termination")
    pon_device: Optional[str] = Field(None, alias="pon-device")
    partition_id: Optional[str] = Field(None, alias="partition-id")
    switched_shelf: Optional[str] = Field(None, alias="switched-shelf")
    switched_slot: Optional[str] = Field(None, alias="switched-slot")
    switched_port: Optional[str] = Field(None, alias="switched-port")
    serial_number: Optional[str] = Field(None, alias="serial-number")

    class Config:
        allow_population_by_field_name = True

class EnrichedAlarm(BaseModel):
    """Alarm data enriched with location and account information"""
    # Original alarm fields
    deviceTime: int
    receiveTime: int
    severity: str
    alarmLevel: int
    standing: bool
    alarmReferForClear: str
    deviceType: str
    sourceType: Optional[str] = None
    category: str
    instanceId: str
    description: str
    probableCause: str
    details: Optional[str] = None
    deviceSequenceNumber: str
    alarm: bool
    port: Optional[str] = None
    location: Optional[str] = None
    address: str
    primaryElement: Optional[str] = None
    secondaryElement: Optional[str] = None
    serviceAffecting: str
    subscriber: Optional[str] = None
    userNotes: Optional[str] = None
    ackUser: Optional[str] = None
    sequenceNum: str
    resource: str
    ont_id: Optional[str] = None
    eventId: Optional[str] = None
    
    # Device-specific fields
    deviceId: Optional[str] = None
    device_name: Optional[str] = Field(None, alias="device-name")
    condition_type: Optional[str] = Field(None, alias="condition-type")
    alarm_type: Optional[str] = Field(None, alias="alarm-type")
    equipment_type: Optional[str] = Field(None, alias="equipment-type")
    shelf_id: Optional[str] = Field(None, alias="shelf-id")
    slot_id: Optional[str] = Field(None, alias="slot-id")
    port_id: Optional[str] = Field(None, alias="port-id")
    ont_type: Optional[str] = Field(None, alias="ont-type")
    ont_port_id: Optional[str] = Field(None, alias="ont-port-id")
    pon_system_id: Optional[str] = Field(None, alias="pon-system-id")
    admin_partition: Optional[str] = Field(None, alias="admin-partition")
    pon_port: Optional[str] = None
    aid: Optional[str] = None
    serial_number: Optional[str] = Field(None, alias="serial-number")
    
    # Acknowledgment fields
    acked: bool = False
    isAcked: bool = False
    
    # Timing fields
    receiveTimeString: Optional[str] = None
    deviceTimeString: Optional[str] = None
    
    # Enrichment tracking fields
    is_enriched: bool = False
    last_enrichment_time: Optional[str] = None
    enrichment_attempts: int = 0
    
    # Enriched fields from Sonar
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    full_address: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_city: Optional[str] = None
    address_subdivision: Optional[str] = None
    address_zip: Optional[str] = None
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    account_status: Optional[str] = None
    customer_type: Optional[str] = None
    service_name: Optional[str] = None
    inventory_model: Optional[str] = None
    manufacturer: Optional[str] = None
    inventory_status: Optional[str] = None
    overall_status: Optional[str] = None
    inventoryitemable_id: Optional[str] = None
    inventoryitemable_type: Optional[str] = None
    region: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

class AlarmResponse(BaseModel):
    """Response model for alarm API endpoints"""
    # Core alarm fields
    sequenceNum: str
    description: str
    severity: str
    serviceAffecting: str
    region: str
    deviceType: str
    category: str
    eventId: str
    deviceId: str
    device_name: Optional[str] = None
    condition_type: Optional[str] = None
    alarm_type: Optional[str] = None
    equipment_type: Optional[str] = None
    
    # ONT-specific fields
    ont_id: Optional[str] = None
    ont_type: Optional[str] = None
    serial_number: Optional[str] = None
    port: str
    pon_port: Optional[str] = None
    
    # Acknowledgment fields
    acked: bool
    ackUser: Optional[str] = None
    userNotes: Optional[str] = None
    isAcked: bool
    
    # Timing fields
    receiveTimeString: str
    deviceTimeString: str
    deviceTime: int
    receiveTime: int
    
    # Additional fields
    probableCause: str
    details: Optional[str] = None
    aid: Optional[str] = None
    resource: Optional[str] = None
    alarmLevel: int
    standing: bool
    
    # Enrichment tracking fields
    is_enriched: bool = False
    last_enrichment_time: Optional[str] = None
    enrichment_attempts: int = 0
    
    # Location data
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    full_address: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    address_city: Optional[str] = None
    address_subdivision: Optional[str] = None
    address_zip: Optional[str] = None
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    account_status: Optional[str] = None
    customer_type: Optional[str] = None
    service_name: Optional[str] = None
    inventory_model: Optional[str] = None
    manufacturer: Optional[str] = None
    inventory_status: Optional[str] = None
    overall_status: Optional[str] = None
    inventoryitemable_id: Optional[str] = None
    inventoryitemable_type: Optional[str] = None
    
    # Computed fields
    is_service_affecting: bool = Field(computed=True)
    alarm_age_hours: float = Field(computed=True)
    
    def __init__(self, **data):
        super().__init__(**data)
        self.is_service_affecting = self.serviceAffecting == "SA"
        self.alarm_age_hours = self._calculate_age_hours()
    
    def _calculate_age_hours(self) -> float:
        """Calculate alarm age in hours"""
        try:
            receive_time = datetime.fromisoformat(self.receiveTimeString.replace('Z', '+00:00'))
            now = datetime.utcnow().replace(tzinfo=receive_time.tzinfo)
            delta = now - receive_time
            return delta.total_seconds() / 3600
        except:
            return 0.0 