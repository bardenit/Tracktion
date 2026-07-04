import { useEffect, useState, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import VehiclePhoto from '../components/VehiclePhoto';
import type { Vehicle, Reminder, Expense, VehicleCosts } from '../types';

interface FuelStats {
  average_mpg: number | null;
  total_spent: number;
  entries_count: number;
  miles_per_day: number | null;
}

interface Alert {
  level: 'red' | 'amber';
  text: string;
  reminder: Reminder | null;
  tab: string;
}

interface RecallStatus {
  available: boolean;
  new_count: number;
  new_recalls: { campaign_number?: string; component?: string }[];
}

interface VehicleCardData {
  fuelStats: FuelStats | null;
  reminders: Reminder[];
  expenses: Expense[];
  costs: VehicleCosts | null;
  recallStatus: RecallStatus | null;
  loading: boolean;
}

function vehicleLabel(v: Vehicle) {
  return v.nickname || `${v.year} ${v.make} ${v.model}`;
}

function computeAlerts(vehicle: Vehicle, reminders: Reminder[], expenses: Expense[], milesPerDay: number | null = null, recallStatus: RecallStatus | null = null): Alert[] {
  const alerts: Alert[] = [];
  if (recallStatus?.available && recallStatus.new_count > 0) {
    for (const r of recallStatus.new_recalls) {
      alerts.push({
        level: 'red',
        text: `New safety recall: ${r.component || 'see NHTSA tab'}`,
        reminder: null,
        tab: 'nhtsa',
      });
    }
  }
  for (const r of reminders) {
    if (r.is_overdue) {
      alerts.push({ level: 'red', text: `${r.service_type} overdue`, reminder: r, tab: 'maintenance' });
      continue;
    }
    let upcoming = false;
    let projectedDays: number | null = null;
    if (r.next_due_mileage) {
      const left = r.next_due_mileage - vehicle.current_mileage;
      if (left >= 0 && left <= (r.reminder_miles ?? 500)) upcoming = true;
      // Project mileage-based reminders into days using average daily miles
      if (left > 0 && milesPerDay && milesPerDay > 0) {
        const days = Math.round(left / milesPerDay);
        if (days <= 14) { upcoming = true; projectedDays = days; }
      }
    }
    if (r.next_due_date) {
      const days = Math.ceil((new Date(r.next_due_date + 'T00:00:00').getTime() - Date.now()) / 86400000);
      if (days >= 0 && days <= 14) upcoming = true;
    }
    if (upcoming) {
      const text = projectedDays !== null
        ? `${r.service_type} due in ~${projectedDays}d`
        : `${r.service_type} due soon`;
      alerts.push({ level: 'amber', text, reminder: r, tab: 'maintenance' });
    }
  }
  for (const e of expenses) {
    if (!e.expires_on) continue;
    const days = Math.ceil((new Date(e.expires_on + 'T00:00:00').getTime() - Date.now()) / 86400000);
    if (days <= 30) {
      alerts.push({
        level: days < 0 ? 'red' : 'amber',
        text: days < 0 ? `${e.description} expired` : `${e.description} expires in ${days}d`,
        reminder: null,
        tab: 'expenses',
      });
    }
  }
  return alerts;
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [cardData, setCardData] = useState<Record<number, VehicleCardData>>({});
  const [loading, setLoading] = useState(true);
  const [markDoneReminder, setMarkDoneReminder] = useState<Reminder | null>(null);
  const [markDoneVehicleId, setMarkDoneVehicleId] = useState<number | null>(null);
  const [markDoneVehicle, setMarkDoneVehicle] = useState<Vehicle | null>(null);
  const [markDoneForm, setMarkDoneForm] = useState({ date: '', mileage: 0, cost: 0, notes: '' });
  const [markDoneSaving, setMarkDoneSaving] = useState(false);
  const dialogRef = useRef<HTMLDialogElement>(null);

  const loadVehicleData = useCallback(async (vehicle: Vehicle) => {
    setCardData((prev) => ({ ...prev, [vehicle.id]: { ...(prev[vehicle.id] ?? { fuelStats: null, reminders: [], expenses: [], costs: null, recallStatus: null }), loading: true } }));
    try {
      const [reminders, expenses, fuelStats, costs, recallStatus] = await Promise.all([
        apiClient.listMaintenanceReminders(vehicle.id),
        apiClient.listExpenses(vehicle.id),
        vehicle.vehicle_type !== 'trailer' ? apiClient.getFuelStats(vehicle.id) : Promise.resolve(null),
        vehicle.vehicle_type !== 'trailer' ? apiClient.getVehicleCosts(vehicle.id).catch(() => null) : Promise.resolve(null),
        vehicle.vehicle_type !== 'trailer' ? apiClient.getRecallStatus(vehicle.id).catch(() => null) : Promise.resolve(null),
      ]);
      setCardData((prev) => ({ ...prev, [vehicle.id]: { fuelStats, reminders, expenses, costs, recallStatus, loading: false } }));
    } catch {
      setCardData((prev) => ({ ...prev, [vehicle.id]: { fuelStats: null, reminders: [], expenses: [], costs: null, recallStatus: null, loading: false } }));
    }
  }, []);

  useEffect(() => {
    apiClient.listVehicles()
      .then((data: Vehicle[]) => {
        setVehicles(data);
        data.forEach((v) => loadVehicleData(v));
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [loadVehicleData]);

  const openMarkDone = (vehicle: Vehicle, reminder: Reminder) => {
    setMarkDoneVehicleId(vehicle.id);
    setMarkDoneVehicle(vehicle);
    setMarkDoneReminder(reminder);
    setMarkDoneForm({ date: new Date().toISOString().split('T')[0], mileage: vehicle.current_mileage, cost: 0, notes: '' });
    dialogRef.current?.showModal();
  };

  const saveMarkDone = async () => {
    if (!markDoneReminder || !markDoneVehicleId) return;
    setMarkDoneSaving(true);
    try {
      await apiClient.createMaintenanceEntry(markDoneVehicleId, {
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
      await apiClient.updateMaintenanceReminder(markDoneVehicleId, markDoneReminder.id, update);
      // Refresh this vehicle's data
      const v = vehicles.find((x) => x.id === markDoneVehicleId);
      if (v) loadVehicleData(v);
      dialogRef.current?.close();
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

  // Filter: show all non-trailers; show trailers only if they have alerts
  const visibleVehicles = vehicles.filter((v) => {
    if (v.vehicle_type !== 'trailer') return true;
    const data = cardData[v.id];
    if (!data || data.loading) return false;
    return computeAlerts(v, data.reminders, data.expenses, data.fuelStats?.miles_per_day ?? null, data.recallStatus).length > 0;
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Dashboard</h1>
        <button onClick={() => navigate('/vehicles')} className="btn-secondary text-sm">+ Add Vehicle</button>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {visibleVehicles.map((vehicle) => {
          const data = cardData[vehicle.id];
          const isTrailer = vehicle.vehicle_type === 'trailer';
          const alerts = data && !data.loading ? computeAlerts(vehicle, data.reminders, data.expenses, data.fuelStats?.miles_per_day ?? null, data.recallStatus) : [];
          const hasAlerts = alerts.length > 0;

          return (
            <div key={vehicle.id} className={`card space-y-4 border ${hasAlerts ? 'border-slate-600' : 'border-slate-700/50'}`}>
              {/* Header row */}
              <div className="flex items-start gap-4">
                {/* Photo thumbnail */}
                <div className="w-20 h-16 flex-shrink-0 rounded-lg overflow-hidden bg-slate-700">
                  <VehiclePhoto vehicleId={vehicle.id} className="w-full h-full object-cover" />
                </div>

                {/* Title + stats */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="font-semibold text-white truncate">{vehicleLabel(vehicle)}</h2>
                    {isTrailer && (
                      <span className="text-xs bg-amber-900/50 text-amber-300 border border-amber-700/50 px-1.5 py-0.5 rounded flex-shrink-0">Trailer</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <span className="text-sm text-slate-400">
                      {vehicle.current_mileage.toLocaleString()} mi
                    </span>
                    {!isTrailer && (
                      <span className="text-sm text-slate-400">
                        {data?.loading ? '...' : data?.fuelStats?.average_mpg != null
                          ? `${Number(data.fuelStats.average_mpg).toFixed(1)} MPG`
                          : 'No fuel data'}
                      </span>
                    )}
                    {!isTrailer && data?.fuelStats && (
                      <span className="text-sm text-slate-400">
                        ${Number(data.fuelStats.total_spent).toFixed(0)} spent
                      </span>
                    )}
                    {!isTrailer && data?.costs?.cost_per_mile != null && (
                      <span className="text-sm text-slate-400">
                        ${data.costs.cost_per_mile.toFixed(2)}/mi
                      </span>
                    )}
                  </div>
                </div>

                {/* Details link */}
                <button
                  onClick={() => navigate(`/vehicles/${vehicle.id}`)}
                  className="text-teal-400 hover:text-teal-300 text-sm transition-colors flex-shrink-0"
                >
                  Details →
                </button>
              </div>

              {/* Alerts */}
              {hasAlerts && (
                <div className="space-y-1.5">
                  {alerts.map((a, i) => (
                    <div key={i} className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs ${
                      a.level === 'red'
                        ? 'bg-red-900/20 border border-red-700/40 text-red-300'
                        : 'bg-amber-900/20 border border-amber-700/40 text-amber-300'
                    }`}>
                      <span className="flex-shrink-0">{a.level === 'red' ? '⚠' : '!'}</span>
                      <span className="flex-1">{a.text}</span>
                      {a.reminder && (
                        <button
                          onClick={() => openMarkDone(vehicle, a.reminder!)}
                          className="bg-slate-700 hover:bg-slate-600 text-white px-2 py-0.5 rounded transition-colors flex-shrink-0"
                        >
                          Mark Done
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/vehicles/${vehicle.id}?tab=${a.tab}`)}
                        className="opacity-60 hover:opacity-100 transition-opacity flex-shrink-0"
                      >
                        View →
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {/* Quick actions — vehicles only (trailers only shown when they have alerts, no need for clutter) */}
              {!isTrailer && (
                <div className="flex gap-2">
                  <button onClick={() => navigate(`/vehicles/${vehicle.id}?tab=fuel&action=add`)}
                    className="bg-slate-700 hover:bg-slate-600 text-white text-xs py-1.5 px-3 rounded transition-colors">
                    Log Fuel
                  </button>
                  <button onClick={() => navigate(`/vehicles/${vehicle.id}?tab=maintenance&action=add`)}
                    className="bg-slate-700 hover:bg-slate-600 text-white text-xs py-1.5 px-3 rounded transition-colors">
                    Log Service
                  </button>
                  <button onClick={() => navigate(`/vehicles/${vehicle.id}?tab=inspect`)}
                    className="bg-slate-700 hover:bg-slate-600 text-white text-xs py-1.5 px-3 rounded transition-colors">
                    Inspect
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {(() => {
        const comparisonVehicles = vehicles.filter(
          (v) => v.vehicle_type !== 'trailer' && cardData[v.id]?.costs != null
        );
        if (comparisonVehicles.length < 2) return null;

        const costPerMileValues = comparisonVehicles
          .map((v) => cardData[v.id]!.costs!.cost_per_mile)
          .filter((c): c is number => c != null);
        const minCostPerMile = costPerMileValues.length >= 2 ? Math.min(...costPerMileValues) : null;
        const maxCostPerMile = costPerMileValues.length >= 2 ? Math.max(...costPerMileValues) : null;

        return (
          <div className="card">
            <h2 className="font-semibold text-white mb-3">Fleet Comparison</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-400 text-left font-medium">
                    <th className="px-3 py-2">Vehicle</th>
                    <th className="px-3 py-2">MPG</th>
                    <th className="px-3 py-2">$/mi</th>
                    <th className="px-3 py-2">Total Spent</th>
                    <th className="px-3 py-2">Miles Tracked</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonVehicles.map((vehicle) => {
                    const data = cardData[vehicle.id]!;
                    const costs = data.costs!;
                    const costPerMile = costs.cost_per_mile;
                    let costPerMileClass = 'text-slate-300';
                    if (costPerMile != null && minCostPerMile != null && maxCostPerMile != null && minCostPerMile !== maxCostPerMile) {
                      if (costPerMile === minCostPerMile) costPerMileClass = 'text-green-400';
                      else if (costPerMile === maxCostPerMile) costPerMileClass = 'text-red-400';
                    }
                    return (
                      <tr key={vehicle.id} className="border-t border-slate-700">
                        <td className="px-3 py-2 text-white truncate">{vehicleLabel(vehicle)}</td>
                        <td className="px-3 py-2 text-slate-300">
                          {data.fuelStats?.average_mpg != null ? Number(data.fuelStats.average_mpg).toFixed(1) : '—'}
                        </td>
                        <td className={`px-3 py-2 ${costPerMileClass}`}>
                          {costPerMile != null ? `$${costPerMile.toFixed(2)}` : '—'}
                        </td>
                        <td className="px-3 py-2 text-slate-300">${costs.total_cost.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                        <td className="px-3 py-2 text-slate-300">{costs.miles_tracked.toLocaleString()}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* Mark Done dialog */}
      <dialog
        ref={dialogRef}
        className="rounded-xl bg-slate-800 border border-slate-700 p-6 w-full max-w-sm shadow-xl text-white backdrop:bg-black/60"
        onClose={() => setMarkDoneReminder(null)}
      >
        {markDoneReminder && (
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold">Mark Done</h3>
              <p className="text-sm text-slate-400 mt-0.5">{markDoneReminder.service_type} — {markDoneVehicle ? vehicleLabel(markDoneVehicle) : ''}</p>
            </div>
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
              <button onClick={saveMarkDone} disabled={markDoneSaving} className="btn-primary flex-1">
                {markDoneSaving ? 'Saving...' : 'Save'}
              </button>
              <button onClick={() => dialogRef.current?.close()} className="btn-secondary flex-1">Cancel</button>
            </div>
          </div>
        )}
      </dialog>
    </div>
  );
}
