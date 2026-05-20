import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiClient } from '../services/api';
import Modal from '../components/Modal';

type Tab = 'summary' | 'fuel' | 'maintenance' | 'expenses' | 'documents';

interface Vehicle {
  id: number;
  make: string;
  model: string;
  year: number;
  vin?: string;
  current_mileage: number;
  fuel_type: string;
  created_at: string;
  nhtsa_data?: Record<string, unknown>;
}

interface FuelEntry {
  id: number;
  date: string;
  mileage: number;
  gallons: number;
  cost: number;
  location?: string;
  notes?: string;
  mpg?: number;
}

interface MaintenanceEntry {
  id: number;
  date: string;
  mileage: number;
  type: string;
  cost: number;
  service_provider?: string;
  notes?: string;
}

interface Reminder {
  id: number;
  service_type: string;
  interval_miles?: number;
  interval_days?: number;
  last_performed_mileage?: number;
  next_due_mileage?: number;
  next_due_date?: string;
  is_overdue: boolean;
}

interface Expense {
  id: number;
  category: string;
  amount: number;
  date: string;
  description: string;
}

interface Document {
  id: number;
  document_type: string;
  filename: string;
  created_at: string;
}

const SERVICE_TYPES = [
  'Oil Change', 'Tire Rotation', 'Brake Service', 'Air Filter',
  'Transmission Service', 'Coolant Flush', 'Spark Plugs', 'Battery',
  'Alignment', 'Wiper Blades', 'Other',
];

const EXPENSE_CATEGORIES = ['insurance', 'registration', 'repair', 'fuel', 'other'];
const DOC_TYPES = ['registration', 'insurance', 'receipt', 'service', 'warranty', 'other'];

const today = () => new Date().toISOString().split('T')[0];

function fmtDate(dateStr: string) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

function FormError({ msg }: { msg: string }) {
  if (!msg) return null;
  return (
    <p className="text-red-400 text-sm bg-red-900/30 border border-red-800 p-3 rounded">
      {msg}
    </p>
  );
}

export default function VehicleDetailPage() {
  const { vehicleId } = useParams<{ vehicleId: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const id = Number(vehicleId);

  const [activeTab, setActiveTab] = useState<Tab>(
    (searchParams.get('tab') as Tab) || 'summary'
  );
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [loading, setLoading] = useState(true);

  // Tab data
  const [fuelEntries, setFuelEntries] = useState<FuelEntry[]>([]);
  const [fuelStats, setFuelStats] = useState<any>(null);
  const [maintEntries, setMaintEntries] = useState<MaintenanceEntry[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);

  // Modal open/close
  const [fuelModal, setFuelModal] = useState(false);
  const [maintModal, setMaintModal] = useState(false);
  const [reminderModal, setReminderModal] = useState(false);
  const [expenseModal, setExpenseModal] = useState(false);
  const [docModal, setDocModal] = useState(false);

  // Edit targets (null = adding new)
  const [editFuel, setEditFuel] = useState<FuelEntry | null>(null);
  const [editMaint, setEditMaint] = useState<MaintenanceEntry | null>(null);

  // Form state
  const [fuelForm, setFuelForm] = useState({ date: today(), mileage: 0, gallons: 0, cost: 0, location: '', notes: '' });
  const [maintForm, setMaintForm] = useState({ date: today(), mileage: 0, type: 'Oil Change', cost: 0, service_provider: '', notes: '' });
  const [reminderForm, setReminderForm] = useState({ service_type: 'Oil Change', interval_miles: '', interval_days: '' });
  const [expenseForm, setExpenseForm] = useState({ category: 'insurance', amount: 0, date: today(), description: '' });
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docType, setDocType] = useState('registration');

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // ─── Data loaders ───────────────────────────────────────────────────────────

  const loadFuel = useCallback(async () => {
    const [entries, stats] = await Promise.all([
      apiClient.listFuelEntries(id),
      apiClient.getFuelStats(id),
    ]);
    setFuelEntries(entries);
    setFuelStats(stats);
  }, [id]);

  const loadMaintenance = useCallback(async () => {
    const [entries, rems] = await Promise.all([
      apiClient.listMaintenanceEntries(id),
      apiClient.listMaintenanceReminders(id),
    ]);
    setMaintEntries(entries);
    setReminders(rems);
  }, [id]);

  const loadExpenses = useCallback(async () => {
    setExpenses(await apiClient.listExpenses(id));
  }, [id]);

  const loadDocuments = useCallback(async () => {
    setDocuments(await apiClient.listDocuments(id));
  }, [id]);

  useEffect(() => {
    apiClient
      .getVehicle(id)
      .then(setVehicle)
      .catch(() => navigate('/vehicles'))
      .finally(() => setLoading(false));
  }, [id, navigate]);

  useEffect(() => {
    if (!vehicle) return;
    if (activeTab === 'fuel') loadFuel().catch(console.error);
    if (activeTab === 'maintenance') loadMaintenance().catch(console.error);
    if (activeTab === 'expenses') loadExpenses().catch(console.error);
    if (activeTab === 'documents') loadDocuments().catch(console.error);
  }, [activeTab, vehicle, loadFuel, loadMaintenance, loadExpenses, loadDocuments]);

  // ─── Fuel handlers ──────────────────────────────────────────────────────────

  const openFuelAdd = () => {
    setEditFuel(null);
    setFuelForm({ date: today(), mileage: 0, gallons: 0, cost: 0, location: '', notes: '' });
    setFormError('');
    setFuelModal(true);
  };

  const openFuelEdit = (e: FuelEntry) => {
    setEditFuel(e);
    setFuelForm({ date: e.date, mileage: e.mileage, gallons: e.gallons, cost: e.cost, location: e.location || '', notes: e.notes || '' });
    setFormError('');
    setFuelModal(true);
  };

  const saveFuel = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const payload = {
        date: fuelForm.date,
        mileage: Number(fuelForm.mileage),
        gallons: Number(fuelForm.gallons),
        cost: Number(fuelForm.cost),
        location: fuelForm.location || undefined,
        notes: fuelForm.notes || undefined,
      };
      if (editFuel) {
        await apiClient.updateFuelEntry(id, editFuel.id, payload);
      } else {
        await apiClient.createFuelEntry(id, payload);
      }
      setFuelModal(false);
      loadFuel().catch(console.error);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const deleteFuel = async (entryId: number) => {
    if (!confirm('Delete this fuel entry?')) return;
    await apiClient.deleteFuelEntry(id, entryId).catch(console.error);
    loadFuel().catch(console.error);
  };

  // ─── Maintenance handlers ────────────────────────────────────────────────────

  const openMaintAdd = () => {
    setEditMaint(null);
    setMaintForm({ date: today(), mileage: 0, type: 'Oil Change', cost: 0, service_provider: '', notes: '' });
    setFormError('');
    setMaintModal(true);
  };

  const openMaintEdit = (e: MaintenanceEntry) => {
    setEditMaint(e);
    setMaintForm({ date: e.date, mileage: e.mileage, type: e.type, cost: e.cost, service_provider: e.service_provider || '', notes: e.notes || '' });
    setFormError('');
    setMaintModal(true);
  };

  const saveMaint = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const payload = {
        date: maintForm.date,
        mileage: Number(maintForm.mileage),
        type: maintForm.type,
        cost: Number(maintForm.cost),
        service_provider: maintForm.service_provider || undefined,
        notes: maintForm.notes || undefined,
      };
      if (editMaint) {
        await apiClient.updateMaintenanceEntry(id, editMaint.id, payload);
      } else {
        await apiClient.createMaintenanceEntry(id, payload);
      }
      setMaintModal(false);
      loadMaintenance().catch(console.error);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const deleteMaint = async (entryId: number) => {
    if (!confirm('Delete this service record?')) return;
    await apiClient.deleteMaintenanceEntry(id, entryId).catch(console.error);
    loadMaintenance().catch(console.error);
  };

  const saveReminder = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      await apiClient.createMaintenanceReminder(id, {
        service_type: reminderForm.service_type,
        interval_miles: reminderForm.interval_miles ? Number(reminderForm.interval_miles) : undefined,
        interval_days: reminderForm.interval_days ? Number(reminderForm.interval_days) : undefined,
      });
      setReminderModal(false);
      loadMaintenance().catch(console.error);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to save reminder');
    } finally {
      setSaving(false);
    }
  };

  const deleteReminder = async (reminderId: number) => {
    if (!confirm('Delete this reminder?')) return;
    await apiClient.deleteMaintenanceReminder(id, reminderId).catch(console.error);
    loadMaintenance().catch(console.error);
  };

  // ─── Expense handlers ────────────────────────────────────────────────────────

  const openExpenseAdd = () => {
    setExpenseForm({ category: 'insurance', amount: 0, date: today(), description: '' });
    setFormError('');
    setExpenseModal(true);
  };

  const saveExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      await apiClient.createExpense(id, { ...expenseForm, amount: Number(expenseForm.amount) });
      setExpenseModal(false);
      loadExpenses().catch(console.error);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const deleteExpense = async (expenseId: number) => {
    if (!confirm('Delete this expense?')) return;
    await apiClient.deleteExpense(id, expenseId).catch(console.error);
    loadExpenses().catch(console.error);
  };

  // ─── Document handlers ───────────────────────────────────────────────────────

  const saveDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docFile) return;
    setSaving(true);
    setFormError('');
    try {
      await apiClient.uploadDocument(id, docFile, docType);
      setDocModal(false);
      setDocFile(null);
      loadDocuments().catch(console.error);
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setSaving(false);
    }
  };

  const deleteDocument = async (docId: number) => {
    if (!confirm('Delete this document?')) return;
    await apiClient.deleteDocument(id, docId).catch(console.error);
    loadDocuments().catch(console.error);
  };

  // ─── Reminder status helper ──────────────────────────────────────────────────

  const reminderStatus = (r: Reminder) => {
    if (r.is_overdue) return { color: 'text-red-400', bg: 'bg-red-900/30', label: 'Overdue' };
    if (r.next_due_mileage && vehicle) {
      const remaining = r.next_due_mileage - vehicle.current_mileage;
      if (remaining <= 500)
        return { color: 'text-amber-400', bg: 'bg-amber-900/30', label: `${remaining.toLocaleString()} mi` };
    }
    return { color: 'text-green-400', bg: 'bg-green-900/20', label: 'OK' };
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

  if (loading) return <div className="text-slate-400 py-10 text-center">Loading...</div>;
  if (!vehicle) return null;

  const tabs: { id: Tab; label: string }[] = [
    { id: 'summary', label: 'Summary' },
    { id: 'fuel', label: 'Fuel' },
    { id: 'maintenance', label: 'Maintenance' },
    { id: 'expenses', label: 'Expenses' },
    { id: 'documents', label: 'Documents' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate('/vehicles')}
          className="text-slate-400 hover:text-white text-sm mb-2 transition-colors block"
        >
          ← All Vehicles
        </button>
        <h1 className="text-2xl font-bold text-white">
          {vehicle.year} {vehicle.make} {vehicle.model}
        </h1>
        {vehicle.vin && (
          <p className="text-slate-400 text-sm mt-1 font-mono">VIN: {vehicle.vin}</p>
        )}
      </div>

      {/* Tab nav */}
      <div className="border-b border-slate-700">
        <nav className="flex overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-teal-500 text-teal-400'
                  : 'border-transparent text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── SUMMARY ─────────────────────────────────────────────────────────── */}
      {activeTab === 'summary' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="card space-y-3">
            <h2 className="font-semibold text-white">Vehicle Info</h2>
            {(
              [
                ['Year', vehicle.year],
                ['Make', vehicle.make],
                ['Model', vehicle.model],
                ['Fuel Type', vehicle.fuel_type],
                ['Current Mileage', `${vehicle.current_mileage.toLocaleString()} mi`],
                ...(vehicle.vin ? [['VIN', vehicle.vin]] : []),
              ] as [string, string | number][]
            ).map(([label, value]) => (
              <div key={label} className="flex justify-between text-sm border-b border-slate-700 pb-2 last:border-0 last:pb-0">
                <span className="text-slate-400">{label}</span>
                <span className="text-white font-mono text-right">{value}</span>
              </div>
            ))}
          </div>

          {vehicle.nhtsa_data && Object.keys(vehicle.nhtsa_data).length > 0 && (
            <div className="card">
              <h2 className="font-semibold text-white mb-3">NHTSA Data</h2>
              <div className="space-y-2">
                {Object.entries(vehicle.nhtsa_data)
                  .slice(0, 8)
                  .map(([k, v]) => (
                    <div key={k} className="flex justify-between text-sm">
                      <span className="text-slate-400 truncate mr-4">{k}</span>
                      <span className="text-white text-right">{String(v)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── FUEL ────────────────────────────────────────────────────────────── */}
      {activeTab === 'fuel' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Fuel History</h2>
            <button onClick={openFuelAdd} className="btn-primary text-sm">
              + Log Fill-up
            </button>
          </div>

          {fuelStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: 'Avg MPG', value: fuelStats.average_mpg != null ? Number(fuelStats.average_mpg).toFixed(1) : '—' },
                { label: 'Total Spent', value: `$${Number(fuelStats.total_spent).toFixed(2)}` },
                { label: 'Total Gallons', value: Number(fuelStats.total_gallons).toFixed(1) },
                { label: 'Fill-ups', value: fuelStats.entries_count },
              ].map(({ label, value }) => (
                <div key={label} className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-400 text-xs">{label}</p>
                  <p className="text-white font-semibold mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          )}

          {fuelEntries.length === 0 ? (
            <div className="card text-center py-10">
              <p className="text-slate-400">No fuel entries yet.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-slate-700">
              <table className="w-full text-sm">
                <thead className="bg-slate-800/80">
                  <tr className="text-slate-400 text-left">
                    <th className="px-4 py-3 font-medium">Date</th>
                    <th className="px-4 py-3 font-medium">Mileage</th>
                    <th className="px-4 py-3 font-medium">Gallons</th>
                    <th className="px-4 py-3 font-medium">Cost</th>
                    <th className="px-4 py-3 font-medium">MPG</th>
                    <th className="px-4 py-3 font-medium">Location</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {fuelEntries.map((e) => (
                    <tr key={e.id} className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
                      <td className="px-4 py-3 text-slate-300">{fmtDate(e.date)}</td>
                      <td className="px-4 py-3 text-slate-300">{e.mileage.toLocaleString()}</td>
                      <td className="px-4 py-3 text-slate-300">{Number(e.gallons).toFixed(3)}</td>
                      <td className="px-4 py-3 text-slate-300">${Number(e.cost).toFixed(2)}</td>
                      <td className="px-4 py-3 text-slate-300">
                        {e.mpg != null ? Number(e.mpg).toFixed(1) : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-400">{e.location || '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          <button
                            onClick={() => openFuelEdit(e)}
                            className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => deleteFuel(e.id)}
                            className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                          >
                            Del
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Modal isOpen={fuelModal} onClose={() => setFuelModal(false)} title={editFuel ? 'Edit Fuel Entry' : 'Log Fill-up'}>
            <form onSubmit={saveFuel} className="space-y-4">
              <FormError msg={formError} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Date *</label>
                  <input type="date" className="input-field" value={fuelForm.date}
                    onChange={(e) => setFuelForm((p) => ({ ...p, date: e.target.value }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Mileage *</label>
                  <input type="number" className="input-field" min="0" value={fuelForm.mileage}
                    onChange={(e) => setFuelForm((p) => ({ ...p, mileage: Number(e.target.value) }))} required />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Gallons *</label>
                  <input type="number" className="input-field" min="0" step="0.001" value={fuelForm.gallons}
                    onChange={(e) => setFuelForm((p) => ({ ...p, gallons: Number(e.target.value) }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Cost ($) *</label>
                  <input type="number" className="input-field" min="0" step="0.01" value={fuelForm.cost}
                    onChange={(e) => setFuelForm((p) => ({ ...p, cost: Number(e.target.value) }))} required />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Location</label>
                <input className="input-field" placeholder="e.g. Meijer, Shell" value={fuelForm.location}
                  onChange={(e) => setFuelForm((p) => ({ ...p, location: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Notes</label>
                <textarea className="input-field" rows={2} value={fuelForm.notes}
                  onChange={(e) => setFuelForm((p) => ({ ...p, notes: e.target.value }))} />
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={saving} className="btn-primary flex-1">
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button type="button" onClick={() => setFuelModal(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </form>
          </Modal>
        </div>
      )}

      {/* ── MAINTENANCE ──────────────────────────────────────────────────────── */}
      {activeTab === 'maintenance' && (
        <div className="space-y-6">
          {/* Reminders */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-white">Reminders</h2>
              <button
                onClick={() => {
                  setReminderForm({ service_type: 'Oil Change', interval_miles: '', interval_days: '' });
                  setFormError('');
                  setReminderModal(true);
                }}
                className="btn-secondary text-sm"
              >
                + Add Reminder
              </button>
            </div>
            {reminders.length === 0 ? (
              <p className="text-slate-400 text-sm">No reminders set.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {reminders.map((r) => {
                  const s = reminderStatus(r);
                  return (
                    <div key={r.id} className={`${s.bg} border border-slate-700 rounded-lg p-4`}>
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="font-medium text-white">{r.service_type}</p>
                          <p className="text-slate-400 text-xs mt-1">
                            {r.interval_miles ? `Every ${r.interval_miles.toLocaleString()} mi` : ''}
                            {r.interval_miles && r.interval_days ? ' · ' : ''}
                            {r.interval_days ? `Every ${r.interval_days} days` : ''}
                          </p>
                          {r.next_due_mileage && (
                            <p className="text-slate-400 text-xs mt-0.5">
                              Due at {r.next_due_mileage.toLocaleString()} mi
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          <span className={`text-xs font-semibold ${s.color}`}>{s.label}</span>
                          <button
                            onClick={() => deleteReminder(r.id)}
                            className="text-slate-500 hover:text-red-400 text-lg leading-none transition-colors"
                          >
                            ×
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Service history */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-semibold text-white">Service History</h2>
              <button onClick={openMaintAdd} className="btn-primary text-sm">
                + Log Service
              </button>
            </div>
            {maintEntries.length === 0 ? (
              <div className="card text-center py-10">
                <p className="text-slate-400">No service records yet.</p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-700">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/80">
                    <tr className="text-slate-400 text-left">
                      <th className="px-4 py-3 font-medium">Date</th>
                      <th className="px-4 py-3 font-medium">Service</th>
                      <th className="px-4 py-3 font-medium">Mileage</th>
                      <th className="px-4 py-3 font-medium">Cost</th>
                      <th className="px-4 py-3 font-medium">Provider</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {maintEntries.map((e) => (
                      <tr key={e.id} className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
                        <td className="px-4 py-3 text-slate-300">{fmtDate(e.date)}</td>
                        <td className="px-4 py-3 text-white">{e.type}</td>
                        <td className="px-4 py-3 text-slate-300">{e.mileage.toLocaleString()}</td>
                        <td className="px-4 py-3 text-slate-300">${Number(e.cost).toFixed(2)}</td>
                        <td className="px-4 py-3 text-slate-400">{e.service_provider || '—'}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <button
                              onClick={() => openMaintEdit(e)}
                              className="text-xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => deleteMaint(e.id)}
                              className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                            >
                              Del
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Maintenance entry modal */}
          <Modal isOpen={maintModal} onClose={() => setMaintModal(false)} title={editMaint ? 'Edit Service Record' : 'Log Service'}>
            <form onSubmit={saveMaint} className="space-y-4">
              <FormError msg={formError} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Date *</label>
                  <input type="date" className="input-field" value={maintForm.date}
                    onChange={(e) => setMaintForm((p) => ({ ...p, date: e.target.value }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Mileage *</label>
                  <input type="number" className="input-field" min="0" value={maintForm.mileage}
                    onChange={(e) => setMaintForm((p) => ({ ...p, mileage: Number(e.target.value) }))} required />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Service Type *</label>
                <select className="input-field" value={maintForm.type}
                  onChange={(e) => setMaintForm((p) => ({ ...p, type: e.target.value }))}>
                  {SERVICE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Cost ($) *</label>
                  <input type="number" className="input-field" min="0" step="0.01" value={maintForm.cost}
                    onChange={(e) => setMaintForm((p) => ({ ...p, cost: Number(e.target.value) }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Provider</label>
                  <input className="input-field" placeholder="e.g. Jiffy Lube" value={maintForm.service_provider}
                    onChange={(e) => setMaintForm((p) => ({ ...p, service_provider: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Notes</label>
                <textarea className="input-field" rows={2} value={maintForm.notes}
                  onChange={(e) => setMaintForm((p) => ({ ...p, notes: e.target.value }))} />
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={saving} className="btn-primary flex-1">
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button type="button" onClick={() => setMaintModal(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </form>
          </Modal>

          {/* Reminder modal */}
          <Modal isOpen={reminderModal} onClose={() => setReminderModal(false)} title="Add Maintenance Reminder">
            <form onSubmit={saveReminder} className="space-y-4">
              <FormError msg={formError} />
              <div>
                <label className="block text-sm text-slate-300 mb-1">Service Type *</label>
                <select className="input-field" value={reminderForm.service_type}
                  onChange={(e) => setReminderForm((p) => ({ ...p, service_type: e.target.value }))}>
                  {SERVICE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Interval (miles)</label>
                  <input type="number" className="input-field" min="1" placeholder="e.g. 5000"
                    value={reminderForm.interval_miles}
                    onChange={(e) => setReminderForm((p) => ({ ...p, interval_miles: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Interval (days)</label>
                  <input type="number" className="input-field" min="1" placeholder="e.g. 90"
                    value={reminderForm.interval_days}
                    onChange={(e) => setReminderForm((p) => ({ ...p, interval_days: e.target.value }))} />
                </div>
              </div>
              <p className="text-slate-400 text-xs">Fill in at least one interval.</p>
              <div className="flex gap-3">
                <button type="submit" disabled={saving} className="btn-primary flex-1">
                  {saving ? 'Saving...' : 'Add Reminder'}
                </button>
                <button type="button" onClick={() => setReminderModal(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </form>
          </Modal>
        </div>
      )}

      {/* ── EXPENSES ──────────────────────────────────────────────────────────── */}
      {activeTab === 'expenses' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Expenses</h2>
            <button onClick={openExpenseAdd} className="btn-primary text-sm">
              + Add Expense
            </button>
          </div>

          {expenses.length === 0 ? (
            <div className="card text-center py-10">
              <p className="text-slate-400">No expenses recorded yet.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-slate-700">
                <table className="w-full text-sm">
                  <thead className="bg-slate-800/80">
                    <tr className="text-slate-400 text-left">
                      <th className="px-4 py-3 font-medium">Date</th>
                      <th className="px-4 py-3 font-medium">Category</th>
                      <th className="px-4 py-3 font-medium">Description</th>
                      <th className="px-4 py-3 font-medium">Amount</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {expenses.map((e) => (
                      <tr key={e.id} className="border-t border-slate-700 hover:bg-slate-800/50 transition-colors">
                        <td className="px-4 py-3 text-slate-300">{fmtDate(e.date)}</td>
                        <td className="px-4 py-3">
                          <span className="capitalize text-xs bg-slate-700 text-slate-200 px-2 py-0.5 rounded">
                            {e.category}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-300">{e.description}</td>
                        <td className="px-4 py-3 text-white font-medium">${Number(e.amount).toFixed(2)}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => deleteExpense(e.id)}
                            className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded hover:bg-slate-700 transition-colors"
                          >
                            Del
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-slate-600">
                      <td colSpan={3} className="px-4 py-3 text-slate-400 text-sm font-medium">
                        Total
                      </td>
                      <td className="px-4 py-3 text-white font-bold">
                        ${expenses.reduce((sum, e) => sum + Number(e.amount), 0).toFixed(2)}
                      </td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </>
          )}

          <Modal isOpen={expenseModal} onClose={() => setExpenseModal(false)} title="Add Expense">
            <form onSubmit={saveExpense} className="space-y-4">
              <FormError msg={formError} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Category *</label>
                  <select className="input-field" value={expenseForm.category}
                    onChange={(e) => setExpenseForm((p) => ({ ...p, category: e.target.value }))}>
                    {EXPENSE_CATEGORIES.map((c) => (
                      <option key={c} value={c} className="capitalize">{c}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Amount ($) *</label>
                  <input type="number" className="input-field" min="0" step="0.01" value={expenseForm.amount}
                    onChange={(e) => setExpenseForm((p) => ({ ...p, amount: Number(e.target.value) }))} required />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Date *</label>
                <input type="date" className="input-field" value={expenseForm.date}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, date: e.target.value }))} required />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Description *</label>
                <input className="input-field" placeholder="e.g. Monthly auto insurance"
                  value={expenseForm.description}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, description: e.target.value }))} required />
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={saving} className="btn-primary flex-1">
                  {saving ? 'Saving...' : 'Add Expense'}
                </button>
                <button type="button" onClick={() => setExpenseModal(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </form>
          </Modal>
        </div>
      )}

      {/* ── DOCUMENTS ────────────────────────────────────────────────────────── */}
      {activeTab === 'documents' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Documents</h2>
            <button
              onClick={() => {
                setDocFile(null);
                setDocType('registration');
                setFormError('');
                setDocModal(true);
              }}
              className="btn-primary text-sm"
            >
              + Upload Document
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="card text-center py-10">
              <p className="text-slate-400">No documents uploaded yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {documents.map((doc) => (
                <div key={doc.id} className="card flex items-center justify-between">
                  <div className="min-w-0">
                    <span className="capitalize text-xs bg-teal-900/40 text-teal-300 px-2 py-0.5 rounded">
                      {doc.document_type}
                    </span>
                    <p className="text-white text-sm mt-1.5 truncate">{doc.filename}</p>
                    <p className="text-slate-400 text-xs mt-0.5">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={() => deleteDocument(doc.id)}
                    className="text-red-400 hover:text-red-300 text-sm ml-4 flex-shrink-0 transition-colors"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}

          <Modal isOpen={docModal} onClose={() => setDocModal(false)} title="Upload Document">
            <form onSubmit={saveDocument} className="space-y-4">
              <FormError msg={formError} />
              <div>
                <label className="block text-sm text-slate-300 mb-1">Document Type *</label>
                <select className="input-field" value={docType} onChange={(e) => setDocType(e.target.value)}>
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t} className="capitalize">{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">File *</label>
                <input
                  type="file"
                  className="w-full text-sm text-slate-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-slate-700 file:text-white hover:file:bg-slate-600 cursor-pointer"
                  onChange={(e) => setDocFile(e.target.files?.[0] || null)}
                  required
                />
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={saving || !docFile} className="btn-primary flex-1">
                  {saving ? 'Uploading...' : 'Upload'}
                </button>
                <button type="button" onClick={() => setDocModal(false)} className="btn-secondary flex-1">
                  Cancel
                </button>
              </div>
            </form>
          </Modal>
        </div>
      )}
    </div>
  );
}
