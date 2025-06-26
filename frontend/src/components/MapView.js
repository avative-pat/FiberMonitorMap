import React, { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

// Set Mapbox access token
mapboxgl.accessToken = process.env.REACT_APP_MAPBOX_TOKEN || 'pk.eyJ1IjoiZXhhbXBsZSIsImEiOiJjbGV4YW1wbGUifQ.example';

// Custom CSS to override Mapbox popup styling
const customPopupCSS = `
  .custom-popup .mapboxgl-popup-content {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    padding: 0 !important;
  }
  
  .custom-popup .mapboxgl-popup-tip {
    border-top-color: #1e40af !important;
  }
`;

// Inject custom CSS
if (!document.getElementById('custom-popup-styles')) {
  const style = document.createElement('style');
  style.id = 'custom-popup-styles';
  style.textContent = customPopupCSS;
  document.head.appendChild(style);
}

const MapView = ({ alarms, focusMode, setFocusMode }) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const [lng] = useState(parseFloat(process.env.REACT_APP_DEFAULT_MAP_CENTER_LNG || -111.89979));
  const [lat] = useState(parseFloat(process.env.REACT_APP_DEFAULT_MAP_CENTER_LAT || 40.3356));
  const [zoom] = useState(parseInt(process.env.REACT_APP_DEFAULT_MAP_ZOOM || 12));

  useEffect(() => {
    if (map.current) return; // initialize map only once
    
    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: process.env.REACT_APP_MAPBOX_STYLE || 'mapbox://styles/mapbox/dark-v11',
      center: [lng, lat],
      zoom: zoom
    });

    // Add navigation controls
    map.current.addControl(new mapboxgl.NavigationControl(), 'top-left');

    // Add fullscreen control
    map.current.addControl(new mapboxgl.FullscreenControl(), 'top-right');

    // Cleanup on unmount
    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [lng, lat, zoom]);

  // Update markers when alarms change
  useEffect(() => {
    if (!map.current) return;

    // Remove existing markers
    const existingMarkers = document.querySelectorAll('.alarm-marker');
    existingMarkers.forEach(marker => marker.remove());

    // Add new markers
    alarms.forEach(alarm => {
      if (alarm.latitude && alarm.longitude) {
        // Create marker element
        const markerEl = document.createElement('div');
        markerEl.className = 'alarm-marker';
        markerEl.style.width = '20px';
        markerEl.style.height = '20px';
        markerEl.style.borderRadius = '50%';
        markerEl.style.backgroundColor = getSeverityColor(alarm);
        markerEl.style.border = '2px solid white';
        markerEl.style.cursor = 'pointer';
        markerEl.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';

        // Create popup
        const popup = new mapboxgl.Popup({ 
          offset: 25,
          className: 'custom-popup'
        }).setHTML(`
          <div class="p-4 bg-white rounded-lg border-2 border-blue-800 shadow-lg min-w-64">
            <div class="space-y-3">
              <!-- Header -->
              <div class="border-b border-gray-200 pb-2">
                <h3 class="font-bold text-gray-900 text-sm leading-tight">${alarm.description || 'Alarm'}</h3>
              </div>
              
              <!-- Service Affecting Status -->
              <div class="flex items-center space-x-2">
                <div class="w-3 h-3 rounded-full ${alarm.is_service_affecting ? 'bg-red-500' : 'bg-yellow-500'}"></div>
                <span class="text-sm font-medium text-gray-700">
                  Service Affecting: ${alarm.is_service_affecting ? 'Yes' : 'No'}
                </span>
              </div>
              
              <!-- Timestamp -->
              ${alarm.receiveTimeString ? `
                <div class="bg-gray-50 rounded p-2">
                  <p class="text-sm text-gray-700">
                    <span class="font-medium">Received:</span> 
                    <span class="timestamp" data-time="${alarm.receiveTimeString}">
                      ${new Date(alarm.receiveTimeString).toLocaleString()}
                    </span>
                  </p>
                  <p class="text-xs text-gray-500 mt-1">
                    ${getRelativeTime(alarm.receiveTimeString)}
                  </p>
                </div>
              ` : ''}
              
              <!-- Device Information -->
              <div class="bg-gray-50 rounded p-2">
                <p class="text-sm text-gray-700">
                  <span class="font-medium">Device:</span> ${alarm.inventory_model || alarm.device_name || 'Unknown Device'}
                </p>
                ${alarm.manufacturer ? `<p class="text-sm text-gray-600 mt-1"><span class="font-medium">Manufacturer:</span> ${alarm.manufacturer}</p>` : ''}
              </div>
              
              <!-- Customer Information -->
              ${alarm.account_name ? `
                <div class="bg-blue-50 rounded p-2 border-l-4 border-blue-400">
                  <p class="text-sm text-gray-700">
                    <span class="font-medium">Customer:</span> ${alarm.account_name}
                  </p>
                  ${alarm.customer_type ? `<p class="text-sm text-gray-600 mt-1"><span class="font-medium">Type:</span> ${alarm.customer_type}</p>` : ''}
                </div>
              ` : `
                <div class="bg-gray-50 rounded p-2 border-l-4 border-gray-400">
                  <p class="text-sm text-gray-600">No customer associated</p>
                </div>
              `}
              
              <!-- Address -->
              ${alarm.full_address ? `
                <div class="bg-gray-50 rounded p-2">
                  <p class="text-sm text-gray-700">
                    <span class="font-medium">Address:</span> ${alarm.full_address}
                  </p>
                </div>
              ` : ''}
            </div>
          </div>
        `);

        // Add marker to map
        new mapboxgl.Marker(markerEl)
          .setLngLat([alarm.longitude, alarm.latitude])
          .setPopup(popup)
          .addTo(map.current);
      }
    });

    // Focus on alarms if in active mode
    if (focusMode === 'active' && alarms.length > 0) {
      const bounds = new mapboxgl.LngLatBounds();
      alarms.forEach(alarm => {
        if (alarm.latitude && alarm.longitude) {
          bounds.extend([alarm.longitude, alarm.latitude]);
        }
      });
      
      if (!bounds.isEmpty()) {
        map.current.fitBounds(bounds, {
          padding: 50,
          maxZoom: 15
        });
      }
    }
  }, [alarms, focusMode]);

  const getSeverityColor = (alarm) => {
    // Use is_service_affecting field for color coding
    if (alarm.is_service_affecting === true) {
      return '#ef4444'; // red for service affecting
    } else if (alarm.is_service_affecting === false) {
      return '#eab308'; // yellow for non-service affecting
    } else {
      // Fallback to severity if is_service_affecting is not available
      switch (alarm.severity?.toUpperCase()) {
        case 'CRITICAL':
          return '#ef4444'; // red
        case 'MAJOR':
          return '#f97316'; // orange
        case 'MINOR':
          return '#eab308'; // yellow
        case 'WARNING':
          return '#3b82f6'; // blue
        default:
          return '#6b7280'; // gray
      }
    }
  };

  const getRelativeTime = (timestamp) => {
    if (!timestamp) return '';
    
    const alarmTime = new Date(timestamp);
    const now = new Date();
    const diffMs = now - alarmTime;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffSeconds < 60) {
      return 'Just now';
    } else if (diffMinutes < 60) {
      return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
    } else if (diffDays < 365) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
    } else {
      return alarmTime.toLocaleDateString();
    }
  };

  return (
    <div className="w-full h-full">
      <div ref={mapContainer} className="w-full h-full" />
    </div>
  );
};

export default MapView; 