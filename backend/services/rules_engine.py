import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import defaultdict
import redis.asyncio as redis

from models.alert import Alert, AlertResponse, AlertType, AlertSeverity
from models.alarm import EnrichedAlarm

logger = logging.getLogger(__name__)

class RulesEngine:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        
        # Define rules
        self.rules = [
            self._fiber_cut_rule,
            self._power_outage_rule,
            self._ethernet_issue_rule,
            self._ont_missing_rule
        ]
    
    async def analyze_alarms(self, alarms: List[EnrichedAlarm]) -> List[Alert]:
        """Analyze alarms and generate alerts based on rules"""
        try:
            alerts = []
            
            for rule in self.rules:
                rule_alerts = await rule(alarms)
                alerts.extend(rule_alerts)
            
            # Store alerts in Redis
            await self._store_alerts(alerts)
            
            logger.info(f"Generated {len(alerts)} alerts from rules analysis")
            return alerts
            
        except Exception as e:
            logger.error(f"Error in rules analysis: {e}")
            return []
    
    async def _fiber_cut_rule(self, alarms: List[EnrichedAlarm]) -> List[Alert]:
        """Detect potential fiber cuts (4+ ont-missing alarms on same PON port)"""
        alerts = []
        
        # Group alarms by PON port
        pon_alarms = defaultdict(list)
        for alarm in alarms:
            if alarm.pon_port and alarm.condition_type == "ont-missing":
                pon_alarms[alarm.pon_port].append(alarm)
        
        # Check for fiber cut conditions
        for pon_port, pon_alarm_list in pon_alarms.items():
            if len(pon_alarm_list) >= 4:
                # Check if alarms are recent (within last 30 minutes)
                recent_alarms = [
                    alarm for alarm in pon_alarm_list
                    if self._is_recent_alarm(alarm, minutes=30)
                ]
                
                if len(recent_alarms) >= 4:
                    alert = Alert(
                        id=f"fiber_cut_{pon_port}_{datetime.utcnow().timestamp()}",
                        type=AlertType.FIBER_CUT,
                        severity=AlertSeverity.CRITICAL,
                        message=f"🚨 {len(recent_alarms)} ONTs missing on PON {pon_port}. Possible fiber cut.",
                        pon_port=pon_port,
                        affected_onts=[alarm.ont_id for alarm in recent_alarms],
                        created_at=datetime.utcnow(),
                        is_active=True
                    )
                    alerts.append(alert)
        
        return alerts
    
    async def _power_outage_rule(self, alarms: List[EnrichedAlarm]) -> List[Alert]:
        """Detect potential power outages (6+ ont-dying-gasp alarms in same region within 10 minutes)"""
        alerts = []
        
        # Group alarms by region
        region_alarms = defaultdict(list)
        for alarm in alarms:
            if alarm.region and alarm.condition_type == "ont-dying-gasp":
                region_alarms[alarm.region].append(alarm)
        
        # Check for power outage conditions
        for region, region_alarm_list in region_alarms.items():
            if len(region_alarm_list) >= 6:
                # Check if alarms are very recent (within last 10 minutes)
                recent_alarms = [
                    alarm for alarm in region_alarm_list
                    if self._is_recent_alarm(alarm, minutes=10)
                ]
                
                if len(recent_alarms) >= 6:
                    # Extract region name from full path
                    region_name = region.split("/")[-1] if "/" in region else region
                    
                    alert = Alert(
                        id=f"power_outage_{region}_{datetime.utcnow().timestamp()}",
                        type=AlertType.POWER_OUTAGE,
                        severity=AlertSeverity.HIGH,
                        message=f"⚡ Power outage suspected in {region_name}. {len(recent_alarms)} ONTs reported dying gasp.",
                        region=region,
                        affected_onts=[alarm.ont_id for alarm in recent_alarms],
                        created_at=datetime.utcnow(),
                        is_active=True
                    )
                    alerts.append(alert)
        
        return alerts
    
    async def _ethernet_issue_rule(self, alarms: List[EnrichedAlarm]) -> List[Alert]:
        """Detect Ethernet issues (3+ ont-eth-down alarms in same region)"""
        alerts = []
        
        # Group alarms by region
        region_alarms = defaultdict(list)
        for alarm in alarms:
            if alarm.region and alarm.condition_type == "ont-eth-down":
                region_alarms[alarm.region].append(alarm)
        
        # Check for Ethernet issue conditions
        for region, region_alarm_list in region_alarms.items():
            if len(region_alarm_list) >= 3:
                # Extract region name from full path
                region_name = region.split("/")[-1] if "/" in region else region
                
                alert = Alert(
                    id=f"ethernet_issue_{region}_{datetime.utcnow().timestamp()}",
                    type=AlertType.ETHERNET_ISSUE,
                    severity=AlertSeverity.MEDIUM,
                    message=f"⚠ Ethernet loss detected in {region_name}. {len(region_alarm_list)} ONTs affected.",
                    region=region,
                    affected_onts=[alarm.ont_id for alarm in region_alarm_list],
                    created_at=datetime.utcnow(),
                    is_active=True
                )
                alerts.append(alert)
        
        return alerts
    
    async def _ont_missing_rule(self, alarms: List[EnrichedAlarm]) -> List[Alert]:
        """Detect general ONT missing patterns (high count in short time)"""
        alerts = []
        
        # Count recent ont-missing alarms
        recent_missing_alarms = [
            alarm for alarm in alarms
            if alarm.condition_type == "ont-missing" and self._is_recent_alarm(alarm, minutes=60)
        ]
        
        if len(recent_missing_alarms) >= 10:
            # Group by region for more specific alerts
            region_counts = defaultdict(int)
            for alarm in recent_missing_alarms:
                region_counts[alarm.region] += 1
            
            for region, count in region_counts.items():
                if count >= 5:  # At least 5 missing ONTs in a region
                    region_name = region.split("/")[-1] if "/" in region else region
                    
                    alert = Alert(
                        id=f"ont_missing_{region}_{datetime.utcnow().timestamp()}",
                        type=AlertType.ONT_MISSING,
                        severity=AlertSeverity.MEDIUM,
                        message=f"📡 Multiple ONTs missing in {region_name}. {count} ONTs affected.",
                        region=region,
                        affected_onts=[alarm.ont_id for alarm in recent_missing_alarms if alarm.region == region],
                        created_at=datetime.utcnow(),
                        is_active=True
                    )
                    alerts.append(alert)
        
        return alerts
    
    def _is_recent_alarm(self, alarm: EnrichedAlarm, minutes: int) -> bool:
        """Check if alarm is within the specified time window"""
        try:
            alarm_time = datetime.fromisoformat(alarm.receiveTimeString.replace('Z', '+00:00'))
            cutoff_time = datetime.utcnow().replace(tzinfo=alarm_time.tzinfo) - timedelta(minutes=minutes)
            return alarm_time >= cutoff_time
        except:
            return False
    
    async def _store_alerts(self, alerts: List[Alert]):
        """Store alerts in Redis"""
        try:
            # Convert alerts to JSON
            alerts_data = [alert.dict() for alert in alerts]
            
            # Store in Redis
            await self.redis_client.set(
                "alerts",
                json.dumps(alerts_data, default=str),
                ex=3600  # Expire after 1 hour
            )
            
        except Exception as e:
            logger.error(f"Error storing alerts in Redis: {e}")
    
    async def get_current_alerts(self) -> List[AlertResponse]:
        """Get current alerts from Redis"""
        try:
            alerts_data = await self.redis_client.get("alerts")
            if not alerts_data:
                return []
            
            alerts_json = json.loads(alerts_data)
            alerts = []
            
            for alert_data in alerts_json:
                # Convert string datetime back to datetime object
                if isinstance(alert_data.get("created_at"), str):
                    alert_data["created_at"] = datetime.fromisoformat(alert_data["created_at"])
                
                alert = Alert(**alert_data)
                alert_response = AlertResponse(
                    id=alert.id,
                    type=alert.type.value,
                    severity=alert.severity.value,
                    message=alert.message,
                    region=alert.region,
                    pon_port=alert.pon_port,
                    affected_onts=alert.affected_onts,
                    created_at=alert.created_at.isoformat(),
                    is_active=alert.is_active
                )
                alerts.append(alert_response)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error retrieving alerts from Redis: {e}")
            return []
    
    async def clear_alerts(self):
        """Clear all stored alerts"""
        try:
            await self.redis_client.delete("alerts")
            logger.info("Cleared all stored alerts")
        except Exception as e:
            logger.error(f"Error clearing alerts: {e}") 