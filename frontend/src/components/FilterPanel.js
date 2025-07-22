import React, { useMemo } from 'react';
import { Filter, X } from 'lucide-react';



const FilterPanel = ({ alarms, filters, setFilters }) => {

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



  const clearFilters = () => {
    setFilters({
      severity: [],
      deviceType: [],
      category: [],
      region: [],
      customerStatus: ['Customer Associated'],
      alarmAge: 'all'
    });
  };

  const hasActiveFilters = Object.entries(filters).some(([key, value]) => {
    if (key === 'customerStatus') {
      // Only consider it active if it's not just the default "Customer Associated"
      return Array.isArray(value) && value.length > 0 && 
             !(value.length === 1 && value[0] === 'Customer Associated');
    }
    if (key === 'alarmAge') {
      return value && value !== 'all';
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

      {/* Alarm Age Filter */}
      <div>
        <h4 className="text-xs font-medium text-gray-400 mb-2">Alarm Age</h4>
        <select
          value={filters.alarmAge || 'all'}
          onChange={(e) => setFilters(prev => ({ ...prev, alarmAge: e.target.value }))}
          className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-md text-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 focus:border-transparent"
        >
          <option value="all">Show All</option>
          <option value="1h">Past 1 hour</option>
          <option value="12h">Past 12 hours</option>
          <option value="24h">Past 24 hours</option>
          <option value="7d">Past 7 days</option>
          <option value="30d">Past 30 days</option>
        </select>
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