import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useAlarms = () => {
  const [alarms, setAlarms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAlarms = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Fetching alarms from:', `${API_BASE_URL}/alarms`);
      const response = await fetch(`${API_BASE_URL}/alarms`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Received alarms from API:', data.length, 'alarms');
      
      // Check for any New York coordinates
      const nyAlarms = data.filter(alarm => 
        alarm.latitude === 40.7128 || alarm.latitude === 40.7589 ||
        alarm.longitude === -74.0060 || alarm.longitude === -73.9851 ||
        (alarm.full_address && alarm.full_address.includes('New York'))
      );
      
      if (nyAlarms.length > 0) {
        console.warn('Found New York coordinates in API response:', nyAlarms);
      }
      
      console.log('First few alarms:', data.slice(0, 3).map(a => ({
        description: a.description,
        latitude: a.latitude,
        longitude: a.longitude,
        full_address: a.full_address
      })));
      
      setAlarms(data);
    } catch (err) {
      console.error('Error fetching alarms:', err);
      setError(err.message);
      // Don't set mock data - just leave alarms as empty array
      setAlarms([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlarms();
  }, [fetchAlarms]);

  const refreshAlarms = useCallback(() => {
    fetchAlarms();
  }, [fetchAlarms]);

  return {
    alarms,
    loading,
    error,
    refreshAlarms
  };
}; 