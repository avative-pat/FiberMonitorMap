import React, { useState, useEffect } from 'react';
import { Wifi, Clock, Activity } from 'lucide-react';

const StatusBar = ({ status, loading }) => {
  const [timeSinceLastUpdate, setTimeSinceLastUpdate] = useState('Just now');

  useEffect(() => {
    if (!status?.last_polled_at) return;

    const updateTimer = () => {
      // Ensure the timestamp is treated as UTC by adding Z suffix if missing
      const timestamp = status.last_polled_at.endsWith('Z') 
        ? status.last_polled_at 
        : status.last_polled_at + 'Z';
      
      const lastUpdate = new Date(timestamp);
      const now = new Date();
      const diffMs = now - lastUpdate;
      const diffSeconds = Math.floor(diffMs / 1000);
      
      if (diffSeconds < 5) {
        setTimeSinceLastUpdate('Just now');
      } else if (diffSeconds < 60) {
        setTimeSinceLastUpdate(`${diffSeconds}s ago`);
      } else {
        const diffMins = Math.floor(diffSeconds / 60);
        if (diffMins < 60) {
          setTimeSinceLastUpdate(`${diffMins}m ago`);
        } else {
          const diffHours = Math.floor(diffMins / 60);
          if (diffHours < 24) {
            setTimeSinceLastUpdate(`${diffHours}h ago`);
          } else {
            const diffDays = Math.floor(diffHours / 24);
            setTimeSinceLastUpdate(`${diffDays}d ago`);
          }
        }
      }
    };

    // Update immediately
    updateTimer();
    
    // Update every second for real-time counter
    const interval = setInterval(updateTimer, 1000);
    
    return () => clearInterval(interval);
  }, [status?.last_polled_at]);

  if (loading) {
    return (
      <div className="flex items-center space-x-4 text-sm text-gray-400">
        <div className="animate-pulse bg-gray-600 h-4 w-20 rounded"></div>
        <div className="animate-pulse bg-gray-600 h-4 w-16 rounded"></div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="flex items-center space-x-4 text-sm text-gray-400">
        <span>Status unavailable</span>
      </div>
    );
  }

  const getStatusColor = (isPolling) => {
    return isPolling ? 'text-green-400' : 'text-red-400';
  };

  return (
    <div className="flex items-center space-x-4 text-sm">
      {/* Polling Status */}
      <div className="flex items-center space-x-1">
        <Activity 
          size={14} 
          className={getStatusColor(status.is_polling)} 
        />
        <span className={getStatusColor(status.is_polling)}>
          {status.is_polling ? 'Active' : 'Inactive'}
        </span>
      </div>

      {/* Last Poll Time - Real-time counter */}
      <div className="flex items-center space-x-1 text-gray-400">
        <Clock size={14} />
        <span>{timeSinceLastUpdate}</span>
      </div>

      {/* Total Alarms */}
      <div className="flex items-center space-x-1 text-gray-400">
        <Wifi size={14} />
        <span>{status.total_alarms || 0} alarms</span>
      </div>
    </div>
  );
};

export default StatusBar; 