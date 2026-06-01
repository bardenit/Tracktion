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

interface FuelEntry {
  date: string;
  mileage: number;
  cost: number;
  gallons: number;
  cost_per_mile?: number;
}

interface TripEntry {
  date: string;
  miles: number;
}

function fmt(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function avgDailyMiles(entries: FuelEntry[]): number | null {
  if (entries.length < 2) return null;
  const sorted = [...entries].sort((a, b) => a.date.localeCompare(b.date));
  const first = sorted[0]; const last = sorted[sorted.length - 1];
  const days = (new Date(last.date).getTime() - new Date(first.date).getTime()) / 86400000;
  if (days <= 0) return null;
  return (last.mileage - first.mileage) / days;
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
  const [allFuelEntries, setAllFuelEntries] = useState<FuelEntry[]>([]);
  const [allTripEntries, setAllTripEntries] = useState<TripEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [markDoneReminder, setMarkDoneReminder] = useState<Reminder | null>(null);
  const [markDoneForm, setMarkDoneForm] = useState({ date: '', mileage: 0, cost: 0, notes: '' });
  const [markDoneSaving, setMarkDoneSaving] = useState(false);
  const markDoneRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    apiClient.listVehicles()
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

    apiClient.listMaintenanceReminders(selectedId).then(setReminders).catch(console.error);
    apiClient.listExpenses(selectedId).then(setExpenses).catch(console.error);

    if (isTrailer) {
      Promise.all([
        apiClient.getTripStats(selectedId),
        apiClient.getMaintenanceStats(selectedId),
        apiClient.listTrips(selectedId),
        apiClient.listMaintenanceEntries(selectedId),
      ]).then(([trips, maint, tripEntries, maintEntries]) => {
        setTripStats(trips);
        setFuelStats(null);
        setMaintenanceStats(maint);
        setAllTripEntries(tripEntries);
        setAllFuelEntries([]);
        const tripItems: ActivityItem[] = tripEntries.slice(0, 5).map((e: any) => ({
          date: e.date, type: 'trip' as const,
          description: `${Number(e.miles).toLocaleString()} mi${e.destination ? ` — ${e.destination}` : ''}`,
          amount: null,
        }));
        const maintItems: ActivityItem[] = maintEntries.slice(0, 5).map((e: any) => ({
          date: e.date, type: 'maintenance' as const,
          description: `${e.type}${e.service_provider ? ` (${e.service_provider})` : ''}`,
          amount: e.cost,
        }));
        setActivity([...tripItems, ...maintItems].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).slice(0, 5));
      }).catch(console.error).finally(() => setStatsLoading(false));
    } else {
      Promise.all([
        apiClient.getFuelStats(selectedId),
        apiClient.getMaintenanceStats(selectedId),
        apiClient.listFuelEntries(selectedId),
        apiClient.listMaintenanceEntries(selectedId),
      ]).then(([fuel, maint, fuelEntries, maintEntries]) => {
        setFuelStats(fuel);
        setTripStats(null);
        setMaintenanceStats(maint);
        setAllFuelEntries(fuelEntries);
        setAllTripEntries([]);
        const fuelItems: ActivityItem[] = fuelEntries.slice(0, 5).map((e: any) => ({
          date: e.date, type: 'fuel' as const,
          description: `Filled up ${Number(e.gallons).toFixed(1)} gal${e.location ? ` @ ${e.location}` : ''}`,
          amount: e.cost,
        }));
        const maintItems: ActivityItem[] = maintEntries.slice(0, 5).map((e: any) => ({
          date: e.date, type: 'maintenance' as const,
          description: `${e.type}${e.service_provider ? ` (${e.service_provider})` : ''}`,
          amount: e.cost,
        }));
        setActivity([...fuelItems, ...maintItems].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()).slice(0, 5));
      }).catch(console.error).finally(() => setStatsLoading(false));
    }
  }, [selectedId, vehicles]);

  const selectedVehicle = vehicles.find((v) => v.id === selectedId);
  const isTrailer = selectedVehicle?.vehicle_type === 'trailer';

  // This-month cost
  const thisMonth = new Date().toISOString().slice(0, 7);
  const monthFuelCost = allFuelEntries.filter((e) => e.date.startsWith(thisMonth)).reduce((s, e) => s + Number(e.cost), 0);
  const monthMaintCost = 0; // maintenance entries not stored separately; skip for now

  // Avg daily miles for projection
  const dailyMiles = isTrailer
    ? (allTripEntries.length >= 2 ? (() => {
        const sorted = [...allTripEntries].sort((a, b) => a.date.localeCompare(b.date));
        const days = (new Date(sorted[sorted.length - 1].date).getTime() - new Date(sorted[0].date).getTime()) / 86400000;
        return days > 0 ? allTripEntries.reduce((s, t) => s + t.miles, 0) / days : null;
      })() : null)
    : avgDailyMiles(allFuelEntries);

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
        date: markDoneForm.date, mileage: markDoneForm.mileage,
        type: markDoneReminder.service_type, cost: markDoneForm.cost,
        notes: markDoneForm.notes || undefined,
      });
      const update: Record<string, unknown> = {
        last_performed_mileage: markDoneForm.mileage,
        last_performed_date: markDoneForm.date,
      };
      if (markDoneReminder.interval_miles) update.next_due_mileage = markDoneForm.mileage + markDoneReminder.interval_miles;
      if (markDoneReminder.interval_days) {
        const d = new Date(markDoneForm.date + 'T00:00:00');
        d.setDate(d.getDate() + markDoneReminder.interval_days);
        update.next_due_date = d.toISOString().split('T')[0];
      }
      await apiClient.updateMaintenanceReminder(selectedId, markDoneReminder.id, update);
      apiClient.listMaintenanceReminders(selectedId).then(setReminders).catch(console.error);
      markDoneRef.current?.close();
      setMarkDoneReminder(null);
    } catch (err) { console.error(err); }
    finally { setMarkDoneSaving(false); }
  };

  if (loading) return <div className="flex items-center justify-center py-20"><p className="text-slate-400">Loading...</p></div>;

  if (vehicles.length === 0) {
    return (
      <div className="text-center py-20">
        <h2 className="text-xl font-semibold text-white mb-2">No vehicles yet</h2>
        <p className="text-slate-400 mb-6">Add your first vehicle to get started.</p>
        <button onClick={() => navigate('/vehicles')} className="btn-primary">Add Vehicle</button>
      </div>
    );
  }

  // Alerts
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
    return Math.ceil((new Date(e.expires_on + 'T00:00:00').getTime() - Date.now()) / 86400000) <= 30;
  });
  const hasAlerts = overdueReminders.length > 0 || upcomingReminders.length > 0 || expiringExpenses.length > 0;

  return (
    <div className="space-y-5">
      {/* Vehicle selector */}
      <div className="flex items-center justify-between gap-3">
        <select
          value={selectedId ?? ''}
          onChange={(e) => { const id = Number(e.target.value); setSelectedId(id); localStorage.setItem('dashboardVehicleId', String(id)); }}
          className="bg-slate-800 border border-slate-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:border-teal-500 flex-1 min-w-0"
        >
          {vehicles.map((v) => (
            <option key={v.id} value={v.id}>{v.nickname || `${v.year} ${v.make} ${v.model}`}</option>
          ))}
        </select>
        <button onClick={() => navigate('/vehicles')} className="btn-secondary text-sm whitespace-nowrap">+ Add Vehicle</button>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="card py-3">
          <p className="text-slate-400 text-xs mb-1">{isTrailer ? 'Miles Hauled' : 'Current Mileage'}</p>
          <p className="text-xl font-bold text-white">
            {statsLoading ? '...' : isTrailer
              ? (tripStats?.total_miles ?? 0).toLocaleString()
              : (selectedVehicle?.current_mileage ?? 0).toLocaleString()}
          </p>
          <p className="text-slate-500 text-xs mt-0.5">{isTrailer ? `${tripStats?.trip_count ?? 0} trips` : 'miles'}</p>
        </div>

        {isTrailer ? (
          <div className="card py-3">
            <p className="text-slate-400 text-xs mb-1">Last Trip</p>
            <p className="text-xl font-bold text-white">
              {statsLoading ? '...' : tripStats?.last_trip_date ? fmt(tripStats.last_trip_date) : '—'}
            </p>
            <p className="text-slate-500 text-xs mt-0.5">date</p>
          </div>
        ) : (
          <div className="card py-3">
            <p className="text-slate-400 text-xs mb-1">Avg Fuel Economy</p>
            <p className="text-xl font-bold text-white">
              {statsLoading ? '...' : fuelStats?.average_mpg != null ? fuelStats.average_mpg.toFixed(1) : '—'}
            </p>
            <p className="text-slate-500 text-xs mt-0.5">MPG</p>
          </div>
        )}

        <div className="card py-3">
          <p className="text-slate-400 text-xs mb-1">This Month</p>
          <p className="text-xl font-bold text-white">
            {statsLoading ? '...' : `$${(monthFuelCost + monthMaintCost).toFixed(0)}`}
          </p>
          <p className="text-slate-500 text-xs mt-0.5">{isTrailer ? 'maintenance' : 'fuel cost'}</p>
        </div>

        <div className="card py-3">
          <p className="text-slate-400 text-xs mb-1">Maint. Total</p>
          <p className="text-xl font-bold text-white">
            {statsLoading ? '...' : `$${(maintenanceStats?.total_cost ?? 0).toFixed(0)}`}
          </p>
          <p className="text-slate-500 text-xs mt-0.5">all time</p>
        </div>
      </div>

      {/* ── Vehicle photo ── */}
      {selectedId && <VehiclePhoto vehicleId={selectedId} className="w-full h-auto rounded-xl" />}

      {/* ── Alerts ── */}
      {hasAlerts && (
        <div className="space-y-2">
          {overdueReminders.map((r) => {
            const projDays = dailyMiles && r.next_due_mileage && selectedVehicle
              ? Math.round((r.next_due_mileage - selectedVehicle.current_mileage) / dailyMiles)
              : null;
            return (
              <div key={r.id} className="flex items-center gap-2 px-4 py-3 rounded-lg border bg-red-900/20 border-red-700/50 text-red-300 text-sm">
                <span className="flex-shrink-0">⚠</span>
                <span className="flex-1">
                  {r.service_type} is overdue
                  {projDays != null && projDays < 0 && <span className="text-xs opacity-70 ml-1">({Math.abs(projDays)} days past est.)</span>}
                </span>
                <button onClick={() => openMarkDone(r)} className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded transition-colors flex-shrink-0">Mark Done</button>
                <button onClick={() => navigate(`/vehicles/${selectedId}?tab=maintenance`)} className="text-xs opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">View →</button>
              </div>
            );
          })}
          {upcomingReminders.map((r) => {
            const projDays = dailyMiles && r.next_due_mileage && selectedVehicle
              ? Math.round((r.next_due_mileage - selectedVehicle.current_mileage) / dailyMiles)
              : r.next_due_date
              ? Math.ceil((new Date(r.next_due_date + 'T00:00:00').getTime() - Date.now()) / 86400000)
              : null;
            return (
              <div key={r.id} className="flex items-center gap-2 px-4 py-3 rounded-lg border bg-amber-900/20 border-amber-700/50 text-amber-300 text-sm">
                <span className="flex-shrink-0">!</span>
                <span className="flex-1">
                  {r.service_type} coming up soon
                  {projDays != null && projDays >= 0 && <span className="text-xs opacity-70 ml-1">(≈ {projDays} day{projDays === 1 ? '' : 's'})</span>}
                </span>
                <button onClick={() => openMarkDone(r)} className="text-xs bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded transition-colors flex-shrink-0">Mark Done</button>
                <button onClick={() => navigate(`/vehicles/${selectedId}?tab=maintenance`)} className="text-xs opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">View →</button>
              </div>
            );
          })}
          {expiringExpenses.map((e) => {
            const days = Math.ceil((new Date(e.expires_on! + 'T00:00:00').getTime() - Date.now()) / 86400000);
            return (
              <div key={e.id} className={`flex items-center gap-2 px-4 py-3 rounded-lg border text-sm ${days < 0 ? 'bg-red-900/20 border-red-700/50 text-red-300' : 'bg-amber-900/20 border-amber-700/50 text-amber-300'}`}>
                <span className="flex-shrink-0">{days < 0 ? '⚠' : '!'}</span>
                <span className="flex-1">{days < 0 ? `${e.description} has expired` : `${e.description} expires in ${days} day${days === 1 ? '' : 's'}`}</span>
                <button onClick={() => navigate(`/vehicles/${selectedId}?tab=expenses`)} className="text-xs opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">View →</button>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Quick actions ── */}
      <div className="grid grid-cols-4 gap-2">
        {(isTrailer
          ? [{ label: 'Log Trip', tab: 'trips' }, { label: 'Log Service', tab: 'maintenance' }, { label: 'Inspect', tab: 'inspect' }, { label: 'Details', tab: 'summary' }]
          : [{ label: 'Log Fuel', tab: 'fuel' }, { label: 'Log Service', tab: 'maintenance' }, { label: 'Inspect', tab: 'inspect' }, { label: 'Details', tab: 'summary' }]
        ).map(({ label, tab }) => (
          <button key={label} onClick={() => navigate(`/vehicles/${selectedId}?tab=${tab}`)}
            className="bg-slate-700 hover:bg-slate-600 text-white text-sm py-3 px-2 rounded-lg transition-colors text-center leading-tight">
            {label}
          </button>
        ))}
      </div>

      {/* ── Recent activity ── */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-white text-sm">Recent Activity</h2>
          <button onClick={() => navigate(`/vehicles/${selectedId}`)} className="text-teal-400 hover:text-teal-300 text-xs transition-colors">View all →</button>
        </div>
        {statsLoading ? (
          <p className="text-slate-400 text-sm">Loading...</p>
        ) : activity.length === 0 ? (
          <p className="text-slate-400 text-sm">{isTrailer ? 'No activity yet. Log a trip or service.' : 'No activity yet. Log a fill-up or service.'}</p>
        ) : (
          <ul className="divide-y divide-slate-700">
            {activity.map((item, i) => (
              <li key={i} className="py-2.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${item.type === 'fuel' ? 'bg-teal-500' : item.type === 'trip' ? 'bg-blue-500' : 'bg-amber-500'}`} />
                  <div>
                    <p className="text-sm text-white">{item.description}</p>
                    <p className="text-xs text-slate-400">{fmt(item.date)}</p>
                  </div>
                </div>
                {item.amount != null && <span className="text-sm text-slate-300 ml-4">${Number(item.amount).toFixed(2)}</span>}
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
              <button onClick={saveMarkDone} disabled={markDoneSaving} className="btn-primary flex-1">{markDoneSaving ? 'Saving...' : 'Save'}</button>
              <button onClick={() => markDoneRef.current?.close()} className="btn-secondary flex-1">Cancel</button>
            </div>
          </div>
        )}
      </dialog>
    </div>
  );
}
