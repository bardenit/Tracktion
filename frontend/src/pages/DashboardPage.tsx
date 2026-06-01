import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import VehiclePhoto from '../components/VehiclePhoto';

interface Vehicle {
  id: number;
  nickname?: string;
  vehicle_type: string;
  make: string;
  model: string;
  year: number;
  current_mileage: number;
  fuel_type: string;
  nhtsa_data?: Record<string, unknown>;
  specs_overrides?: Record<string, unknown>;
}

interface TripStats {
  total_miles: number;
  trip_count: number;
  last_trip_date: string | null;
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
  type: 'fuel' | 'maintenance' | 'trip';
  description: string;
  amount: number | null;
}

interface Reminder {
  id: number;
  service_type: string;
  is_overdue: boolean;
  next_due_mileage?: number;
  next_due_date?: string;
  reminder_miles?: number;
  interval_miles?: number;
  interval_days?: number;
}

interface Expense {
  id: number;
  description: string;
  category: string;
  expires_on?: string;
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
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const stored = localStorage.getItem('dashboardVehicleId');
    return stored ? Number(stored) : null;
  });
  const [fuelStats, setFuelStats] = useState<FuelStats | null>(null);
  const [tripStats, setTripStats] = useState<TripStats | null>(null);
  const [maintenanceStats, setMaintenanceStats] = useState<MaintenanceStats | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [markDoneReminder, setMarkDoneReminder] = useState<Reminder | null>(null);
  const [markDoneForm, setMarkDoneForm] = useState({ date: '', mileage: 0, cost: 0, notes: '' });
  const [markDoneSaving, setMarkDoneSaving] = useState(false);
  const markDoneRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    apiClient
      .listVehicles()
      .then((data: Vehicle[]) => {
        setVehicles(data);
        if (data.length > 0) {
          const stored = localStorage.getItem('dashboardVehicleId');
          const storedId = stored ? Number(stored) : null;
          const valid = storedId && data.some((v: Vehicle) => v.id === storedId);
          setSelectedId(valid ? storedId : data[0].id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    const vehicle = vehicles.find((v) => v.id === selectedId);
    if (!vehicle) return;

    setStatsLoading(true);
    const isTrailer = vehicle.vehicle_type === 'trailer';

    // Always load reminders and expenses for alerts
    apiClient.listMaintenanceReminders(selectedId).then(setReminders).catch(console.error);
    apiClient.listExpenses(selectedId).then(setExpenses).catch(console.error);

    if (isTrailer) {
      Promise.all([
        apiClient.getTripStats(selectedId),
        apiClient.getMaintenanceStats(selectedId),
        apiClient.listTrips(selectedId),
        apiClient.listMaintenanceEntries(selectedId),
      ])
        .then(([trips, maint, tripEntries, maintEntries]) => {
          setTripStats(trips);
          setFuelStats(null);
          setMaintenanceStats(maint);

          const tripItems: ActivityItem[] = tripEntries.slice(0, 5).map((e: any) => ({
            date: e.date,
            type: 'trip' as const,
            description: `${Number(e.miles).toLocaleString()} mi${e.destination ? ` — ${e.destination}` : ''}`,
            amount: null,
          }));
          const maintItems: ActivityItem[] = maintEntries.slice(0, 5).map((e: any) => ({
            date: e.date,
            type: 'maintenance' as const,
            description: `${e.type}${e.service_provider ? ` (${e.service_provider})` : ''}`,
            amount: e.cost,
          }));

          setActivity(
            [...tripItems, ...maintItems]
              .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
              .slice(0, 5)
          );
        })
        .catch(console.error)
        .finally(() => setStatsLoading(false));
    } else {
      Promise.all([
        apiClient.getFuelStats(selectedId),
        apiClient.getMaintenanceStats(selectedId),
        apiClient.listFuelEntries(selectedId),
        apiClient.listMaintenanceEntries(selectedId),
      ])
        .then(([fuel, maint, fuelEntries, maintEntries]) => {
          setFuelStats(fuel);
          setTripStats(null);
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
    }
  }, [selectedId, vehicles]);

  const selectedVehicle = vehicles.find((v) => v.id === selectedId);
  const isTrailer = selectedVehicle?.vehicle_type === 'trailer';
  const totalCost = (isTrailer ? 0 : (fuelStats?.total_spent ?? 0)) + (maintenanceStats?.total_cost ?? 0);

  const openMarkDone = (r: Reminder) => {
    const todayStr = new Date().toISOString().split('T')[0];
    setMarkDoneReminder(r);
    setMarkDoneForm({ date: todayStr, mileage: selectedVehicle?.current_mileage ?? 0, cost: 0, notes: '' });
    markDoneRef.current?.showModal();
  };

  const saveMarkDone = async () => {
    if (!markDoneReminder || !selectedId) return;
    setMarkDoneSaving(true);
    try {
      await apiClient.createMaintenanceEntry(selectedId, {
        date: markDoneForm.date,
        mileage: markDoneForm.mileage,
        type: markDoneReminder.service_type,
        cost: markDoneForm.cost,
        notes: markDoneForm.notes || undefined,
      });
      const todayStr = markDoneForm.date;
      const update: Record<string, unknown> = {
        last_performed_mileage: markDoneForm.mileage,
        last_performed_date: todayStr,
      };
      if (markDoneReminder.interval_miles) update.next_due_mileage = markDoneForm.mileage + markDoneReminder.interval_miles;
      if (markDoneReminder.interval_days) {
        const d = new Date(todayStr + 'T00:00:00');
        d.setDate(d.getDate() + markDoneReminder.interval_days);
        update.next_due_date = d.toISOString().split('T')[0];
      }
      await apiClient.updateMaintenanceReminder(selectedId, markDoneReminder.id, update);
      apiClient.listMaintenanceReminders(selectedId).then(setReminders).catch(console.error);
      markDoneRef.current?.close();
      setMarkDoneReminder(null);
    } catch (err) {
      console.error(err);
    } finally {
      setMarkDoneSaving(false);
    }
  };

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
          onChange={(e) => {
            const id = Number(e.target.value);
            setSelectedId(id);
            localStorage.setItem('dashboardVehicleId', String(id));
          }}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:border-teal-500"
        >
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>
              {v.nickname || `${v.year} ${v.make} ${v.model}`}
            </option>
          ))}
        </select>
        <button onClick={() => navigate('/vehicles')} className="btn-secondary text-sm">
          + Add Vehicle
        </button>
      </div>

      {/* Vehicle photo */}
      {selectedId && (
        <VehiclePhoto vehicleId={selectedId} className="w-full h-auto" />
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm mb-1">Current Mileage</p>
          <p className="text-2xl font-bold text-white">
            {selectedVehicle ? selectedVehicle.current_mileage.toLocaleString() : '—'}
          </p>
          <p className="text-slate-500 text-xs mt-1">miles</p>
        </div>
        {isTrailer ? (
          <div className="card">
            <p className="text-slate-400 text-sm mb-1">Miles Hauled</p>
            <p className="text-2xl font-bold text-white">
              {statsLoading ? '...' : (tripStats?.total_miles ?? 0).toLocaleString()}
            </p>
            <p className="text-slate-500 text-xs mt-1">{tripStats?.trip_count ?? 0} trips</p>
          </div>
        ) : (
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
        )}
        <div className="card">
          <p className="text-slate-400 text-sm mb-1">Total Cost</p>
          <p className="text-2xl font-bold text-white">
            {statsLoading ? '...' : `$${totalCost.toFixed(2)}`}
          </p>
          <p className="text-slate-500 text-xs mt-1">{isTrailer ? 'maintenance' : 'fuel + maintenance'}</p>
        </div>
      </div>

      {/* Alerts */}
      {(() => {
        const overdueReminders = reminders.filter((r) => r.is_overdue);
        const upcomingReminders = reminders.filter((r) => {
          if (r.is_overdue) return false;
          if (r.next_due_mileage && selectedVehicle) {
            const left = r.next_due_mileage - selectedVehicle.current_mileage;
            return left >= 0 && left <= (r.reminder_miles ?? 500);
          }
          if (r.next_due_date) {
            const daysLeft = Math.ceil((new Date(r.next_due_date + 'T00:00:00').getTime() - Date.now()) / 86400000);
            return daysLeft >= 0 && daysLeft <= 14;
          }
          return false;
        });
        const expiringExpenses = expenses.filter((e) => {
          if (!e.expires_on) return false;
          const daysLeft = Math.ceil((new Date(e.expires_on + 'T00:00:00').getTime() - Date.now()) / 86400000);
          return daysLeft <= 30;
        });
        const reminderAlerts = [
          ...overdueReminders.map((r) => ({ level: 'red' as const, text: `${r.service_type} is overdue`, tab: 'maintenance', reminder: r as Reminder | null })),
          ...upcomingReminders.map((r) => ({ level: 'amber' as const, text: `${r.service_type} coming up soon`, tab: 'maintenance', reminder: r as Reminder | null })),
        ];
        const expenseAlerts = expiringExpenses.map((e) => {
          const days = Math.ceil((new Date(e.expires_on! + 'T00:00:00').getTime() - Date.now()) / 86400000);
          return { level: days < 0 ? 'red' as const : 'amber' as const, text: days < 0 ? `${e.description} has expired` : `${e.description} expires in ${days} day${days === 1 ? '' : 's'}`, tab: 'expenses', reminder: null as Reminder | null };
        });
        const alerts = [...reminderAlerts, ...expenseAlerts];
        if (alerts.length === 0) return null;
        return (
          <div className="space-y-2">
            {alerts.map((a, i) => (
              <div key={i} className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm ${
                  a.level === 'red'
                    ? 'bg-red-900/20 border-red-700/50 text-red-300'
                    : 'bg-amber-900/20 border-amber-700/50 text-amber-300'
                }`}>
                <span className="flex-shrink-0">{a.level === 'red' ? '⚠' : '!'}</span>
                <span className="flex-1">{a.text}</span>
                {a.reminder && (
                  <button onClick={() => openMarkDone(a.reminder!)}
                    className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded transition-colors flex-shrink-0">
                    Mark Done
                  </button>
                )}
                <button onClick={() => navigate(`/vehicles/${selectedId}?tab=${a.tab}`)}
                  className="text-xs opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">
                  View →
                </button>
              </div>
            ))}
          </div>
        );
      })()}

      {/* Quick actions */}
      <div className="card">
        <p className="text-sm font-medium text-slate-400 mb-3">Quick Actions</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {(isTrailer
            ? [
                { label: 'Log Trip', tab: 'trips' },
                { label: 'Log Service', tab: 'maintenance' },
                { label: 'Upload Doc', tab: 'documents' },
                { label: 'View Details', tab: 'summary' },
              ]
            : [
                { label: 'Log Fuel', tab: 'fuel' },
                { label: 'Log Service', tab: 'maintenance' },
                { label: 'Upload Doc', tab: 'documents' },
                { label: 'View Details', tab: 'summary' },
              ]
          ).map(({ label, tab }) => (
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
            {isTrailer
              ? 'No activity yet. Start by logging a trip or service.'
              : 'No activity yet. Start by logging a fuel fill-up or service.'}
          </p>
        ) : (
          <ul className="divide-y divide-slate-700">
            {activity.map((item, i) => (
              <li key={i} className="py-3 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      item.type === 'fuel' ? 'bg-teal-500' :
                      item.type === 'trip' ? 'bg-blue-500' :
                      'bg-amber-500'
                    }`}
                  />
                  <div>
                    <p className="text-sm text-white">{item.description}</p>
                    <p className="text-xs text-slate-400">{fmt(item.date)}</p>
                  </div>
                </div>
                {item.amount != null && (
                  <span className="text-sm text-slate-300 ml-4">${Number(item.amount).toFixed(2)}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Mark Done dialog */}
      <dialog ref={markDoneRef} className="rounded-xl bg-slate-800 border border-slate-700 p-6 w-full max-w-sm shadow-xl text-white backdrop:bg-black/60" onClose={() => setMarkDoneReminder(null)}>
        {markDoneReminder && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Mark Done — {markDoneReminder.service_type}</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-slate-300 mb-1">Date *</label>
                <input type="date" className="input-field" value={markDoneForm.date}
                  onChange={(e) => setMarkDoneForm((p) => ({ ...p, date: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Mileage *</label>
                <input type="number" className="input-field" min="0" value={markDoneForm.mileage}
                  onChange={(e) => setMarkDoneForm((p) => ({ ...p, mileage: Number(e.target.value) }))} />
              </div>
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">Cost ($)</label>
              <input type="number" className="input-field" min="0" step="0.01" value={markDoneForm.cost}
                onChange={(e) => setMarkDoneForm((p) => ({ ...p, cost: Number(e.target.value) }))} />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">Notes</label>
              <input className="input-field" value={markDoneForm.notes}
                onChange={(e) => setMarkDoneForm((p) => ({ ...p, notes: e.target.value }))} />
            </div>
            <div className="flex gap-3">
              <button onClick={saveMarkDone} disabled={markDoneSaving}
                className="btn-primary flex-1">{markDoneSaving ? 'Saving...' : 'Save'}</button>
              <button onClick={() => markDoneRef.current?.close()} className="btn-secondary flex-1">Cancel</button>
            </div>
          </div>
        )}
      </dialog>
    </div>
  );
}
