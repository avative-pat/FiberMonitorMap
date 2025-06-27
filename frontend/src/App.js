import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { RefreshCw, Map, Filter, AlertTriangle, Menu, X } from 'lucide-react';
import MapView from './components/MapView';
import FilterPanel from './components/FilterPanel';
import AlertsPanel from './components/AlertsPanel';
import StatusBar from './components/StatusBar';
import Settings from './components/Settings';
import { useAlarms } from './hooks/useAlarms';
import { useAlerts } from './hooks/useAlerts';
import { useStatus } from './hooks/useStatus';

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [focusMode, setFocusMode] = useState('active');
  
  // Load refresh interval from localStorage or use default (60 seconds)
  const getInitialRefreshInterval = () => {
    try {
      const savedInterval = localStorage.getItem('fiberMonitorRefreshInterval');
      return savedInterval ? parseInt(savedInterval) : 60000;
    } catch (error) {
      console.warn('Failed to load refresh interval from localStorage:', error);
      return 60000;
    }
  };
  
  const [refreshInterval, setRefreshInterval] = useState(getInitialRefreshInterval);
  
  // Custom hooks for data fetching
  const { alarms, loading: alarmsLoading, syncing: alarmsSyncing, refreshAlarms, syncAlarms } = useAlarms();
  const { alerts, loading: alertsLoading, refreshAlerts } = useAlerts();
  const { status, loading: statusLoading, refreshStatus } = useStatus();

  // Compute default date range from alarms
  const defaultDateRange = useMemo(() => {
    const alarmDates = alarms
      .map(a => a.receiveTimeString ? new Date(a.receiveTimeString) : null)
      .filter(Boolean)
      .sort((a, b) => a - b);
    
    const minDate = alarmDates.length > 0 ? alarmDates[0] : new Date();
    const maxDate = alarmDates.length > 0 ? alarmDates[alarmDates.length - 1] : new Date();
    
    // Use tomorrow's date as the upper bound
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const sliderMaxDate = maxDate > tomorrow ? maxDate : tomorrow;
    
    return {
      start: minDate.toISOString().slice(0, 10),
      end: sliderMaxDate.toISOString().slice(0, 10)
    };
  }, [alarms]);

  // Load filters from localStorage or use defaults
  const getInitialFilters = () => {
    try {
      const savedFilters = localStorage.getItem('fiberMonitorFilters');
      if (savedFilters) {
        const parsed = JSON.parse(savedFilters);
        // Ensure customerStatus has at least "Customer Associated" as default
        if (!parsed.customerStatus || parsed.customerStatus.length === 0) {
          parsed.customerStatus = ['Customer Associated'];
        }
        // Validate date range - if invalid, it will be set by the useEffect later
        if (parsed.alarmDateRange && (!parsed.alarmDateRange.start || !parsed.alarmDateRange.end)) {
          parsed.alarmDateRange = { start: '', end: '' };
        }
        return parsed;
      }
    } catch (error) {
      console.warn('Failed to load filters from localStorage:', error);
    }
    
    return {
      severity: [],
      deviceType: [],
      category: [],
      region: [],
      customerStatus: ['Customer Associated'], // Default to showing customer-associated alarms
      alarmDateRange: { start: '', end: '' }
    };
  };

  const [filters, setFilters] = useState(getInitialFilters);

  // Save filters to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem('fiberMonitorFilters', JSON.stringify(filters));
    } catch (error) {
      console.warn('Failed to save filters to localStorage:', error);
    }
  }, [filters]);

  // Save refresh interval to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('fiberMonitorRefreshInterval', refreshInterval.toString());
    } catch (error) {
      console.warn('Failed to save refresh interval to localStorage:', error);
    }
  }, [refreshInterval]);

  // Update filters when defaultDateRange changes, but preserve existing filter values
  useEffect(() => {
    if (defaultDateRange.start && defaultDateRange.end) {
      setFilters(prev => ({
        ...prev,
        alarmDateRange: prev.alarmDateRange.start && prev.alarmDateRange.end 
          ? prev.alarmDateRange // Keep existing date range if already set
          : defaultDateRange // Only set default if no date range exists
      }));
    }
  }, [defaultDateRange]);

  // Auto-refresh based on configured interval
  useEffect(() => {
    const interval = setInterval(() => {
      refreshAlarms();
      refreshAlerts();
      refreshStatus();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [refreshAlarms, refreshAlerts, refreshStatus, refreshInterval]);

  // Manual refresh function - now triggers full backend sync
  const handleRefresh = useCallback(() => {
    console.log('=== REFRESH BUTTON CLICKED ===');
    console.log('Calling syncAlarms...');
    syncAlarms(); // Trigger full backend sync
    console.log('Calling refreshAlerts...');
    refreshAlerts();
    console.log('Calling refreshStatus...');
    refreshStatus();
    console.log('=== REFRESH BUTTON HANDLED ===');
  }, [syncAlarms, refreshAlerts, refreshStatus]);

  // Filter alarms based on selected filters
  const filteredAlarms = useMemo(() => {
    return alarms.filter(alarm => {
      // Severity filter
      if (filters.severity.length > 0 && !filters.severity.includes(alarm.severity)) {
        return false;
      }
      
      // Device type filter
      if (filters.deviceType.length > 0 && !filters.deviceType.includes(alarm.device_type)) {
        return false;
      }
      
      // Category filter
      if (filters.category.length > 0 && !filters.category.includes(alarm.category)) {
        return false;
      }
      
      // Region filter
      if (filters.region.length > 0 && !filters.region.includes(alarm.region)) {
        return false;
      }
      
      // Customer status filter
      if (filters.customerStatus.length > 0) {
        // Use the explicit account_activates_account field if available, otherwise fall back to checking account_name
        const hasActiveCustomer = alarm.account_activates_account === true || 
                                (alarm.account_activates_account === null && alarm.account_name !== null && alarm.account_name !== undefined);
        const customerStatus = hasActiveCustomer ? 'Customer Associated' : 'No Customer';
        if (!filters.customerStatus.includes(customerStatus)) {
          return false;
        }
      }

      // Alarm Age Date Range filter
      if (filters.alarmDateRange && filters.alarmDateRange.start && filters.alarmDateRange.end) {
        if (!alarm.receiveTimeString) return false;
        const alarmDate = new Date(alarm.receiveTimeString);
        const startDate = new Date(filters.alarmDateRange.start);
        const endDate = new Date(filters.alarmDateRange.end);
        
        // Set time to start of day for start date and end of day for end date
        startDate.setHours(0, 0, 0, 0);
        endDate.setHours(23, 59, 59, 999);
        
        if (alarmDate < startDate || alarmDate > endDate) {
          return false;
        }
      }
      
      return true;
    });
  }, [alarms, filters]);

  // Set alerts panel default state based on alert count
  useEffect(() => {
    // Only auto-show alerts panel if there are alerts and it's currently closed
    if (alerts.length > 0 && !alertsOpen) {
      setAlertsOpen(true);
    }
    // Only auto-hide alerts panel if there are no alerts and it's currently open
    else if (alerts.length === 0 && alertsOpen) {
      setAlertsOpen(false);
    }
  }, [alerts.length]); // Remove alertsOpen from dependencies to prevent infinite loops

  return (
    <div className="h-screen bg-gray-900 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-4 py-3 flex items-center justify-between relative z-50">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="lg:hidden p-2 rounded-md hover:bg-gray-700 transition-colors"
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          
          <div className="flex items-center space-x-2">
            <Map className="text-blue-400" size={24} />
            <h1 className="text-xl font-bold">Fiber Network Monitor</h1>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <StatusBar status={status} loading={statusLoading} />
          
          <button
            onClick={handleRefresh}
            disabled={alarmsLoading || alarmsSyncing}
            className="p-2 rounded-md hover:bg-gray-700 transition-colors disabled:opacity-50"
            title={alarmsSyncing ? "Syncing with backend..." : "Refresh data (full sync)"}
          >
            <RefreshCw 
              size={20} 
              className={(alarmsLoading || alarmsSyncing) ? 'animate-spin' : ''} 
            />
          </button>

          <Settings 
            focusMode={focusMode} 
            setFocusMode={setFocusMode} 
            refreshInterval={refreshInterval}
            setRefreshInterval={setRefreshInterval}
          />

          <button
            onClick={() => setAlertsOpen(!alertsOpen)}
            className="p-2 rounded-md hover:bg-gray-700 transition-colors relative"
            title="View alerts"
          >
            <AlertTriangle size={20} />
            {alerts.length > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {alerts.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <div className={`
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0 lg:static lg:inset-0
          fixed inset-y-0 left-0 z-50 w-80 bg-gray-800 border-r border-gray-700
          transform transition-transform duration-300 ease-in-out
        `}>
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold flex items-center space-x-2">
                <Filter size={20} />
                <span>Filters</span>
              </h2>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <FilterPanel alarms={alarms} filters={filters} setFilters={setFilters} />
            </div>
          </div>
        </div>

        {/* Map Area */}
        <div className="flex-1 relative">
          <MapView 
            alarms={filteredAlarms} 
            focusMode={focusMode}
            setFocusMode={setFocusMode}
          />
        </div>

        {/* Alerts Panel */}
        <div className={`
          ${alertsOpen ? 'translate-x-0' : 'translate-x-full'}
          fixed top-0 right-0 z-30 w-96 bg-gray-800 border-l border-gray-700
          transform transition-transform duration-300 ease-in-out
          lg:fixed lg:right-0
          h-screen pt-16
        `}>
          <div className="h-full flex flex-col">
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-semibold flex items-center space-x-2">
                <AlertTriangle size={20} />
                <span>Alerts</span>
              </h2>
              <button
                onClick={() => setAlertsOpen(false)}
                className="p-1 rounded hover:bg-gray-700"
              >
                <X size={16} />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto">
              <AlertsPanel alerts={alerts} loading={alertsLoading} />
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile Alerts Overlay */}
      {alertsOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-30"
          onClick={() => setAlertsOpen(false)}
        />
      )}
    </div>
  );
}

export default App; 