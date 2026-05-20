import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';

interface Vehicle {
  id: number;
  make: string;
  model: string;
  year: number;
  current_mileage: number;
  fuel_type: string;
}

interface FuelStats {
  average_mpg: number | null;
  total_spent: number;
  entries_count: number;
}

interface MaintenanceStats {
  total_cost: number;
  entries_count: number;
}

interface ActivityItem {
  date: string;
  type: 'fuel' | 'maintenance';
  description: string;
  amount: number;
}

function fmt(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [fuelStats, setFuelStats] = useState<FuelStats | null>(null);
  const [maintenanceStats, setMaintenanceStats] = useState<MaintenanceStats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    apiClient
      .listVehicles()
      .then((data: Vehicle[]) => {
        setVehicles(data);
        if (data.length > 0) setSelectedId(data[0].id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setStatsLoading(true);

    Promise.all([
      apiClient.getFuelStats(selectedId),
      apiClient.getMaintenanceStats(selectedId),
      apiClient.listFuelEntries(selectedId),
      apiClient.listMaintenanceEntries(selectedId),
    ])
      .then(([fuel, maint, fuelEntries, maintEntries]) => {
        setFuelStats(fuel);
        setMaintenanceStats(maint);

        const fuelItems: ActivityItem[] = fuelEntries.slice(0, 5).map((e: any) => ({
          date: e.date,
          type: 'fuel' as const,
          description: `Filled up ${Number(e.gallons).toFixed(1)} gal${e.location ? ` @ ${e.location}` : ''}`,
          amount: e.cost,
        }));
        const maintItems: ActivityItem[] = maintEntries.slice(0, 5).map((e: any) => ({
          date: e.date,
          type: 'maintenance' as const,
          description: `${e.type}${e.service_provider ? ` (${e.service_provider})` : ''}`,
          amount: e.cost,
        }));

        setActivity(
          [...fuelItems, ...maintItems]
            .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
            .slice(0, 5)
        );
      })
      .catch(console.error)
      .finally(() => setStatsLoading(false));
  }, [selectedId]);

  const selectedVehicle = vehicles.find((v) => v.id === selectedId);
  const totalCost = (fuelStats?.total_spent ?? 0) + (maintenanceStats?.total_cost ?? 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-slate-400">Loading...</p>
      </div>
    );
  }

  if (vehicles.length === 0) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-white mb-2">No vehicles yet</h2>
        <p className="text-slate-400 mb-6">Add your first vehicle to get started.</p>
        <button onClick={() => navigate('/vehicles')} className="btn-primary">
          Add Vehicle
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
      </div>

      {/* Vehicle selector */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={selectedId ?? ''}
          onChange={(e) => setSelectedId(Number(e.target.value))}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:border-teal-500"
        >
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.year} {v.make} {v.model}
            </option>
          ))}
        </select>
        <button onClick={() => navigate('/vehicles')} className="btn-secondary text-sm">
          + Add Vehicle
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm mb-1">Current Mileage</p>
          <p className="text-2xl font-bold text-white">
            {selectedVehicle ? selectedVehicle.current_mileage.toLocaleString() : '—'}
          </p>
          <p className="text-slate-500 text-xs mt-1">miles</p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm mb-1">Avg Fuel Economy</p>
          <p className="text-2xl font-bold text-white">
            {statsLoading
              ? '...'
              : fuelStats?.average_mpg != null
              ? fuelStats.average_mpg.toFixed(1)
              : '—'}
          </p>
          <p className="text-slate-500 text-xs mt-1">MPG</p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm mb-1">Total Cost</p>
          <p className="text-2xl font-bold text-white">
            {statsLoading ? '...' : `$${totalCost.toFixed(2)}`}
          </p>
          <p className="text-slate-500 text-xs mt-1">fuel + maintenance</p>
        </div>
      </div>

      {/* Quick actions */}
      <div className="card">
        <p className="text-sm font-medium text-slate-400 mb-3">Quick Actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Log Fuel', tab: 'fuel' },
            { label: 'Log Service', tab: 'maintenance' },
            { label: 'Upload Doc', tab: 'documents' },
            { label: 'View Details', tab: 'summary' },
          ].map(({ label, tab }) => (
            <button
              key={label}
              onClick={() => navigate(`/vehicles/${selectedId}?tab=${tab}`)}
              className="bg-slate-700 hover:bg-slate-600 text-white text-sm py-2.5 px-3 rounded transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Recent activity */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-white">Recent Activity</h2>
          <button
            onClick={() => navigate(`/vehicles/${selectedId}`)}
            className="text-teal-400 hover:text-teal-300 text-sm transition-colors"
          >
            View all →
          </button>
        </div>
        {statsLoading ? (
          <p className="text-slate-400 text-sm">Loading...</p>
        ) : activity.length === 0 ? (
          <p className="text-slate-400 text-sm">
            No activity yet. Start by logging a fuel fill-up or service.
          </p>
        ) : (
          <ul className="divide-y divide-slate-700">
            {activity.map((item, i) => (
              <li key={i} className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      item.type === 'fuel' ? 'bg-teal-500' : 'bg-amber-500'
                    }`}
                  />
                  <div>
                    <p className="text-sm text-white">{item.description}</p>
                    <p className="text-xs text-slate-400">{fmt(item.date)}</p>
                  </div>
                </div>
                <span className="text-sm text-slate-300 ml-4">${Number(item.amount).toFixed(2)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
