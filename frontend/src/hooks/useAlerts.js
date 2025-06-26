import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export const useAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAlerts = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_BASE_URL}/alerts`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      setAlerts(data);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError(err.message);
      // For development, use mock data if API is not available
      if (err.message.includes('Failed to fetch') || err.message.includes('ECONNREFUSED')) {
        setAlerts([
          {
            id: '1',
            title: 'High Alarm Volume',
            message: 'Unusually high number of alarms detected in the last hour',
            severity: 'WARNING',
            source: 'System Monitor',
            timestamp: new Date().toISOString(),
            details: {
              alarm_count: 15,
              threshold: 10,
              time_window: '1 hour'
            }
          },
          {
            id: '2',
            title: 'Backend Connection Lost',
            message: 'Unable to connect to Calix SMx API',
            severity: 'MAJOR',
            source: 'API Monitor',
            timestamp: new Date(Date.now() - 600000).toISOString(),
            details: {
              endpoint: '/rest/v1/fault/alarm',
              error: 'Connection timeout',
              retry_count: 3
            }
          }
        ]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const refreshAlerts = useCallback(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  return {
    alerts,
    loading,
    error,
    refreshAlerts
  };
}; 