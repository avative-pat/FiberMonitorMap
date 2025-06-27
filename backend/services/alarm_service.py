import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import httpx
import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import re

from models.alarm import Alarm, EnrichedAlarm, AlarmResponse
from services.sonar_service import SonarService

logger = logging.getLogger(__name__)

class AlarmService:
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        self.sonar_service = SonarService()
        self.scheduler = AsyncIOScheduler()
        self.is_polling = False
        
        # Configuration
        self.smx_url = os.getenv("SMX_API_URL")
        self.smx_username = os.getenv("SMX_USERNAME")
        self.smx_password = os.getenv("SMX_PASSWORD")
        self.smx_auth_header = os.getenv("SMX_AUTH_HEADER")
        self.poll_interval = int(os.getenv("POLL_INTERVAL", "90"))
        
        # Log configuration status
        logger.info(f"SMx URL configured: {bool(self.smx_url)}")
        logger.info(f"SMx auth header configured: {bool(self.smx_auth_header)}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        
        # HTTP client for SMx API
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            verify=False  # For self-signed certificates
        )
    
    async def start_polling(self):
        """Start the alarm polling scheduler"""
        if not self.is_polling:
            logger.info("Creating alarm polling job...")
            self.scheduler.add_job(
                self.poll_alarms,
                IntervalTrigger(seconds=self.poll_interval),
                id="alarm_polling",
                replace_existing=True
            )
            logger.info("Starting scheduler...")
            self.scheduler.start()
            self.is_polling = True
            logger.info(f"Started alarm polling every {self.poll_interval} seconds")
            
            # Trigger an immediate poll for testing
            logger.info("Triggering immediate alarm poll for testing...")
            await self.poll_alarms()
    
    async def stop_polling(self):
        """Stop the alarm polling scheduler"""
        if self.is_polling:
            self.scheduler.shutdown()
            self.is_polling = False
            logger.info("Stopped alarm polling")
    
    def is_polling_active(self) -> bool:
        """Check if polling is currently active"""
        return self.is_polling
    
    async def poll_alarms(self):
        """Poll Calix SMx for alarms and process them"""
        try:
            logger.info("=== STARTING ALARM POLL ===")
            
            # Fetch alarms from SMx
            logger.info("Step 1: Fetching alarms from SMx...")
            raw_alarms = await self._fetch_smx_alarms()
            logger.info(f"Step 1 COMPLETE: Fetched {len(raw_alarms)} raw alarms from SMx")
            
            if not raw_alarms:
                logger.warning("No alarms received from SMx - ending poll")
                return
            
            # Log raw alarm details for debugging
            for i, alarm in enumerate(raw_alarms[:3]):  # Log first 3 alarms
                logger.info(f"Raw alarm {i+1}: sequenceNum={alarm.get('sequenceNum', 'N/A')}, description={alarm.get('description', 'N/A')}")
            
            # Get existing alarms from Redis to check for duplicates and re-enrichment candidates
            logger.info("Step 2: Checking existing alarms in Redis...")
            existing_alarms = await self._get_existing_alarms()
            existing_sequence_nums = {alarm.sequenceNum for alarm in existing_alarms}
            logger.info(f"Step 2 COMPLETE: Found {len(existing_alarms)} existing alarms in Redis")
            
            # Separate new alarms, existing enriched alarms, and re-enrichment candidates
            new_alarms = []
            existing_enriched_alarms = []
            re_enrichment_candidates = []
            
            for raw_alarm in raw_alarms:
                sequence_num = raw_alarm.get('sequenceNum')
                if sequence_num in existing_sequence_nums:
                    # Alarm already exists - check if it needs re-enrichment
                    existing_alarm = next((a for a in existing_alarms if a.sequenceNum == sequence_num), None)
                    if existing_alarm:
                        if self._should_re_enrich_alarm(existing_alarm):
                            re_enrichment_candidates.append(raw_alarm)
                            logger.debug(f"Alarm {sequence_num} marked for re-enrichment (last enriched: {existing_alarm.last_enrichment_time})")
                        else:
                            existing_enriched_alarms.append(existing_alarm)
                            logger.debug(f"Alarm {sequence_num} already exists and doesn't need re-enrichment")
                else:
                    # New alarm - needs enrichment
                    new_alarms.append(raw_alarm)
                    logger.debug(f"Alarm {sequence_num} is new - will enrich with Sonar data")
            
            logger.info(f"Found {len(new_alarms)} new alarms, {len(existing_enriched_alarms)} existing enriched alarms, and {len(re_enrichment_candidates)} re-enrichment candidates")
            
            # Process and enrich new alarms and re-enrichment candidates
            enriched_new_alarms = []
            re_enriched_alarms = []
            
            if new_alarms:
                logger.info("Step 3a: Starting alarm enrichment for new alarms...")
                enriched_new_alarms = await self._enrich_alarms(new_alarms)
                logger.info(f"Step 3a COMPLETE: Enriched {len(enriched_new_alarms)} new alarms")
            else:
                logger.info("Step 3a SKIPPED: No new alarms to enrich")
            
            if re_enrichment_candidates:
                logger.info("Step 3b: Starting re-enrichment for existing alarms...")
                re_enriched_alarms = await self._re_enrich_alarms(re_enrichment_candidates)
                logger.info(f"Step 3b COMPLETE: Re-enriched {len(re_enriched_alarms)} alarms")
            else:
                logger.info("Step 3b SKIPPED: No alarms need re-enrichment")
            
            # Combine all alarms
            all_alarms = enriched_new_alarms + re_enriched_alarms + existing_enriched_alarms
            logger.info(f"Total alarms to store: {len(all_alarms)} ({len(enriched_new_alarms)} new + {len(re_enriched_alarms)} re-enriched + {len(existing_enriched_alarms)} existing)")
            
            if not all_alarms:
                logger.warning("No alarms to store - ending poll")
                return
            
            # Store in Redis
            logger.info("Step 4: Storing alarms in Redis...")
            await self._store_alarms(all_alarms)
            logger.info(f"Step 4 COMPLETE: Stored {len(all_alarms)} alarms in Redis")
            
            # Update last poll time
            logger.info("Step 5: Updating last poll time...")
            await self._update_last_poll_time()
            logger.info("Step 5 COMPLETE: Last poll time updated")
            
            logger.info(f"=== ALARM POLL COMPLETE: Successfully processed {len(all_alarms)} alarms ({len(enriched_new_alarms)} newly enriched, {len(re_enriched_alarms)} re-enriched) ===")
            
        except Exception as e:
            logger.error(f"=== ALARM POLL FAILED: {e} ===")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _fetch_smx_alarms(self) -> List[Dict[str, Any]]:
        """Fetch alarms from Calix SMx API"""
        # Check if SMx configuration is available
        if not self.smx_url or not self.smx_auth_header:
            logger.warning("SMx configuration missing - using mock data for development")
            return self._get_mock_alarms()
        
        try:
            logger.info(f"Fetching alarms from SMx API: {self.smx_url}")
            logger.info(f"Using auth header: {self.smx_auth_header[:20]}...")  # Log first 20 chars for security
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {self.smx_auth_header}"
            }
            
            # Try to get all alarms by adding pagination parameters
            # Common pagination parameters for APIs
            params = {
                "limit": 1000,  # Request a large limit to get all alarms
                "offset": 0,    # Start from the beginning
                "pageSize": 1000,  # Alternative parameter name
                "page": 1       # Alternative parameter name
            }
            
            logger.info(f"Making HTTP GET request with headers: {headers}")
            logger.info(f"Using query parameters: {params}")
            
            response = await self.http_client.get(self.smx_url, headers=headers, params=params)
            logger.info(f"Received response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            response.raise_for_status()
            
            alarms = response.json()
            logger.info(f"Response JSON type: {type(alarms)}")
            logger.info(f"Response JSON length: {len(alarms) if isinstance(alarms, list) else 'Not a list'}")
            
            if isinstance(alarms, list):
                logger.info(f"Successfully fetched {len(alarms)} alarms from SMx")
                return alarms
            else:
                logger.warning(f"Expected list but got {type(alarms)}: {alarms}")
                logger.info("Falling back to mock data due to unexpected response format")
                return self._get_mock_alarms()
                
        except Exception as e:
            logger.error(f"Error fetching alarms from SMx: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            logger.info("Falling back to mock data for development")
            return self._get_mock_alarms()
    
    async def _get_existing_alarms(self) -> List[EnrichedAlarm]:
        """Get existing enriched alarms from Redis"""
        try:
            logger.debug("Retrieving existing alarms from Redis...")
            alarm_keys = await self.redis_client.keys("alarms:*")
            
            if not alarm_keys:
                logger.debug("No existing alarms found in Redis")
                return []
            
            existing_alarms = []
            for key in alarm_keys:
                try:
                    alarm_data = await self.redis_client.get(key)
                    if alarm_data:
                        enriched_alarm = EnrichedAlarm.parse_raw(alarm_data)
                        existing_alarms.append(enriched_alarm)
                        logger.debug(f"Retrieved existing alarm: {enriched_alarm.sequenceNum}")
                except Exception as e:
                    logger.error(f"Error retrieving existing alarm from key {key}: {e}")
                    continue
            
            logger.debug(f"Successfully retrieved {len(existing_alarms)} existing alarms from Redis")
            return existing_alarms
            
        except Exception as e:
            logger.error(f"Error getting existing alarms: {e}")
            return []
    
    def _get_mock_alarms(self) -> List[Dict[str, Any]]:
        """Return mock alarm data for development"""
        logger.info("Generating mock alarm data for development")
        mock_alarms = [
            {
                "deviceTime": 1723180396000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-missing||7.122",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.122",
                "description": "Provisioned ONT is missing",
                "probableCause": "Provisioned ONT is not accessible on the PON.",
                "details": "SerialNo=BBF93A",
                "deviceSequenceNumber": "123",
                "alarm": True,
                "port": "sonar_item_5014",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_5014']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5020",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280960\"",
                "deviceTimeString": "2024-08-09T05:13:16",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-missing",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-sonar_item_5014",
                "shelf-id": None,
                "slot-id": None,
                "port-id": None,
                "sequenceNum": "969637107402280960",
                "ont-id": "sonar_item_5014",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "BBF93A",
                "resource": "ONT: sonar_item_5014"
            },
            {
                "deviceTime": 1723180396000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-missing||7.121",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.121",
                "description": "Provisioned ONT is missing",
                "probableCause": "Provisioned ONT is not accessible on the PON.",
                "details": "SerialNo=BBF634",
                "deviceSequenceNumber": "122",
                "alarm": True,
                "port": "sonar_item_5042",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_5042']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5020",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280961\"",
                "deviceTimeString": "2024-08-09T05:13:16",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-missing",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-sonar_item_5042",
                "shelf-id": None,
                "slot-id": None,
                "port-id": None,
                "sequenceNum": "969637107402280961",
                "ont-id": "sonar_item_5042",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "BBF634",
                "resource": "ONT: sonar_item_5042"
            },
            {
                "deviceTime": 1728248103000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-dying-gasp||7.3799",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.3799",
                "description": "ONT reported dying gasp",
                "probableCause": "ONT is out of service due to loss of power event detected by the ONT.",
                "details": "SerialNo=11E0018",
                "deviceSequenceNumber": "4687",
                "alarm": True,
                "port": "1/1/xp3",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_6933']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5029",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280962\"",
                "deviceTimeString": "2024-10-06T20:55:03",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-dying-gasp",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-1/1/xp3",
                "shelf-id": "1",
                "slot-id": "1",
                "port-id": "xp3",
                "sequenceNum": "969637107402280962",
                "ont-id": "sonar_item_6933",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "11E0018",
                "resource": "ONT: sonar_item_6933"
            },
            {
                "deviceTime": 1724687100000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-missing||7.1574",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.1574",
                "description": "Provisioned ONT is missing",
                "probableCause": "Provisioned ONT is not accessible on the PON.",
                "details": "SerialNo=1396A6A",
                "deviceSequenceNumber": "1901",
                "alarm": True,
                "port": "sonar_item_8755",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_8755']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5020",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280963\"",
                "deviceTimeString": "2024-08-26T15:45:00",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-missing",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-sonar_item_8755",
                "shelf-id": None,
                "slot-id": None,
                "port-id": None,
                "sequenceNum": "969637107402280963",
                "ont-id": "sonar_item_8755",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "1396A6A",
                "resource": "ONT: sonar_item_8755"
            },
            {
                "deviceTime": 1723191015000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-missing||7.637",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.637",
                "description": "Provisioned ONT is missing",
                "probableCause": "Provisioned ONT is not accessible on the PON.",
                "details": "SerialNo=101FADF",
                "deviceSequenceNumber": "729",
                "alarm": True,
                "port": "sonar_item_5671",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_5671']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5020",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280964\"",
                "deviceTimeString": "2024-08-09T08:10:15",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-missing",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-sonar_item_5671",
                "shelf-id": None,
                "slot-id": None,
                "port-id": None,
                "sequenceNum": "969637107402280964",
                "ont-id": "sonar_item_5671",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "101FADF",
                "resource": "ONT: sonar_item_5671"
            },
            {
                "deviceTime": 1723191015000,
                "receiveTime": 1748421102391,
                "severity": "MINOR",
                "alarmLevel": 2,
                "standing": True,
                "alarmReferForClear": "63d049daa639945c5524780f||ont-missing||7.636",
                "deviceType": "ONT",
                "sourceType": None,
                "category": "PON",
                "instanceId": "7.636",
                "description": "Provisioned ONT is missing",
                "probableCause": "Provisioned ONT is not accessible on the PON.",
                "details": "SerialNo=8864",
                "deviceSequenceNumber": "728",
                "alarm": True,
                "port": "sonar_item_4636",
                "location": None,
                "address": "/config/system/ont[ont-id='sonar_item_4636']",
                "primaryElement": None,
                "secondaryElement": None,
                "serviceAffecting": "SA",
                "subscriber": "",
                "isAcked": True,
                "userNotes": "Acknowledged by NOC",
                "region": "root/Pelican_Bay",
                "ackUser": "STRATANOC",
                "eventId": "5020",
                "deviceId": "63d049daa639945c5524780f",
                "expireAt": None,
                "acked": True,
                "receiveTimeString": "2025-05-28T08:31:42",
                "changeString": "\"969637107402280965\"",
                "deviceTimeString": "2024-08-09T08:10:15",
                "simpleName": "EMSAlarm",
                "condition-type": "ont-missing",
                "device-name": "PB-E72-OLT-1",
                "aid": "PB-E72-OLT-1-sonar_item_4636",
                "shelf-id": None,
                "slot-id": None,
                "port-id": None,
                "sequenceNum": "969637107402280965",
                "ont-id": "sonar_item_4636",
                "ont-type": "Residential",
                "ont-port-id": None,
                "pon-system-id": None,
                "admin-partition": None,
                "pon-id": None,
                "equipment-type": "ONT",
                "alarm-type": "EQUIPMENT",
                "switched-pon-id": None,
                "switched-channel-termination": None,
                "pon-device": None,
                "partition-id": None,
                "switched-shelf": None,
                "switched-slot": None,
                "switched-port": None,
                "serial-number": "8864",
                "resource": "ONT: sonar_item_4636"
            }
        ]
        logger.info(f"Generated {len(mock_alarms)} mock alarms")
        return mock_alarms
    
    async def _enrich_alarms(self, raw_alarms: List[Dict[str, Any]]) -> List[EnrichedAlarm]:
        """Enrich alarm data with Sonar information"""
        enriched_alarms = []
        logger.info(f"Starting enrichment of {len(raw_alarms)} alarms")
        
        for i, raw_alarm in enumerate(raw_alarms):
            try:
                logger.info(f"Processing alarm {i+1}/{len(raw_alarms)}: {raw_alarm.get('sequenceNum', 'unknown')}")
                
                # Parse raw alarm
                logger.debug(f"  Step 1: Parsing raw alarm data...")
                alarm = Alarm(**raw_alarm)
                logger.debug(f"  Step 1 COMPLETE: Successfully parsed alarm: {alarm.sequenceNum}")
                
                # Create enriched alarm
                logger.debug(f"  Step 2: Creating enriched alarm object...")
                enriched_alarm = EnrichedAlarm(**alarm.dict())
                logger.debug(f"  Step 2 COMPLETE: Successfully created enriched alarm: {enriched_alarm.sequenceNum}")
                
                # Populate additional fields
                logger.debug(f"  Step 2a: Populating additional fields...")
                enriched_alarm.deviceId = raw_alarm.get('deviceId', enriched_alarm.instanceId)
                enriched_alarm.eventId = raw_alarm.get('eventId', enriched_alarm.sequenceNum)
                
                # Convert timestamps to strings
                try:
                    receive_time = datetime.utcfromtimestamp(enriched_alarm.receiveTime / 1000)
                    device_time = datetime.utcfromtimestamp(enriched_alarm.deviceTime / 1000)
                    enriched_alarm.receiveTimeString = receive_time.isoformat() + 'Z'
                    enriched_alarm.deviceTimeString = device_time.isoformat() + 'Z'
                except Exception as e:
                    logger.warning(f"  Step 2a: Error converting timestamps: {e}")
                    enriched_alarm.receiveTimeString = "Unknown"
                    enriched_alarm.deviceTimeString = "Unknown"
                
                # Set acknowledgment fields
                enriched_alarm.acked = False
                enriched_alarm.isAcked = False
                
                # Initialize enrichment tracking fields
                enriched_alarm.is_enriched = False
                enriched_alarm.last_enrichment_time = datetime.now().isoformat()
                enriched_alarm.enrichment_attempts = 1
                
                logger.debug(f"  Step 2a COMPLETE: Additional fields populated")
                
                # Extract ONT ID for Sonar lookup
                ont_id = alarm.ont_id
                logger.debug(f"  Step 3: ONT ID extracted: {ont_id}")
                
                # If ont_id is "unknown" or doesn't start with "sonar_item_", try to extract from resource field
                if not ont_id or ont_id == "unknown" or not ont_id.startswith("sonar_item_"):
                    if alarm.resource and "sonar_item_" in alarm.resource:
                        # Extract from resource field like "ONT: sonar_item_6455"
                        import re
                        match = re.search(r"sonar_item_\d+", alarm.resource)
                        if match:
                            ont_id = match.group(0)
                            enriched_alarm.ont_id = ont_id  # Update the enriched alarm with the extracted ONT ID
                            logger.debug(f"  Step 3a: Extracted ONT ID from resource: {ont_id}")
                        else:
                            logger.debug(f"  Step 3a: Could not extract ONT ID from resource: {alarm.resource}")
                    else:
                        logger.debug(f"  Step 3a: No resource field or no sonar_item_ in resource: {alarm.resource}")
                
                if ont_id and ont_id.startswith("sonar_item_"):
                    logger.debug(f"  Step 4: Looking up Sonar data for ONT: {ont_id}")
                    # Enrich with Sonar data
                    sonar_data = await self.sonar_service.get_ont_location(ont_id)
                    if sonar_data:
                        logger.debug(f"  Step 4 COMPLETE: Found Sonar data for ONT: {ont_id}")
                        enriched_alarm.latitude = sonar_data.get("latitude")
                        enriched_alarm.longitude = sonar_data.get("longitude")
                        enriched_alarm.full_address = sonar_data.get("full_address")
                        enriched_alarm.account_name = sonar_data.get("account_name")
                        enriched_alarm.account_id = sonar_data.get("account_id")
                        enriched_alarm.region = sonar_data.get("region")
                        
                        # Populate address fields if available
                        if sonar_data.get("address_line1"):
                            enriched_alarm.address_line1 = sonar_data.get("address_line1")
                            enriched_alarm.address_line2 = sonar_data.get("address_line2")
                            enriched_alarm.address_city = sonar_data.get("address_city")
                            enriched_alarm.address_subdivision = sonar_data.get("address_subdivision")
                            enriched_alarm.address_zip = sonar_data.get("address_zip")
                        
                        # Populate other Sonar fields
                        enriched_alarm.account_status = sonar_data.get("account_status")
                        enriched_alarm.account_activates_account = sonar_data.get("account_activates_account")
                        enriched_alarm.customer_type = sonar_data.get("customer_type")
                        enriched_alarm.service_name = sonar_data.get("service_name")
                        enriched_alarm.inventory_model = sonar_data.get("inventory_model")
                        enriched_alarm.manufacturer = sonar_data.get("manufacturer")
                        enriched_alarm.inventory_status = sonar_data.get("inventory_status")
                        enriched_alarm.overall_status = sonar_data.get("overall_status")
                        enriched_alarm.inventoryitemable_id = sonar_data.get("inventoryitemable_id")
                        enriched_alarm.inventoryitemable_type = sonar_data.get("inventoryitemable_type")
                        
                        # Mark as enriched if we have valid location data
                        if enriched_alarm.latitude and enriched_alarm.longitude:
                            enriched_alarm.is_enriched = True
                            logger.info(f"  SUCCESS: Successfully enriched alarm with location data: {enriched_alarm.sequenceNum}")
                        else:
                            logger.info(f"  PARTIAL: Alarm {enriched_alarm.sequenceNum} has Sonar data but no coordinates (unused inventory)")
                    else:
                        logger.info(f"  UNENRICHED: No Sonar data found for ONT: {ont_id} - represents unused inventory")
                else:
                    logger.debug(f"  Step 4 SKIPPED: ONT ID not found or doesn't start with 'sonar_item_': {ont_id}")
                    logger.info(f"  UNENRICHED: Alarm {enriched_alarm.sequenceNum} has no valid ONT ID for enrichment")
                
                # Extract PON port information
                logger.debug(f"  Step 5: Extracting PON port information...")
                enriched_alarm.pon_port = self._extract_pon_port(alarm)
                logger.debug(f"  Step 5 COMPLETE: PON port extracted: {enriched_alarm.pon_port}")
                
                # Always add the alarm to the list, whether enriched or not
                enriched_alarms.append(enriched_alarm)
                logger.info(f"  STORED: Alarm {enriched_alarm.sequenceNum} stored as {'enriched' if enriched_alarm.is_enriched else 'unenriched'}")
                
            except Exception as e:
                logger.error(f"  FAILED: Error enriching alarm {raw_alarm.get('sequenceNum', 'unknown')}: {e}")
                import traceback
                logger.error(f"  FAILED: Traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"Enrichment complete: Successfully processed {len(enriched_alarms)} out of {len(raw_alarms)} alarms")
        return enriched_alarms
    
    def _extract_pon_port(self, alarm: Alarm) -> Optional[str]:
        """Extract PON port from alarm data"""
        # Try to extract from port field if it contains PON information
        if alarm.port and "/" in alarm.port:
            return alarm.port
        
        # Try to construct from shelf/slot/port
        if alarm.shelf_id and alarm.slot_id and alarm.port_id:
            return f"{alarm.shelf_id}/{alarm.slot_id}/{alarm.port_id}"
        
        # Try to extract from the address field
        if alarm.address and "ont[ont-id='" in alarm.address:
            # Extract ONT ID from address like "/config/system/ont[ont-id='sonar_item_5014']"
            match = re.search(r"ont\[ont-id='([^']+)'\]", alarm.address)
            if match:
                return match.group(1)
        
        return None
    
    async def _store_alarms(self, alarms: List[EnrichedAlarm]):
        """Store alarms in Redis"""
        try:
            logger.info(f"Starting to store {len(alarms)} alarms in Redis")
            
            # Get current alarm keys to identify truly stale alarms
            logger.debug("Step 1: Getting current alarm keys from Redis...")
            current_keys = await self.redis_client.keys("alarms:*")
            current_sequence_nums = {key.decode().split(":")[1] for key in current_keys}
            logger.info(f"Step 1 COMPLETE: Found {len(current_keys)} existing alarm keys in Redis")
            
            # Get sequence numbers of alarms we're about to store
            new_sequence_nums = {alarm.sequenceNum for alarm in alarms}
            
            # Store alarms (this will update existing ones and add new ones)
            logger.debug("Step 2: Storing alarms in Redis...")
            stored_count = 0
            for i, alarm in enumerate(alarms):
                try:
                    key = f"alarms:{alarm.sequenceNum}"
                    logger.debug(f"  Storing alarm {i+1}/{len(alarms)}: {key}")
                    
                    # Convert alarm to JSON
                    alarm_json = alarm.json()
                    logger.debug(f"  Alarm JSON length: {len(alarm_json)} characters")
                    
                    # Store in Redis
                    await self.redis_client.set(
                        key,
                        alarm_json,
                        ex=3600  # Expire after 1 hour
                    )
                    stored_count += 1
                    logger.debug(f"  SUCCESS: Stored alarm: {key}")
                except Exception as e:
                    logger.error(f"  FAILED: Error storing alarm {alarm.sequenceNum}: {e}")
                    import traceback
                    logger.error(f"  FAILED: Traceback: {traceback.format_exc()}")
                    continue
            
            logger.info(f"Step 2 COMPLETE: Stored {stored_count} alarms in Redis")
            
            # Remove truly stale alarms (those that exist in Redis but not in our current alarm list)
            logger.debug("Step 3: Removing stale alarms from Redis...")
            stale_keys = current_sequence_nums - new_sequence_nums
            removed_count = 0
            for sequence_num in stale_keys:
                try:
                    await self.redis_client.delete(f"alarms:{sequence_num}")
                    removed_count += 1
                    logger.debug(f"  Removed stale alarm: {sequence_num}")
                except Exception as e:
                    logger.error(f"  FAILED: Error removing stale alarm {sequence_num}: {e}")
            
            logger.info(f"Step 3 COMPLETE: Removed {removed_count} stale alarms from Redis")
            logger.info(f"Redis storage complete: Stored {stored_count} alarms, removed {removed_count} stale alarms")
            
        except Exception as e:
            logger.error(f"FAILED: Error storing alarms in Redis: {e}")
            import traceback
            logger.error(f"FAILED: Traceback: {traceback.format_exc()}")
    
    async def _update_last_poll_time(self):
        """Update the last poll timestamp"""
        try:
            await self.redis_client.set(
                "last_polled_at",
                datetime.utcnow().isoformat(),
                ex=3600
            )
        except Exception as e:
            logger.error(f"Error updating last poll time: {e}")
    
    async def get_all_alarms(self) -> List[AlarmResponse]:
        """Get all currently stored alarms"""
        try:
            logger.info("=== STARTING ALARM RETRIEVAL ===")
            logger.info("Step 1: Retrieving alarm keys from Redis...")
            alarm_keys = await self.redis_client.keys("alarms:*")
            logger.info(f"Step 1 COMPLETE: Found {len(alarm_keys)} alarm keys in Redis")
            
            if not alarm_keys:
                logger.warning("No alarm keys found in Redis - returning empty list")
                return []
            
            alarms = []
            logger.info("Step 2: Processing alarm data from Redis...")
            
            for i, key in enumerate(alarm_keys):
                try:
                    logger.debug(f"  Processing alarm {i+1}/{len(alarm_keys)}: {key.decode()}")
                    alarm_data = await self.redis_client.get(key)
                    
                    if alarm_data:
                        logger.debug(f"  Retrieved alarm data for key: {key.decode()}")
                        logger.debug(f"  Alarm data length: {len(alarm_data)} bytes")
                        
                        # Parse enriched alarm
                        enriched_alarm = EnrichedAlarm.parse_raw(alarm_data)
                        logger.debug(f"  Successfully parsed enriched alarm: {enriched_alarm.sequenceNum}")
                        
                        # Create alarm response
                        alarm_response = AlarmResponse(
                            # Core alarm fields
                            sequenceNum=enriched_alarm.sequenceNum,
                            description=enriched_alarm.description,
                            severity=enriched_alarm.severity,
                            serviceAffecting=enriched_alarm.serviceAffecting,
                            region=enriched_alarm.region or "Unknown",
                            deviceType=enriched_alarm.deviceType,
                            category=enriched_alarm.category,
                            eventId=enriched_alarm.eventId or enriched_alarm.sequenceNum,
                            deviceId=enriched_alarm.deviceId or enriched_alarm.instanceId,
                            device_name=enriched_alarm.device_name or "Unknown Device",
                            condition_type=enriched_alarm.condition_type or "unknown",
                            alarm_type=enriched_alarm.alarm_type or "Unknown",
                            equipment_type=enriched_alarm.equipment_type or "Unknown",
                            
                            # ONT-specific fields
                            ont_id=enriched_alarm.ont_id or "unknown",
                            ont_type=enriched_alarm.ont_type or "Unknown",
                            serial_number=enriched_alarm.serial_number or "Unknown",
                            port=enriched_alarm.port or "Unknown",
                            pon_port=enriched_alarm.pon_port,
                            
                            # Acknowledgment fields
                            acked=enriched_alarm.acked,
                            ackUser=enriched_alarm.ackUser,
                            userNotes=enriched_alarm.userNotes,
                            isAcked=enriched_alarm.isAcked,
                            
                            # Timing fields
                            receiveTimeString=enriched_alarm.receiveTimeString or "Unknown",
                            deviceTimeString=enriched_alarm.deviceTimeString or "Unknown",
                            deviceTime=enriched_alarm.deviceTime,
                            receiveTime=enriched_alarm.receiveTime,
                            
                            # Additional fields
                            probableCause=enriched_alarm.probableCause,
                            details=enriched_alarm.details,
                            aid=enriched_alarm.aid,
                            resource=enriched_alarm.resource or "Unknown Resource",
                            alarmLevel=enriched_alarm.alarmLevel,
                            standing=enriched_alarm.standing,
                            
                            # Enrichment tracking fields
                            is_enriched=enriched_alarm.is_enriched,
                            last_enrichment_time=enriched_alarm.last_enrichment_time,
                            enrichment_attempts=enriched_alarm.enrichment_attempts,
                            
                            # Calculated fields
                            is_service_affecting=self._convert_service_affecting_to_bool(enriched_alarm.serviceAffecting),
                            alarm_age_hours=self._calculate_alarm_age_hours(enriched_alarm.receiveTime),
                            
                            # Location data
                            latitude=enriched_alarm.latitude,
                            longitude=enriched_alarm.longitude,
                            full_address=enriched_alarm.full_address,
                            address_line1=enriched_alarm.address_line1,
                            address_line2=enriched_alarm.address_line2,
                            address_city=enriched_alarm.address_city,
                            address_subdivision=enriched_alarm.address_subdivision,
                            address_zip=enriched_alarm.address_zip,
                            account_id=enriched_alarm.account_id,
                            account_name=enriched_alarm.account_name,
                            account_status=enriched_alarm.account_status,
                            account_activates_account=enriched_alarm.account_activates_account,
                            customer_type=enriched_alarm.customer_type,
                            service_name=enriched_alarm.service_name,
                            inventory_model=enriched_alarm.inventory_model,
                            manufacturer=enriched_alarm.manufacturer,
                            inventory_status=enriched_alarm.inventory_status,
                            overall_status=enriched_alarm.overall_status,
                            inventoryitemable_id=enriched_alarm.inventoryitemable_id,
                            inventoryitemable_type=enriched_alarm.inventoryitemable_type
                        )
                        logger.debug(f"  Successfully created alarm response: {alarm_response.sequenceNum}")
                        alarms.append(alarm_response)
                    else:
                        logger.warning(f"  No data found for key: {key.decode()}")
                except Exception as e:
                    logger.error(f"  FAILED: Error processing alarm key {key.decode()}: {e}")
                    import traceback
                    logger.error(f"  FAILED: Traceback: {traceback.format_exc()}")
                    continue
            
            logger.info(f"Step 2 COMPLETE: Successfully processed {len(alarms)} alarms from Redis")
            logger.info(f"=== ALARM RETRIEVAL COMPLETE: Returning {len(alarms)} alarms ===")
            return alarms
            
        except Exception as e:
            logger.error(f"=== ALARM RETRIEVAL FAILED: {e} ===")
            import traceback
            logger.error(f"FAILED: Traceback: {traceback.format_exc()}")
            return []
    
    async def get_alarm_count(self) -> int:
        """Get the total number of active alarms"""
        try:
            alarm_keys = await self.redis_client.keys("alarms:*")
            return len(alarm_keys)
        except Exception as e:
            logger.error(f"Error getting alarm count: {e}")
            return 0
    
    async def get_last_poll_time(self) -> Optional[str]:
        """Get the last poll timestamp"""
        try:
            last_poll = await self.redis_client.get("last_polled_at")
            return last_poll.decode() if last_poll else None
        except Exception as e:
            logger.error(f"Error getting last poll time: {e}")
            return None

    def _calculate_alarm_age_hours(self, receiveTime: int) -> float:
        """Calculate the age of an alarm in hours"""
        current_time = datetime.utcnow().timestamp()
        alarm_time = receiveTime / 1000  # Convert milliseconds to seconds
        age_seconds = current_time - alarm_time
        return age_seconds / 3600  # Convert seconds to hours
    
    def _convert_service_affecting_to_bool(self, service_affecting: str) -> bool:
        """Convert service affecting string to boolean"""
        if isinstance(service_affecting, bool):
            return service_affecting
        return service_affecting.upper() == 'SA'  # 'SA' = Service Affecting = True
    
    def _should_re_enrich_alarm(self, existing_alarm: EnrichedAlarm) -> bool:
        """Determine if an existing alarm should be re-enriched"""
        if not existing_alarm.last_enrichment_time:
            # If no last enrichment time, it's a legacy alarm that should be re-enriched
            return True
        
        try:
            # Parse the last enrichment time
            last_enrichment = datetime.fromisoformat(existing_alarm.last_enrichment_time.replace('Z', '+00:00'))
            current_time = datetime.now(last_enrichment.tzinfo) if last_enrichment.tzinfo else datetime.now()
            
            # Calculate hours since last enrichment
            time_diff = current_time - last_enrichment
            hours_since_enrichment = time_diff.total_seconds() / 3600
            
            # Re-enrich if it's been more than 8 hours or if the alarm is not enriched
            should_re_enrich = hours_since_enrichment > 8 or not existing_alarm.is_enriched
            
            if should_re_enrich:
                logger.debug(f"Alarm {existing_alarm.sequenceNum} marked for re-enrichment: "
                           f"hours_since_enrichment={hours_since_enrichment:.2f}, "
                           f"is_enriched={existing_alarm.is_enriched}")
            
            return should_re_enrich
            
        except Exception as e:
            logger.warning(f"Error calculating re-enrichment time for alarm {existing_alarm.sequenceNum}: {e}")
            # If we can't parse the time, re-enrich to be safe
            return True
    
    async def _re_enrich_alarms(self, raw_alarms: List[Dict[str, Any]]) -> List[EnrichedAlarm]:
        """Re-enrich alarms that haven't been enriched in the last 8 hours"""
        re_enriched_alarms = []
        logger.info(f"Starting re-enrichment of {len(raw_alarms)} alarms")
        
        # Get existing alarms to preserve their data
        existing_alarms = await self._get_existing_alarms()
        existing_alarms_dict = {alarm.sequenceNum: alarm for alarm in existing_alarms}
        
        for i, raw_alarm in enumerate(raw_alarms):
            try:
                sequence_num = raw_alarm.get('sequenceNum', 'unknown')
                logger.info(f"Processing alarm {i+1}/{len(raw_alarms)}: {sequence_num}")
                
                # Get existing alarm data if available
                existing_alarm = existing_alarms_dict.get(sequence_num)
                
                # Parse raw alarm
                logger.debug(f"  Step 1: Parsing raw alarm data...")
                alarm = Alarm(**raw_alarm)
                logger.debug(f"  Step 1 COMPLETE: Successfully parsed alarm: {alarm.sequenceNum}")
                
                # Create enriched alarm, preserving existing data if available
                logger.debug(f"  Step 2: Creating enriched alarm object...")
                if existing_alarm:
                    # Start with existing alarm data and update with new raw data
                    enriched_alarm = EnrichedAlarm(**existing_alarm.dict())
                    # Update with new raw data
                    for key, value in alarm.dict().items():
                        setattr(enriched_alarm, key, value)
                    logger.debug(f"  Step 2 COMPLETE: Updated existing enriched alarm: {enriched_alarm.sequenceNum}")
                else:
                    # Create new enriched alarm
                    enriched_alarm = EnrichedAlarm(**alarm.dict())
                    logger.debug(f"  Step 2 COMPLETE: Created new enriched alarm: {enriched_alarm.sequenceNum}")
                
                # Populate additional fields
                logger.debug(f"  Step 2a: Populating additional fields...")
                enriched_alarm.deviceId = raw_alarm.get('deviceId', enriched_alarm.instanceId)
                enriched_alarm.eventId = raw_alarm.get('eventId', enriched_alarm.sequenceNum)
                
                # Convert timestamps to strings
                try:
                    receive_time = datetime.utcfromtimestamp(enriched_alarm.receiveTime / 1000)
                    device_time = datetime.utcfromtimestamp(enriched_alarm.deviceTime / 1000)
                    enriched_alarm.receiveTimeString = receive_time.isoformat() + 'Z'
                    enriched_alarm.deviceTimeString = device_time.isoformat() + 'Z'
                except Exception as e:
                    logger.warning(f"  Step 2a: Error converting timestamps: {e}")
                    enriched_alarm.receiveTimeString = "Unknown"
                    enriched_alarm.deviceTimeString = "Unknown"
                
                # Set acknowledgment fields (preserve existing if available)
                if not existing_alarm:
                    enriched_alarm.acked = False
                    enriched_alarm.isAcked = False
                
                # Update enrichment tracking fields
                enriched_alarm.last_enrichment_time = datetime.now().isoformat()
                if existing_alarm:
                    enriched_alarm.enrichment_attempts = existing_alarm.enrichment_attempts + 1
                else:
                    enriched_alarm.enrichment_attempts = 1
                
                logger.debug(f"  Step 2a COMPLETE: Additional fields populated (enrichment_attempts: {enriched_alarm.enrichment_attempts})")
                
                # Extract ONT ID for Sonar lookup
                ont_id = alarm.ont_id
                logger.debug(f"  Step 3: ONT ID extracted: {ont_id}")
                
                # If ont_id is "unknown" or doesn't start with "sonar_item_", try to extract from resource field
                if not ont_id or ont_id == "unknown" or not ont_id.startswith("sonar_item_"):
                    if alarm.resource and "sonar_item_" in alarm.resource:
                        # Extract from resource field like "ONT: sonar_item_6455"
                        import re
                        match = re.search(r"sonar_item_\d+", alarm.resource)
                        if match:
                            ont_id = match.group(0)
                            enriched_alarm.ont_id = ont_id  # Update the enriched alarm with the extracted ONT ID
                            logger.debug(f"  Step 3a: Extracted ONT ID from resource: {ont_id}")
                        else:
                            logger.debug(f"  Step 3a: Could not extract ONT ID from resource: {alarm.resource}")
                    else:
                        logger.debug(f"  Step 3a: No resource field or no sonar_item_ in resource: {alarm.resource}")
                
                if ont_id and ont_id.startswith("sonar_item_"):
                    logger.debug(f"  Step 4: Looking up Sonar data for ONT: {ont_id}")
                    # Enrich with Sonar data
                    sonar_data = await self.sonar_service.get_ont_location(ont_id)
                    if sonar_data:
                        logger.debug(f"  Step 4 COMPLETE: Found Sonar data for ONT: {ont_id}")
                        enriched_alarm.latitude = sonar_data.get("latitude")
                        enriched_alarm.longitude = sonar_data.get("longitude")
                        enriched_alarm.full_address = sonar_data.get("full_address")
                        enriched_alarm.account_name = sonar_data.get("account_name")
                        enriched_alarm.account_id = sonar_data.get("account_id")
                        enriched_alarm.region = sonar_data.get("region")
                        
                        # Populate address fields if available
                        if sonar_data.get("address_line1"):
                            enriched_alarm.address_line1 = sonar_data.get("address_line1")
                            enriched_alarm.address_line2 = sonar_data.get("address_line2")
                            enriched_alarm.address_city = sonar_data.get("address_city")
                            enriched_alarm.address_subdivision = sonar_data.get("address_subdivision")
                            enriched_alarm.address_zip = sonar_data.get("address_zip")
                        
                        # Populate other Sonar fields
                        enriched_alarm.account_status = sonar_data.get("account_status")
                        enriched_alarm.account_activates_account = sonar_data.get("account_activates_account")
                        enriched_alarm.customer_type = sonar_data.get("customer_type")
                        enriched_alarm.service_name = sonar_data.get("service_name")
                        enriched_alarm.inventory_model = sonar_data.get("inventory_model")
                        enriched_alarm.manufacturer = sonar_data.get("manufacturer")
                        enriched_alarm.inventory_status = sonar_data.get("inventory_status")
                        enriched_alarm.overall_status = sonar_data.get("overall_status")
                        enriched_alarm.inventoryitemable_id = sonar_data.get("inventoryitemable_id")
                        enriched_alarm.inventoryitemable_type = sonar_data.get("inventoryitemable_type")
                        
                        # Mark as enriched if we have valid location data
                        if enriched_alarm.latitude and enriched_alarm.longitude:
                            enriched_alarm.is_enriched = True
                            logger.info(f"  SUCCESS: Successfully re-enriched alarm with location data: {enriched_alarm.sequenceNum}")
                        else:
                            logger.info(f"  PARTIAL: Alarm {enriched_alarm.sequenceNum} has Sonar data but no coordinates (unused inventory)")
                    else:
                        logger.info(f"  UNENRICHED: No Sonar data found for ONT: {ont_id} - represents unused inventory")
                else:
                    logger.debug(f"  Step 4 SKIPPED: ONT ID not found or doesn't start with 'sonar_item_': {ont_id}")
                    logger.info(f"  UNENRICHED: Alarm {enriched_alarm.sequenceNum} has no valid ONT ID for enrichment")
                
                # Extract PON port information
                logger.debug(f"  Step 5: Extracting PON port information...")
                enriched_alarm.pon_port = self._extract_pon_port(alarm)
                logger.debug(f"  Step 5 COMPLETE: PON port extracted: {enriched_alarm.pon_port}")
                
                # Always add the alarm to the list, whether enriched or not
                re_enriched_alarms.append(enriched_alarm)
                logger.info(f"  STORED: Alarm {enriched_alarm.sequenceNum} stored as {'enriched' if enriched_alarm.is_enriched else 'unenriched'} (attempt {enriched_alarm.enrichment_attempts})")
                
            except Exception as e:
                logger.error(f"  FAILED: Error re-enriching alarm {raw_alarm.get('sequenceNum', 'unknown')}: {e}")
                import traceback
                logger.error(f"  FAILED: Traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"Re-enrichment complete: Successfully processed {len(re_enriched_alarms)} out of {len(raw_alarms)} alarms")
        return re_enriched_alarms
    
    async def full_sync_alarms(self):
        """Force a full sync: immediate SMx call and re-enrichment of all alarms regardless of elapsed time"""
        try:
            logger.info("=== STARTING FULL ALARM SYNC ===")
            
            # Fetch fresh alarms from SMx
            logger.info("Step 1: Fetching fresh alarms from SMx...")
            raw_alarms = await self._fetch_smx_alarms()
            logger.info(f"Step 1 COMPLETE: Fetched {len(raw_alarms)} fresh alarms from SMx")
            
            if not raw_alarms:
                logger.warning("No alarms received from SMx - ending sync")
                return
            
            # Log raw alarm details for debugging
            for i, alarm in enumerate(raw_alarms[:3]):  # Log first 3 alarms
                logger.info(f"Raw alarm {i+1}: sequenceNum={alarm.get('sequenceNum', 'N/A')}, description={alarm.get('description', 'N/A')}")
            
            # Get existing alarms from Redis to preserve any existing data
            logger.info("Step 2: Retrieving existing alarms from Redis for data preservation...")
            existing_alarms = await self._get_existing_alarms()
            existing_sequence_nums = {alarm.sequenceNum for alarm in existing_alarms}
            logger.info(f"Step 2 COMPLETE: Found {len(existing_alarms)} existing alarms in Redis")
            
            # For full sync, we re-enrich ALL alarms regardless of when they were last enriched
            logger.info("Step 3: Starting full re-enrichment of all alarms...")
            re_enriched_alarms = await self._re_enrich_alarms(raw_alarms)
            logger.info(f"Step 3 COMPLETE: Re-enriched {len(re_enriched_alarms)} alarms")
            
            # Store all re-enriched alarms in Redis
            logger.info("Step 4: Storing all re-enriched alarms in Redis...")
            await self._store_alarms(re_enriched_alarms)
            logger.info(f"Step 4 COMPLETE: Stored {len(re_enriched_alarms)} alarms in Redis")
            
            # Update last poll time
            logger.info("Step 5: Updating last poll time...")
            await self._update_last_poll_time()
            logger.info("Step 5 COMPLETE: Last poll time updated")
            
            logger.info(f"=== FULL ALARM SYNC COMPLETE: Successfully processed {len(re_enriched_alarms)} alarms ===")
            
        except Exception as e:
            logger.error(f"=== FULL ALARM SYNC FAILED: {e} ===")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    