import os
import logging
from typing import Optional, Dict, Any
import httpx
from gql import gql, Client
from gql.transport.httpx import HTTPXAsyncTransport

logger = logging.getLogger(__name__)

class SonarService:
    def __init__(self):
        self.sonar_url = os.getenv("SONAR_API_URL")
        self.sonar_token = os.getenv("SONAR_API_KEY")
        
        # Initialize GraphQL client
        if self.sonar_url and self.sonar_token:
            transport = HTTPXAsyncTransport(
                url=self.sonar_url,
                headers={
                    "Authorization": f"Bearer {self.sonar_token}",
                    "Content-Type": "application/json"
                },
                verify=False  # For self-signed certificates
            )
            self.client = Client(transport=transport, fetch_schema_from_transport=True)
        else:
            self.client = None
            logger.warning("Sonar API not configured - location enrichment will be disabled")
    
    async def get_ont_location(self, ont_id: str) -> Optional[Dict[str, Any]]:
        """Get location and account information for an ONT from Sonar"""
        logger.info(f"[SONAR] get_ont_location called with ont_id={ont_id}")
        if not self.client:
            logger.warning("[SONAR] Sonar API client not configured, using mock location.")
            return self._get_mock_location(ont_id)
        try:
            # First, let's try a simpler query to see what fields are available
            simple_query = gql("""
                query GetOntLocation($ontId: Int64Bit!) {
                    inventory_items(id: $ontId) {
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
                                    account_type {
                                        name
                                    }
                                    account_status {
                                        name
                                    }
                                }
                                service {
                                    id
                                    name
                                }
                            }
                            inventory_model {
                                model_name
                                manufacturer {
                                    name
                                }
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
            """)
            
            variables = {"ontId": int(ont_id.replace("sonar_item_", ""))}
            logger.info(f"[SONAR] Querying Sonar for ont_id={ont_id} with variables={variables}")
            result = await self.client.execute_async(simple_query, variable_values=variables)
            logger.info(f"[SONAR] Raw Sonar GraphQL result for ont_id={ont_id}: {result}")
            
            if result and result.get("inventory_items") and result["inventory_items"].get("entities"):
                entities = result["inventory_items"]["entities"]
                if entities:
                    inventory = entities[0]  # Get first entity
                    logger.info(f"[SONAR] Found inventory entity for ont_id={ont_id}: {inventory}")
                    
                    # Check if we have inventoryitemable information
                    inventoryitemable = inventory.get("inventoryitemable")
                    inventoryitemable_id = inventoryitemable.get("id") if inventoryitemable else None
                    inventoryitemable_type = inventoryitemable.get("__typename") if inventoryitemable else None
                    
                    logger.info(f"[SONAR] inventoryitemable for ont_id={ont_id}: type={inventoryitemable_type}, id={inventoryitemable_id}")
                    
                    # If we have an inventoryitemable_id and it's an Address type, query for address details
                    if inventoryitemable_id and inventoryitemable_type == "Address":
                        logger.info(f"[SONAR] Found Address in inventoryitemable for ont_id={ont_id}, querying address details")
                        address_details = await self._get_address_details(inventoryitemable_id)
                        if address_details:
                            logger.info(f"[SONAR] Found address details for ont_id={ont_id}: {address_details}")
                            return {
                                "latitude": address_details.get("latitude"),
                                "longitude": address_details.get("longitude"),
                                "full_address": address_details.get("full_address"),
                                "account_name": address_details.get("customer_name"),
                                "account_number": address_details.get("customer_id"),
                                "region": address_details.get("customer_type"),
                                "inventory_model": inventory.get("inventory_model", {}).get("model_name"),
                                "manufacturer": inventory.get("inventory_model", {}).get("manufacturer", {}).get("name"),
                                "inventory_status": inventory.get("status"),
                                "overall_status": inventory.get("overall_status")
                            }
                    
                    # If we don't have address details, check if the inventory item itself has coordinates
                    latitude = inventory.get("latitude")
                    longitude = inventory.get("longitude")
                    
                    if latitude and longitude:
                        logger.info(f"[SONAR] Using coordinates from inventory item for ont_id={ont_id}: lat={latitude}, lng={longitude}")
                        return {
                            "latitude": latitude,
                            "longitude": longitude,
                            "full_address": f"Location for {ont_id}",
                            "account_name": None,
                            "account_number": None,
                            "region": None,
                            "inventory_model": inventory.get("inventory_model", {}).get("model_name"),
                            "manufacturer": inventory.get("inventory_model", {}).get("manufacturer", {}).get("name"),
                            "inventory_status": inventory.get("status"),
                            "overall_status": inventory.get("overall_status")
                        }
                    
                    logger.warning(f"[SONAR] No location data found for ont_id={ont_id}, using mock location")
                    return self._get_mock_location(ont_id)
            
            logger.warning(f"[SONAR] No inventory entity found for ont_id={ont_id}, using mock location.")
            return self._get_mock_location(ont_id)
            
        except Exception as e:
            logger.error(f"[SONAR] Error fetching ONT location from Sonar for {ont_id}: {e}")
            import traceback
            logger.error(f"[SONAR] Traceback: {traceback.format_exc()}")
            return self._get_mock_location(ont_id)
    
    async def _get_address_details(self, address_id: str) -> Optional[Dict[str, Any]]:
        """Get address details from Sonar"""
        try:
            address_query = gql("""
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
            """)
            
            variables = {"addressId": int(address_id)}
            result = await self.client.execute_async(address_query, variable_values=variables)
            logger.info(f"[SONAR] Address query result for address_id={address_id}: {result}")
            
            if result and result.get("addresses") and result["addresses"].get("entities"):
                entities = result["addresses"]["entities"]
                if entities:
                    address = entities[0]  # Get first address entity
                    logger.info(f"[SONAR] Found address entity for address_id={address_id}: {address}")
                    
                    # Build full address
                    address_parts = []
                    if address.get("line1"):
                        address_parts.append(address["line1"])
                    if address.get("line2"):
                        address_parts.append(address["line2"])
                    if address.get("city"):
                        address_parts.append(address["city"])
                    if address.get("subdivision"):
                        subdivision = address.get("subdivision")
                        if subdivision and subdivision != "null":
                            address_parts.append(subdivision)
                    if address.get("zip"):
                        address_parts.append(address["zip"])
                    
                    full_address = ", ".join(address_parts) if address_parts else None
                    
                    # Check if there's an associated customer account
                    addressable = address.get("addressable")
                    customer_data = {}
                    
                    if addressable and addressable.get("__typename") == "Account":
                        # Get customer details from the associated account
                        customer_data = await self._get_customer_details(addressable.get("id"))
                    
                    # Combine address and customer data
                    result_data = {
                        "latitude": address.get("latitude"),
                        "longitude": address.get("longitude"),
                        "full_address": full_address,
                        "customer_id": customer_data.get("customer_id"),
                        "customer_name": customer_data.get("customer_name"),
                        "customer_type": customer_data.get("customer_type"),
                        "customer_status": customer_data.get("customer_status")
                    }
                    
                    logger.info(f"[SONAR] Final address details for address_id={address_id}: {result_data}")
                    return result_data
            
            logger.warning(f"[SONAR] No address entity found for address_id={address_id}")
            return None
            
        except Exception as e:
            logger.error(f"[SONAR] Error fetching address details from Sonar for {address_id}: {e}")
            import traceback
            logger.error(f"[SONAR] Traceback: {traceback.format_exc()}")
            return None
    
    async def _get_customer_details(self, account_id: str) -> Dict[str, Any]:
        """Get customer details from Sonar account"""
        try:
            customer_query = gql("""
                query GetCustomerDetails($accountId: Int64Bit!) {
                    accounts(id: $accountId) {
                        entities {
                            id
                            name
                            account_type {
                                name
                            }
                            account_status {
                                name
                            }
                        }
                    }
                }
            """)
            
            variables = {"accountId": int(account_id)}
            result = await self.client.execute_async(customer_query, variable_values=variables)
            
            if result and result.get("accounts") and result["accounts"].get("entities"):
                entities = result["accounts"]["entities"]
                if entities:
                    account = entities[0]  # Get first account entity
                    
                    # Return customer data with prefixed keys to avoid conflicts
                    return {
                        "customer_id": account.get("id"),
                        "customer_name": account.get("name"),
                        "customer_type": account.get("account_type", {}).get("name"),
                        "customer_status": account.get("account_status", {}).get("name")
                    }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching customer details from Sonar for {account_id}: {e}")
            return {}
    
    def _get_mock_location(self, ont_id: str) -> Optional[Dict[str, Any]]:
        """Return None for ONTs without address data - they represent unused inventory"""
        logger.info(f"[SONAR] No address found for ont_id={ont_id} - this represents unused inventory, not displaying on map")
        return None
    
    async def test_connection(self) -> bool:
        """Test the connection to Sonar API"""
        if not self.client:
            return False
        
        try:
            # Simple query to test connection
            query = gql("""
                query TestConnection {
                    __schema {
                        types {
                            name
                        }
                    }
                }
            """)
            
            await self.client.execute_async(query)
            return True
            
        except Exception as e:
            logger.error(f"Sonar API connection test failed: {e}")
            return False 