import React from 'react';
import { AlertTriangle, Clock, X } from 'lucide-react';

const AlertsPanel = ({ alerts, loading }) => {
  if (loading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-gray-700 rounded-lg p-4">
              <div className="h-4 bg-gray-600 rounded w-3/4 mb-2"></div>
              <div className="h-3 bg-gray-600 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (alerts.length === 0) {
    return (
      <div className="p-4 text-center">
        <AlertTriangle className="mx-auto text-gray-500 mb-2" size={32} />
        <p className="text-sm text-gray-500">No active alerts</p>
      </div>
    );
  }

  const getSeverityColor = (severity) => {
    switch (severity?.toUpperCase()) {
      case 'CRITICAL':
        return 'text-red-400 bg-red-900/20 border-red-500/30';
      case 'MAJOR':
        return 'text-orange-400 bg-orange-900/20 border-orange-500/30';
      case 'MINOR':
        return 'text-yellow-400 bg-yellow-900/20 border-yellow-500/30';
      case 'WARNING':
        return 'text-blue-400 bg-blue-900/20 border-blue-500/30';
      default:
        return 'text-gray-400 bg-gray-900/20 border-gray-500/30';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    // Ensure the timestamp is treated as UTC by adding Z suffix if missing
    const utcTimestamp = timestamp.endsWith('Z') ? timestamp : timestamp + 'Z';
    const date = new Date(utcTimestamp);
    return date.toLocaleString();
  };

  return (
    <div className="p-4 space-y-4">
      {alerts.map((alert, index) => (
        <div
          key={alert.id || index}
          className={`p-4 rounded-lg border ${getSeverityColor(alert.severity)}`}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex items-center space-x-2">
              <AlertTriangle size={16} />
              <span className="font-medium text-sm">{alert.title || 'Alert'}</span>
            </div>
            <span className="text-xs opacity-70">
              {alert.severity || 'UNKNOWN'}
            </span>
          </div>
          
          {alert.message && (
            <p className="text-sm mb-3 opacity-90">{alert.message}</p>
          )}
          
          <div className="flex items-center justify-between text-xs opacity-70">
            <div className="flex items-center space-x-1">
              <Clock size={12} />
              <span>{formatTimestamp(alert.timestamp)}</span>
            </div>
            
            {alert.source && (
              <span className="bg-gray-700 px-2 py-1 rounded text-xs">
                {alert.source}
              </span>
            )}
          </div>
          
          {alert.details && (
            <details className="mt-3">
              <summary className="text-xs cursor-pointer hover:opacity-80">
                View Details
              </summary>
              <pre className="text-xs mt-2 p-2 bg-gray-800 rounded overflow-x-auto">
                {JSON.stringify(alert.details, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
};

export default AlertsPanel; 