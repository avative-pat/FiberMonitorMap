import React, { useState, useMemo } from 'react';
import { Filter, X } from 'lucide-react';
import { Range } from 'react-range';

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

function formatDateForDisplay(date) {
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric',
    year: 'numeric'
  });
}

const FilterPanel = ({ alarms, filters, setFilters }) => {
  // Compute min/max dates from alarms
  const alarmDates = useMemo(() => alarms
    .map(a => {
      if (!a.receiveTimeString) return null;
      // Ensure the timestamp is treated as UTC by adding Z suffix if missing
      const utcTimestamp = a.receiveTimeString.endsWith('Z') ? a.receiveTimeString : a.receiveTimeString + 'Z';
      return new Date(utcTimestamp);
    })
    .filter(Boolean)
    .sort((a, b) => a - b), [alarms]);
  
  const minDate = alarmDates.length > 0 ? alarmDates[0] : new Date();
  const maxDate = alarmDates.length > 0 ? alarmDates[alarmDates.length - 1] : new Date();
  
  // Use tomorrow's date as the upper bound to ensure we don't filter off recent alarms
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const sliderMaxDate = maxDate > tomorrow ? maxDate : tomorrow;
  
  // Convert dates to timestamps for the slider
  const minTimestamp = minDate.getTime();
  const maxTimestamp = sliderMaxDate.getTime();
  
  // Convert current filter values to timestamps
  const currentStartTimestamp = filters.alarmDateRange?.start 
    ? new Date(filters.alarmDateRange.start).getTime() 
    : minTimestamp;
  const currentEndTimestamp = filters.alarmDateRange?.end 
    ? new Date(filters.alarmDateRange.end).getTime() 
    : maxTimestamp;

  // Ensure timestamps are within valid range
  const validStartTimestamp = Math.max(minTimestamp, Math.min(maxTimestamp, currentStartTimestamp));
  const validEndTimestamp = Math.max(minTimestamp, Math.min(maxTimestamp, currentEndTimestamp));

  // Extract unique values for filter options
  const filterOptions = useMemo(() => {
    const options = {
      severity: [...new Set(alarms.map(a => a.severity).filter(Boolean))],
      deviceType: [...new Set(alarms.map(a => a.device_type).filter(Boolean))],
      category: [...new Set(alarms.map(a => a.category).filter(Boolean))],
      region: [...new Set(alarms.map(a => a.region).filter(Boolean))],
      customerStatus: ['Customer Associated', 'No Customer']
    };
    return options;
  }, [alarms]);

  const handleFilterChange = (filterType, value, checked) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: checked 
        ? [...prev[filterType], value]
        : prev[filterType].filter(v => v !== value)
    }));
  };

  const handleDateRangeChange = (values) => {
    const [startTimestamp, endTimestamp] = values;
    setFilters(prev => ({
      ...prev,
      alarmDateRange: {
        start: formatDateInput(new Date(startTimestamp)),
        end: formatDateInput(new Date(endTimestamp))
      }
    }));
  };

  const clearFilters = () => {
    setFilters({
      severity: [],
      deviceType: [],
      category: [],
      region: [],
      customerStatus: ['Customer Associated'],
      alarmDateRange: {
        start: formatDateInput(minDate),
        end: formatDateInput(sliderMaxDate)
      }
    });
  };

  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    if (key === 'customerStatus') {
      // Only consider it active if it's not just the default "Customer Associated"
      return Array.isArray(value) && value.length > 0 && 
             !(value.length === 1 && value[0] === 'Customer Associated');
    }
    if (key === 'alarmDateRange') {
      return value && (value.start !== formatDateInput(minDate) || value.end !== formatDateInput(sliderMaxDate));
    }
    return Array.isArray(value) ? value.length > 0 : false;
  });

  return (
    <div className="p-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-300">Filters</h3>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-gray-400 hover:text-gray-200 flex items-center space-x-1"
          >
            <X size={12} />
            <span>Clear all</span>
          </button>
        )}
      </div>

      {/* Severity Filter */}
      {filterOptions.severity.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">Severity</h4>
          <div className="space-y-2">
            {filterOptions.severity.map(severity => (
              <label key={severity} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.severity.includes(severity)}
                  onChange={(e) => handleFilterChange('severity', severity, e.target.checked)}
                  className="rounded border-gray-600 bg-gray-700 text-blue-400 focus:ring-blue-400"
                />
                <span className="text-sm text-gray-300">{severity}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Device Type Filter */}
      {filterOptions.deviceType.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">Device Type</h4>
          <div className="space-y-2">
            {filterOptions.deviceType.map(deviceType => (
              <label key={deviceType} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.deviceType.includes(deviceType)}
                  onChange={(e) => handleFilterChange('deviceType', deviceType, e.target.checked)}
                  className="rounded border-gray-600 bg-gray-700 text-blue-400 focus:ring-blue-400"
                />
                <span className="text-sm text-gray-300">{deviceType}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Category Filter */}
      {filterOptions.category.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">Category</h4>
          <div className="space-y-2">
            {filterOptions.category.map(category => (
              <label key={category} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.category.includes(category)}
                  onChange={(e) => handleFilterChange('category', category, e.target.checked)}
                  className="rounded border-gray-600 bg-gray-700 text-blue-400 focus:ring-blue-400"
                />
                <span className="text-sm text-gray-300">{category}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Region Filter */}
      {filterOptions.region.length > 0 && (
        <div>
          <h4 className="text-xs font-medium text-gray-400 mb-2">Region</h4>
          <div className="space-y-2">
            {filterOptions.region.map(region => (
              <label key={region} className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={filters.region.includes(region)}
                  onChange={(e) => handleFilterChange('region', region, e.target.checked)}
                  className="rounded border-gray-600 bg-gray-700 text-blue-400 focus:ring-blue-400"
                />
                <span className="text-sm text-gray-300">{region}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      {/* Customer Status Filter */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-2">Customer Status</h4>
        <div className="space-y-2">
          {filterOptions.customerStatus.map(status => (
            <label key={status} className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={filters.customerStatus.includes(status)}
                onChange={(e) => handleFilterChange('customerStatus', status, e.target.checked)}
                className="rounded border-gray-600 bg-gray-700 text-blue-400 focus:ring-blue-400"
              />
              <span className="text-sm text-gray-300">{status}</span>
            </label>
          ))}
        </div>
      </div>

      {/* Alarm Age Date Range Slider */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-2">Alarm Age (Date Range)</h4>
        <div className="px-2">
          <Range
            step={86400000} // 1 day in milliseconds
            min={minTimestamp}
            max={maxTimestamp}
            values={[validStartTimestamp, validEndTimestamp]}
            onChange={handleDateRangeChange}
            renderTrack={({ props, children }) => (
              <div
                {...props}
                className="w-full h-3 bg-gray-600 rounded-full relative"
                style={{
                  ...props.style,
                }}
              >
                <div
                  className="h-3 bg-blue-500 rounded-full absolute"
                  style={{
                    width: `${((validEndTimestamp - validStartTimestamp) / (maxTimestamp - minTimestamp)) * 100}%`,
                    left: `${((validStartTimestamp - minTimestamp) / (maxTimestamp - minTimestamp)) * 100}%`,
                  }}
                />
                {children}
              </div>
            )}
            renderThumb={({ props, index }) => (
              <div
                {...props}
                className="w-6 h-6 bg-blue-400 border-2 border-white rounded-full shadow-lg cursor-pointer hover:bg-blue-300 transition-colors"
                style={{
                  ...props.style,
                }}
              />
            )}
          />
          <div className="flex justify-between mt-3 text-xs">
            <div className="text-gray-400">
              <div className="font-medium">Start</div>
              <div>{formatDateForDisplay(new Date(validStartTimestamp))}</div>
            </div>
            <div className="text-blue-400 text-center">
              <div className="font-medium">End</div>
              <div className="flex items-center space-x-1">
                <span>{formatDateForDisplay(new Date(validEndTimestamp))}</span>
                {validEndTimestamp >= tomorrow.getTime() && (
                  <span className="bg-blue-500 text-white px-1 py-0.5 rounded text-xs font-medium">Now</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex justify-between mt-1 text-xs text-gray-500">
            <span>Oldest Alarm</span>
            <span>Latest Alarm</span>
          </div>
        </div>
      </div>

      {/* No filters available */}
      {Object.values(filterOptions).every(arr => arr.length === 0) && (
        <div className="text-center py-8">
          <Filter className="mx-auto text-gray-500 mb-2" size={24} />
          <p className="text-sm text-gray-500">No filter options available</p>
        </div>
      )}
    </div>
  );
};

export default FilterPanel; 