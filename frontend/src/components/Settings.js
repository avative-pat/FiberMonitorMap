import React, { useState } from 'react';
import { Settings as SettingsIcon, Map, RefreshCw } from 'lucide-react';

const Settings = ({ focusMode, setFocusMode, refreshInterval, setRefreshInterval }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-2 rounded-md hover:bg-gray-700 transition-colors"
        title="Settings"
      >
        <SettingsIcon size={20} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-[55]"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 w-64 bg-gray-800 rounded-lg shadow-lg border border-gray-700 z-[60]">
            <div className="p-4">
              <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center space-x-2">
                <Map size={16} />
                <span>Map Settings</span>
              </h3>
              
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-2">
                    Map Mode
                  </label>
                  <select
                    value={focusMode}
                    onChange={(e) => setFocusMode(e.target.value)}
                    className="w-full bg-gray-700 text-gray-100 px-3 py-2 rounded border border-gray-600 text-sm focus:outline-none focus:border-blue-500"
                  >
                    <option value="default">Default View</option>
                    <option value="active">Focus on Alarms</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-gray-400 mb-2 flex items-center space-x-1">
                    <RefreshCw size={12} />
                    <span>Auto Refresh Interval</span>
                  </label>
                  <select
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(parseInt(e.target.value))}
                    className="w-full bg-gray-700 text-gray-100 px-3 py-2 rounded border border-gray-600 text-sm focus:outline-none focus:border-blue-500"
                  >
                    <option value={10000}>10 seconds</option>
                    <option value={60000}>60 seconds</option>
                    <option value={120000}>2 minutes</option>
                    <option value={300000}>5 minutes</option>
                    <option value={600000}>10 minutes</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Settings; 