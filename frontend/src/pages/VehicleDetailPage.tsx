import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { apiClient } from '../services/api';
import Modal from '../components/Modal';
import { useToastStore } from '../stores/toastStore';
import AnalyticsTab from '../components/AnalyticsTab';

type Tab = 'summary' | 'fuel' | 'trips' | 'maintenance' | 'expenses' | 'documents' | 'parts' | 'analytics';

interface Vehicle {
  id: number;
  nickname?: string;
  vehicle_type: string;
  make: string;
  model: string;
  year: number;
  vin?: string;
  current_mileage: number;
  fuel_type: string;
  axle_count?: number;
  created_at: string;
  nhtsa_data?: Record<string, unknown>;
  specs_overrides?: Record<string, unknown>;
}

interface TripEntry {
  id: number;
  date: string;
  miles: number;
  destination?: string;
  notes?: string;
}

interface VehiclePart {
  id: number;
  name: string;
  part_number?: string;
  brand?: string;
  category: string;
  notes?: string;
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
  target_mileage?: number;
  reminder_miles?: number;
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

const VEHICLE_SERVICE_TYPES = [
  'Oil Change', 'Tire Rotation', 'Brake Service', 'Air Filter',
  'Transmission Service', 'Coolant Flush', 'Spark Plugs', 'Battery',
  'Alignment', 'Wiper Blades', 'Other',
];

const TRAILER_SERVICE_TYPES = [
  'Wheel Bearing Service', 'Hub Inspection', 'Axle Seal Replacement',
  'Brake Adjustment', 'Running Lights Check', 'Tire Rotation/Replacement',
  'Coupler/Hitch Inspection', 'Safety Chain Inspection',
  'Floor/Decking Inspection', 'Wiring Harness Inspection',
  'Suspension Inspection', 'Other',
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

function ScanReceiptButton({ onScan }: { onScan: (file: File) => Promise<void> }) {
  const [scanning, setScanning] = React.useState(false);
  const ref = React.useRef<HTMLInputElement>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanning(true);
    try { await onScan(file); } finally { setScanning(false); if (ref.current) ref.current.value = ''; }
  };

  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={() => ref.current?.click()} disabled={scanning}
        className="flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 border border-teal-800 hover:border-teal-700 bg-teal-900/20 px-3 py-1.5 rounded transition-colors disabled:opacity-50">
        {scanning ? (
          <><span className="animate-spin inline-block">⟳</span> Scanning...</>
        ) : (
          <>📷 Scan Receipt</>
        )}
      </button>
      <input ref={ref} type="file" accept="image/*" className="hidden" onChange={handleFile} />
    </div>
  );
}

function MileageRow({ vehicle, onUpdate }: { vehicle: Vehicle; onUpdate: (v: Vehicle) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(String(vehicle.current_mileage));
  const [saving, setSaving] = useState(false);
  const addToast = useToastStore((state) => state.addToast);

  const save = async () => {
    const miles = Number(value);
    if (isNaN(miles) || miles < 0) return;
    setSaving(true);
    try {
      const updated = await apiClient.updateVehicleMileage(vehicle.id, miles);
      onUpdate(updated);
      setEditing(false);
      addToast('success', 'Mileage updated');
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div className="flex justify-between text-sm border-b border-slate-700 pb-2 last:border-0 last:pb-0">
        <span className="text-slate-400">Current Mileage</span>
        <button
          onClick={() => { setValue(String(vehicle.current_mileage)); setEditing(true); }}
          className="text-white font-mono hover:text-teal-400 transition-colors group flex items-center gap-1"
        >
          {vehicle.current_mileage.toLocaleString()} mi
          <span className="text-slate-500 group-hover:text-teal-400 text-xs">✎</span>
        </button>
      </div>
    );
  }

  return (
    <div className="flex justify-between items-center text-sm border-b border-slate-700 pb-2">
      <span className="text-slate-400">Current Mileage</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          className="w-28 px-2 py-0.5 bg-slate-700 border border-teal-500 rounded text-white text-right font-mono text-sm focus:outline-none"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false); }}
          autoFocus
          min="0"
        />
        <button onClick={save} disabled={saving} className="text-teal-400 hover:text-teal-300 text-xs font-medium">
          {saving ? '...' : 'Save'}
        </button>
        <button onClick={() => setEditing(false)} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
      </div>
    </div>
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

  // Analytics data (loaded once, used by analytics tab)
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsFuel, setAnalyticsFuel] = useState<FuelEntry[]>([]);
  const [analyticsMaint, setAnalyticsMaint] = useState<MaintenanceEntry[]>([]);
  const [analyticsExpenses, setAnalyticsExpenses] = useState<Expense[]>([]);
  const [analyticsTrips, setAnalyticsTrips] = useState<TripEntry[]>([]);

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
  const [partModal, setPartModal] = useState(false);
  const [specsEditModal, setSpecsEditModal] = useState(false);

  // Edit targets (null = adding new)
  const [editFuel, setEditFuel] = useState<FuelEntry | null>(null);
  const [editMaint, setEditMaint] = useState<MaintenanceEntry | null>(null);
  const [editPart, setEditPart] = useState<VehiclePart | null>(null);

  // Parts state
  const [parts, setParts] = useState<VehiclePart[]>([]);

  // Trip state
  const [tripEntries, setTripEntries] = useState<TripEntry[]>([]);
  const [tripStats, setTripStats] = useState<any>(null);
  const [tripModal, setTripModal] = useState(false);
  const [editTrip, setEditTrip] = useState<TripEntry | null>(null);
  const [tripForm, setTripForm] = useState({ date: today(), miles: 0, destination: '', notes: '' });

  // Specs override state
  const [specsForm, setSpecsForm] = useState<Record<string, string>>({});

  // Form state
  const [fuelForm, setFuelForm] = useState({ date: today(), mileage: 0, gallons: 0, cost: 0, location: '', notes: '' });
  const [gpsLoading, setGpsLoading] = useState(false);
  const [customServiceTypes, setCustomServiceTypes] = useState<string[]>(() =>
    JSON.parse(localStorage.getItem('customServiceTypes') || '[]')
  );
  const [customTypesOpen, setCustomTypesOpen] = useState(false);
  const [newTypeInput, setNewTypeInput] = useState('');
  const [customExpenseCategories, setCustomExpenseCategories] = useState<string[]>(() =>
    JSON.parse(localStorage.getItem('customExpenseCategories') || '[]')
  );
  const [expenseCatsOpen, setExpenseCatsOpen] = useState(false);
  const [newCatInput, setNewCatInput] = useState('');
  const [maintOther, setMaintOther] = useState('');
  const [maintForm, setMaintForm] = useState({ date: today(), mileage: 0, type: 'Oil Change', cost: 0, service_provider: '', notes: '' });
  const [reminderTrigger, setReminderTrigger] = useState<'interval' | 'target'>('interval');
  const [reminderForm, setReminderForm] = useState({ service_type: 'Oil Change', interval_miles: '', interval_days: '', target_mileage: '', reminder_miles: '500' });
  const [expenseForm, setExpenseForm] = useState({ category: 'insurance', amount: 0, date: today(), description: '' });
  const [partForm, setPartForm] = useState({ name: '', part_number: '', brand: '', category: 'filters', notes: '' });
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docType, setDocType] = useState('registration');

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const addToast = useToastStore((state) => state.addToast);

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
    const [entries, rems, fuel] = await Promise.all([
      apiClient.listMaintenanceEntries(id),
      apiClient.listMaintenanceReminders(id),
      apiClient.listFuelEntries(id),
    ]);
    setMaintEntries(entries);
    setReminders(rems);
    setFuelEntries(fuel);
  }, [id]);

  const loadExpenses = useCallback(async () => {
    setExpenses(await apiClient.listExpenses(id));
  }, [id]);

  const loadDocuments = useCallback(async () => {
    setDocuments(await apiClient.listDocuments(id));
  }, [id]);

  const loadParts = useCallback(async () => {
    setParts(await apiClient.listParts(id));
  }, [id]);

  const loadTrips = useCallback(async () => {
    const [entries, stats] = await Promise.all([
      apiClient.listTrips(id),
      apiClient.getTripStats(id),
    ]);
    setTripEntries(entries);
    setTripStats(stats);
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
    if (activeTab === 'parts') loadParts().catch(console.error);
    if (activeTab === 'trips') loadTrips().catch(console.error);
    if (activeTab === 'analytics') {
      setAnalyticsLoading(true);
      const trailer = vehicle.vehicle_type === 'trailer';
      const calls = trailer
        ? [Promise.resolve([]), apiClient.listMaintenanceEntries(id), Promise.resolve([]), apiClient.listTrips(id)]
        : [apiClient.listFuelEntries(id), apiClient.listMaintenanceEntries(id), apiClient.listExpenses(id), Promise.resolve([])];
      Promise.all(calls)
        .then(([fuel, maint, exp, trips]) => {
          setAnalyticsFuel(fuel as FuelEntry[]);
          setAnalyticsMaint(maint as MaintenanceEntry[]);
          setAnalyticsExpenses(exp as Expense[]);
          setAnalyticsTrips(trips as TripEntry[]);
        })
        .catch(console.error)
        .finally(() => setAnalyticsLoading(false));
    }
  }, [activeTab, vehicle, loadFuel, loadMaintenance, loadExpenses, loadDocuments, loadParts, loadTrips]);

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
      addToast('success', editFuel ? 'Fuel entry updated' : 'Fill-up logged');
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
    addToast('success', 'Fuel entry deleted');
  };

  // ─── Maintenance handlers ────────────────────────────────────────────────────

  const openMaintAdd = () => {
    setEditMaint(null);
    setMaintForm({ date: today(), mileage: 0, type: 'Oil Change', cost: 0, service_provider: '', notes: '' });
    setMaintOther('');
    setCustomTypesOpen(false);
    setFormError('');
    setMaintModal(true);
  };

  const openMaintEdit = (e: MaintenanceEntry) => {
    setEditMaint(e);
    const knownType = [...BASE_TYPES, ...customServiceTypes].includes(e.type) ? e.type : 'Other';
    setMaintForm({ date: e.date, mileage: e.mileage, type: knownType, cost: e.cost, service_provider: e.service_provider || '', notes: e.notes || '' });
    setMaintOther(knownType === 'Other' ? e.type : '');
    setCustomTypesOpen(false);
    setFormError('');
    setMaintModal(true);
  };

  const saveMaint = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      const serviceType = maintForm.type === 'Other' ? (maintOther.trim() || 'Other') : maintForm.type;
      const payload = {
        date: maintForm.date,
        mileage: Number(maintForm.mileage),
        type: serviceType,
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
      addToast('success', editMaint ? 'Service record updated' : 'Service logged');
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
    addToast('success', 'Service record deleted');
  };

  const saveReminder = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setFormError('');
    try {
      await apiClient.createMaintenanceReminder(id, {
        service_type: reminderForm.service_type,
        interval_miles: reminderTrigger === 'interval' && reminderForm.interval_miles ? Number(reminderForm.interval_miles) : undefined,
        interval_days: reminderTrigger === 'interval' && reminderForm.interval_days ? Number(reminderForm.interval_days) : undefined,
        target_mileage: reminderTrigger === 'target' && reminderForm.target_mileage ? Number(reminderForm.target_mileage) : undefined,
        reminder_miles: reminderForm.reminder_miles ? Number(reminderForm.reminder_miles) : 500,
      });
      setReminderModal(false);
      loadMaintenance().catch(console.error);
      addToast('success', 'Reminder added');
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
    addToast('success', 'Reminder deleted');
  };

  // ─── Expense handlers ────────────────────────────────────────────────────────

  const openExpenseAdd = () => {
    setExpenseForm({ category: 'insurance', amount: 0, date: today(), description: '' });
    setFormError('');
    setExpenseCatsOpen(false);
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
      addToast('success', 'Expense added');
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
    addToast('success', 'Expense deleted');
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
      addToast('success', 'Document uploaded');
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
    addToast('success', 'Document deleted');
  };

  // ─── Reminder helpers ────────────────────────────────────────────────────────

  const avgMilesPerDay = (): number | null => {
    if (fuelEntries.length < 2) return null;
    const sorted = [...fuelEntries].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const days = (new Date(sorted[sorted.length - 1].date).getTime() - new Date(sorted[0].date).getTime()) / 86400000;
    const miles = sorted[sorted.length - 1].mileage - sorted[0].mileage;
    return days > 0 && miles > 0 ? miles / days : null;
  };

  const reminderEta = (r: Reminder): { daysLeft: number; estDate: Date } | null => {
    if (!r.next_due_mileage || !vehicle) return null;
    const milesLeft = r.next_due_mileage - vehicle.current_mileage;
    if (milesLeft <= 0) return null;
    const avg = avgMilesPerDay();
    if (!avg) return null;
    const daysLeft = Math.round(milesLeft / avg);
    return { daysLeft, estDate: new Date(Date.now() + daysLeft * 86400000) };
  };

  const reminderStatus = (r: Reminder) => {
    const threshold = r.reminder_miles ?? 500;
    if (r.is_overdue) return { color: 'text-red-400', bg: 'bg-red-900/30', label: 'Overdue' };
    if (!r.next_due_mileage && !r.next_due_date && !r.target_mileage)
      return { color: 'text-slate-400', bg: 'bg-slate-800/50', label: 'Pending' };
    if (r.next_due_mileage && vehicle) {
      const remaining = r.next_due_mileage - vehicle.current_mileage;
      if (remaining <= 0) return { color: 'text-red-400', bg: 'bg-red-900/30', label: 'Overdue' };
      if (remaining <= threshold)
        return { color: 'text-amber-400', bg: 'bg-amber-900/30', label: `${remaining.toLocaleString()} mi left` };
    }
    return { color: 'text-green-400', bg: 'bg-green-900/20', label: 'OK' };
  };

  const startReminderNow = async (r: Reminder) => {
    if (!vehicle) return;
    const todayStr = today();
    const update: Record<string, unknown> = {
      last_performed_mileage: vehicle.current_mileage,
      last_performed_date: todayStr,
    };
    if (r.interval_miles) update.next_due_mileage = vehicle.current_mileage + r.interval_miles;
    if (r.interval_days) {
      const d = new Date();
      d.setDate(d.getDate() + r.interval_days);
      update.next_due_date = d.toISOString().split('T')[0];
    }
    try {
      await apiClient.updateMaintenanceReminder(id, r.id, update);
      loadMaintenance().catch(console.error);
      addToast('success', `${r.service_type} interval started from today`);
    } catch {
      addToast('error', 'Failed to update reminder');
    }
  };

  const handleGpsLocation = () => {
    if (!navigator.geolocation) { addToast('error', 'Geolocation not supported by this browser'); return; }
    setGpsLoading(true);
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const query = `[out:json];node["amenity"="fuel"](around:500,${coords.latitude},${coords.longitude});out body;`;
          const res = await fetch('https://overpass-api.de/api/interpreter', {
            method: 'POST',
            body: query,
          });
          const data = await res.json();
          if (!data.elements?.length) { addToast('info', 'No gas stations found nearby'); return; }
          const nearest = data.elements.reduce((a: any, b: any) => {
            const dist = (n: any) => Math.hypot(n.lat - coords.latitude, n.lon - coords.longitude);
            return dist(a) <= dist(b) ? a : b;
          });
          const name = nearest.tags?.name || nearest.tags?.brand || nearest.tags?.operator || 'Gas Station';
          setFuelForm((p) => ({ ...p, location: name }));
        } catch {
          addToast('error', 'Could not fetch nearby stations');
        } finally {
          setGpsLoading(false);
        }
      },
      () => { addToast('error', 'Location access denied'); setGpsLoading(false); },
      { timeout: 10000 }
    );
  };

  // ─── Render ──────────────────────────────────────────────────────────────────

  if (loading) return <div className="text-slate-400 py-10 text-center">Loading...</div>;
  if (!vehicle) return null;

  const isTrailer = vehicle.vehicle_type === 'trailer';

  const BASE_TYPES = isTrailer ? TRAILER_SERVICE_TYPES : VEHICLE_SERVICE_TYPES;
  const SERVICE_TYPES = [
    ...BASE_TYPES.filter((t) => t !== 'Other'),
    ...customServiceTypes.filter((t) => !BASE_TYPES.includes(t)),
    'Other',
  ];

  const addCustomType = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed || SERVICE_TYPES.includes(trimmed)) return;
    const updated = [...customServiceTypes, trimmed];
    setCustomServiceTypes(updated);
    localStorage.setItem('customServiceTypes', JSON.stringify(updated));
    setNewTypeInput('');
  };

  const removeCustomType = (name: string) => {
    const updated = customServiceTypes.filter((t) => t !== name);
    setCustomServiceTypes(updated);
    localStorage.setItem('customServiceTypes', JSON.stringify(updated));
  };

  const BASE_EXPENSE_CATEGORIES = EXPENSE_CATEGORIES.filter((c) => c !== 'other');
  const ALL_EXPENSE_CATEGORIES = [
    ...BASE_EXPENSE_CATEGORIES,
    ...customExpenseCategories.filter((c) => !BASE_EXPENSE_CATEGORIES.includes(c)),
    'other',
  ];

  const addExpenseCategory = (name: string) => {
    const trimmed = name.trim().toLowerCase();
    if (!trimmed || ALL_EXPENSE_CATEGORIES.includes(trimmed)) return;
    const updated = [...customExpenseCategories, trimmed];
    setCustomExpenseCategories(updated);
    localStorage.setItem('customExpenseCategories', JSON.stringify(updated));
    setNewCatInput('');
  };

  const removeExpenseCategory = (name: string) => {
    const updated = customExpenseCategories.filter((c) => c !== name);
    setCustomExpenseCategories(updated);
    localStorage.setItem('customExpenseCategories', JSON.stringify(updated));
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'summary', label: 'Summary' },
    ...(isTrailer
      ? [{ id: 'trips' as Tab, label: 'Trip Log' }]
      : [{ id: 'fuel' as Tab, label: 'Fuel' }]
    ),
    { id: 'maintenance', label: 'Maintenance' },
    { id: 'expenses', label: 'Expenses' },
    { id: 'parts', label: 'Parts' },
    { id: 'documents', label: 'Documents' },
    { id: 'analytics', label: 'Analytics' },
  ];

  const effectiveSpecs = { ...(vehicle.nhtsa_data || {}), ...(vehicle.specs_overrides || {}) };

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
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">
            {vehicle.nickname || `${vehicle.year} ${vehicle.make} ${vehicle.model}`}
          </h1>
          {isTrailer && (
            <span className="text-xs bg-amber-900/50 text-amber-300 border border-amber-700 px-2 py-0.5 rounded">Trailer</span>
          )}
        </div>
        {vehicle.nickname && (
          <p className="text-slate-400 text-sm">{vehicle.year} {vehicle.make} {vehicle.model}</p>
        )}
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
                ...(!isTrailer ? [['Fuel Type', vehicle.fuel_type]] : []),
                ...(isTrailer && vehicle.axle_count ? [['Axles', vehicle.axle_count]] : []),
                ...(vehicle.vin ? [['VIN', vehicle.vin]] : []),
              ] as [string, string | number][]
            ).map(([label, value]) => (
              <div key={label} className="flex justify-between text-sm border-b border-slate-700 pb-2 last:border-0 last:pb-0">
                <span className="text-slate-400">{label}</span>
                <span className="text-white font-mono text-right">{value}</span>
              </div>
            ))}
            <MileageRow vehicle={vehicle} onUpdate={(v) => setVehicle(v)} />
          </div>

          {Object.keys(effectiveSpecs).length > 0 && (
            <div className="card sm:col-span-2">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-semibold text-white">Vehicle Specs</h2>
                <button onClick={() => {
                  setSpecsForm(Object.fromEntries(Object.entries(effectiveSpecs).map(([k, v]) => [k, String(v)])));
                  setSpecsEditModal(true);
                }} className="btn-secondary text-xs py-1 px-3">Edit Specs</button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                {(effectiveSpecs.engine_model || effectiveSpecs.engine_cylinders || effectiveSpecs.engine_displacement_l || effectiveSpecs.fuel_type) && (
                  <div>
                    <h3 className="text-xs font-semibold text-teal-400 uppercase tracking-wider mb-2">Engine</h3>
                    <div className="space-y-1.5">
                      {[
                        effectiveSpecs.engine_model && ['Model', effectiveSpecs.engine_model],
                        effectiveSpecs.engine_displacement_l && ['Displacement', `${effectiveSpecs.engine_displacement_l}L`],
                        effectiveSpecs.engine_cylinders && ['Cylinders', effectiveSpecs.engine_cylinders],
                        effectiveSpecs.engine_hp && ['Horsepower', `${effectiveSpecs.engine_hp} hp`],
                        effectiveSpecs.turbo && ['Turbocharged', effectiveSpecs.turbo],
                        effectiveSpecs.fuel_type && ['Fuel', effectiveSpecs.fuel_type],
                      ].filter(Boolean).map(([label, value]) => (
                        <div key={label as string} className="flex justify-between text-sm">
                          <span className="text-slate-400">{label as string}</span>
                          <span className={`text-right ml-4 text-sm ${vehicle.specs_overrides?.[label as string] !== undefined ? 'text-teal-300' : 'text-white'}`}>{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(effectiveSpecs.drive_type || effectiveSpecs.transmission_type || effectiveSpecs.transmission_speeds) && (
                  <div>
                    <h3 className="text-xs font-semibold text-teal-400 uppercase tracking-wider mb-2">Drivetrain</h3>
                    <div className="space-y-1.5">
                      {[
                        effectiveSpecs.drive_type && ['Drive Type', effectiveSpecs.drive_type],
                        effectiveSpecs.transmission_type && ['Transmission', effectiveSpecs.transmission_type],
                        effectiveSpecs.transmission_speeds && ['Speeds', effectiveSpecs.transmission_speeds],
                      ].filter(Boolean).map(([label, value]) => (
                        <div key={label as string} className="flex justify-between text-sm">
                          <span className="text-slate-400">{label as string}</span>
                          <span className={`text-right ml-4 text-sm ${vehicle.specs_overrides?.[label as string] !== undefined ? 'text-teal-300' : 'text-white'}`}>{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {(effectiveSpecs.body_class || effectiveSpecs.cab_type || effectiveSpecs.trim || effectiveSpecs.series || effectiveSpecs.gvwr) && (
                  <div>
                    <h3 className="text-xs font-semibold text-teal-400 uppercase tracking-wider mb-2">Body & Trim</h3>
                    <div className="space-y-1.5">
                      {[
                        effectiveSpecs.body_class && ['Body', effectiveSpecs.body_class],
                        effectiveSpecs.cab_type && ['Cab', effectiveSpecs.cab_type],
                        effectiveSpecs.doors && ['Doors', effectiveSpecs.doors],
                        effectiveSpecs.series && ['Series', effectiveSpecs.series],
                        effectiveSpecs.trim && ['Trim', effectiveSpecs.trim],
                        effectiveSpecs.gvwr && ['GVWR', effectiveSpecs.gvwr],
                        effectiveSpecs.plant_city && effectiveSpecs.plant_country && ['Built In', `${effectiveSpecs.plant_city}, ${effectiveSpecs.plant_country}`],
                      ].filter(Boolean).map(([label, value]) => (
                        <div key={label as string} className="flex justify-between text-sm">
                          <span className="text-slate-400">{label as string}</span>
                          <span className={`text-right ml-4 text-sm ${vehicle.specs_overrides?.[label as string] !== undefined ? 'text-teal-300' : 'text-white'}`}>{String(value)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TRIP LOG ────────────────────────────────────────────────────────── */}
      {activeTab === 'trips' && (
        <div className="space-y-5">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Trip Log</h2>
            <button onClick={() => {
              setEditTrip(null);
              setTripForm({ date: today(), miles: 0, destination: '', notes: '' });
              setFormError('');
              setTripModal(true);
            }} className="btn-primary text-sm">+ Log Trip</button>
          </div>

          {tripStats && (
            <div className="grid grid-cols-3 gap-3">
              {[
                { label: 'Total Miles', value: tripStats.total_miles.toLocaleString() + ' mi' },
                { label: 'Total Trips', value: tripStats.trip_count },
                { label: 'Last Trip', value: tripStats.last_trip_date ? fmtDate(tripStats.last_trip_date) : '—' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-slate-800 rounded-lg p-3 border border-slate-700">
                  <p className="text-slate-400 text-xs">{label}</p>
                  <p className="text-white font-semibold mt-0.5">{value}</p>
                </div>
              ))}
            </div>
          )}

          {tripEntries.length === 0 ? (
            <div className="card text-center py-10 text-slate-400">No trips logged yet.</div>
          ) : (
            <div className="card overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700">
                    {['Date', 'Miles', 'Destination', 'Notes', ''].map((h) => (
                      <th key={h} className="px-4 py-2 text-left text-slate-400 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tripEntries.map((t) => (
                    <tr key={t.id} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                      <td className="px-4 py-3 text-slate-300">{fmtDate(t.date)}</td>
                      <td className="px-4 py-3 text-white font-medium">{t.miles.toLocaleString()} mi</td>
                      <td className="px-4 py-3 text-slate-300">{t.destination || '—'}</td>
                      <td className="px-4 py-3 text-slate-400">{t.notes || '—'}</td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => {
                          setEditTrip(t);
                          setTripForm({ date: t.date, miles: t.miles, destination: t.destination || '', notes: t.notes || '' });
                          setFormError('');
                          setTripModal(true);
                        }} className="text-slate-400 hover:text-white text-xs mr-3">Edit</button>
                        <button onClick={async () => {
                          if (!confirm('Delete this trip? This will subtract the miles from the odometer.')) return;
                          await apiClient.deleteTrip(id, t.id);
                          const v = await apiClient.getVehicle(id);
                          setVehicle(v);
                          loadTrips();
                          addToast('success', 'Trip deleted');
                        }} className="text-red-400 hover:text-red-300 text-xs">Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Modal isOpen={tripModal} onClose={() => setTripModal(false)} title={editTrip ? 'Edit Trip' : 'Log Trip'}>
            <form onSubmit={async (e) => {
              e.preventDefault();
              setSaving(true);
              setFormError('');
              try {
                const payload = { ...tripForm, miles: Number(tripForm.miles), destination: tripForm.destination || undefined, notes: tripForm.notes || undefined };
                if (editTrip) {
                  await apiClient.updateTrip(id, editTrip.id, payload);
                } else {
                  await apiClient.createTrip(id, payload);
                }
                const v = await apiClient.getVehicle(id);
                setVehicle(v);
                setTripModal(false);
                loadTrips();
                addToast('success', editTrip ? 'Trip updated' : 'Trip logged');
              } catch {
                setFormError('Failed to save trip');
              } finally {
                setSaving(false);
              }
            }} className="space-y-4">
              <FormError msg={formError} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Date *</label>
                  <input type="date" className="input-field" value={tripForm.date} onChange={(e) => setTripForm((p) => ({ ...p, date: e.target.value }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Miles *</label>
                  <input type="number" className="input-field" min="0" step="0.1" value={tripForm.miles} onChange={(e) => setTripForm((p) => ({ ...p, miles: Number(e.target.value) }))} required />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Destination</label>
                <input className="input-field" placeholder="e.g. Camping trip, job site" value={tripForm.destination} onChange={(e) => setTripForm((p) => ({ ...p, destination: e.target.value }))} />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Notes</label>
                <input className="input-field" placeholder="Optional notes" value={tripForm.notes} onChange={(e) => setTripForm((p) => ({ ...p, notes: e.target.value }))} />
              </div>
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={saving} className="btn-primary flex-1">{saving ? 'Saving...' : editTrip ? 'Update Trip' : 'Log Trip'}</button>
                <button type="button" onClick={() => setTripModal(false)} className="btn-secondary flex-1">Cancel</button>
              </div>
            </form>
          </Modal>
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
              <div className="flex items-center justify-between">
                <FormError msg={formError} />
                <ScanReceiptButton onScan={async (file) => {
                  setFormError('');
                  try {
                    const r = await apiClient.ocrFuel(file);
                    if (r.date) setFuelForm((p) => ({ ...p, date: r.date }));
                    if (r.gallons != null) setFuelForm((p) => ({ ...p, gallons: r.gallons }));
                    if (r.cost != null) setFuelForm((p) => ({ ...p, cost: r.cost }));
                    if (r.location) setFuelForm((p) => ({ ...p, location: r.location }));
                    if (r.mileage != null) setFuelForm((p) => ({ ...p, mileage: r.mileage }));
                    addToast('success', 'Receipt scanned — review and save');
                  } catch (err: any) {
                    setFormError(err.response?.data?.detail || 'Scan failed');
                  }
                }} />
              </div>
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
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm text-slate-300">Location</label>
                  <button type="button" onClick={handleGpsLocation} disabled={gpsLoading}
                    className="flex items-center gap-1 text-xs text-teal-400 hover:text-teal-300 disabled:opacity-50 transition-colors">
                    {gpsLoading
                      ? <><span className="animate-spin">⟳</span> Locating...</>
                      : <><span>📍</span> Use my location</>}
                  </button>
                </div>
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
                  setReminderTrigger('interval');
                  setReminderForm({ service_type: 'Oil Change', interval_miles: '', interval_days: '', target_mileage: '', reminder_miles: '500' });
                  setCustomTypesOpen(false);
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
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white">{r.service_type}</p>
                          <p className="text-slate-400 text-xs mt-1">
                            {r.target_mileage
                              ? `At ${r.target_mileage.toLocaleString()} mi`
                              : [
                                  r.interval_miles ? `Every ${r.interval_miles.toLocaleString()} mi` : '',
                                  r.interval_days ? `Every ${r.interval_days} days` : '',
                                ].filter(Boolean).join(' · ')}
                          </p>
                          {r.next_due_mileage ? (
                            <p className="text-slate-400 text-xs mt-0.5">
                              Due at {r.next_due_mileage.toLocaleString()} mi
                              {r.reminder_miles ? ` · alert at ${(r.next_due_mileage - r.reminder_miles).toLocaleString()} mi` : ''}
                            </p>
                          ) : !r.target_mileage && (
                            <button
                              type="button"
                              onClick={() => startReminderNow(r)}
                              className="mt-1.5 text-xs text-teal-400 hover:text-teal-300 border border-teal-800 hover:border-teal-700 bg-teal-900/20 px-2 py-0.5 rounded transition-colors"
                            >
                              ▶ Start from now
                            </button>
                          )}
                          {(() => {
                            const eta = reminderEta(r);
                            if (!eta) return null;
                            const mo = eta.estDate.toLocaleString('default', { month: 'short', day: 'numeric' });
                            return (
                              <p className="text-teal-400 text-xs mt-0.5">
                                ~{eta.daysLeft} days · est. {mo}
                              </p>
                            );
                          })()}
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
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm text-slate-300">Service Type *</label>
                  <button type="button" onClick={() => setCustomTypesOpen((o) => !o)}
                    className="text-xs text-slate-400 hover:text-teal-400 transition-colors">
                    {customTypesOpen ? 'Done' : '✎ Edit list'}
                  </button>
                </div>
                <select className="input-field" value={maintForm.type}
                  onChange={(e) => { setMaintForm((p) => ({ ...p, type: e.target.value })); setMaintOther(''); }}>
                  {SERVICE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                {maintForm.type === 'Other' && (
                  <input className="input-field mt-2" placeholder="Describe the service (e.g. Differential Flush)"
                    value={maintOther} onChange={(e) => setMaintOther(e.target.value)} autoFocus />
                )}
                {customTypesOpen && (
                  <div className="mt-2 p-3 bg-slate-800 rounded-lg border border-slate-700 space-y-2">
                    {customServiceTypes.length === 0 && (
                      <p className="text-slate-500 text-xs">No custom types yet.</p>
                    )}
                    {customServiceTypes.map((t) => (
                      <div key={t} className="flex items-center justify-between text-sm">
                        <span className="text-slate-300">{t}</span>
                        <button type="button" onClick={() => removeCustomType(t)}
                          className="text-slate-500 hover:text-red-400 text-base leading-none transition-colors">×</button>
                      </div>
                    ))}
                    <div className="flex gap-2 pt-1">
                      <input className="input-field flex-1 text-sm py-1" placeholder="Add type..."
                        value={newTypeInput} onChange={(e) => setNewTypeInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomType(newTypeInput); } }} />
                      <button type="button" onClick={() => addCustomType(newTypeInput)}
                        className="btn-secondary text-sm px-3 py-1">Add</button>
                    </div>
                  </div>
                )}
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
                <label className="block text-sm text-slate-300 mb-1">
                  Notes{maintForm.type === 'Other' && !maintOther.trim() ? ' *' : ''}
                </label>
                <textarea className="input-field" rows={maintForm.type === 'Other' ? 3 : 2} value={maintForm.notes}
                  onChange={(e) => setMaintForm((p) => ({ ...p, notes: e.target.value }))}
                  placeholder={maintForm.type === 'Other' ? 'Any additional details about the service...' : ''} />
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
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm text-slate-300">Service Type *</label>
                  <button type="button" onClick={() => setCustomTypesOpen((o) => !o)}
                    className="text-xs text-slate-400 hover:text-teal-400 transition-colors">
                    {customTypesOpen ? 'Done' : '✎ Edit list'}
                  </button>
                </div>
                <select className="input-field" value={reminderForm.service_type}
                  onChange={(e) => setReminderForm((p) => ({ ...p, service_type: e.target.value }))}>
                  {SERVICE_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                {customTypesOpen && (
                  <div className="mt-2 p-3 bg-slate-800 rounded-lg border border-slate-700 space-y-2">
                    {customServiceTypes.length === 0 && (
                      <p className="text-slate-500 text-xs">No custom types yet.</p>
                    )}
                    {customServiceTypes.map((t) => (
                      <div key={t} className="flex items-center justify-between text-sm">
                        <span className="text-slate-300">{t}</span>
                        <button type="button" onClick={() => removeCustomType(t)}
                          className="text-slate-500 hover:text-red-400 text-base leading-none transition-colors">×</button>
                      </div>
                    ))}
                    <div className="flex gap-2 pt-1">
                      <input className="input-field flex-1 text-sm py-1" placeholder="Add type..."
                        value={newTypeInput} onChange={(e) => setNewTypeInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustomType(newTypeInput); } }} />
                      <button type="button" onClick={() => addCustomType(newTypeInput)}
                        className="btn-secondary text-sm px-3 py-1">Add</button>
                    </div>
                  </div>
                )}
              </div>

              {/* Trigger type toggle */}
              <div>
                <label className="block text-sm text-slate-300 mb-2">Schedule</label>
                <div className="grid grid-cols-2 gap-2">
                  {(['interval', 'target'] as const).map((t) => (
                    <button key={t} type="button" onClick={() => setReminderTrigger(t)}
                      className={`py-2 px-3 rounded border text-sm font-medium transition-colors ${
                        reminderTrigger === t ? 'border-teal-500 bg-teal-900/30 text-teal-300' : 'border-slate-600 text-slate-400 hover:border-slate-500'
                      }`}>
                      {t === 'interval' ? 'Recurring interval' : 'At mileage'}
                    </button>
                  ))}
                </div>
              </div>

              {reminderTrigger === 'interval' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">Every (miles)</label>
                    <input type="number" className="input-field" min="1" placeholder="e.g. 5000"
                      value={reminderForm.interval_miles}
                      onChange={(e) => setReminderForm((p) => ({ ...p, interval_miles: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-sm text-slate-300 mb-1">Every (days)</label>
                    <input type="number" className="input-field" min="1" placeholder="e.g. 90"
                      value={reminderForm.interval_days}
                      onChange={(e) => setReminderForm((p) => ({ ...p, interval_days: e.target.value }))} />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Target odometer (miles) *</label>
                  <input type="number" className="input-field" min="1" placeholder="e.g. 50000"
                    value={reminderForm.target_mileage}
                    onChange={(e) => setReminderForm((p) => ({ ...p, target_mileage: e.target.value }))} />
                  <p className="text-slate-500 text-xs mt-1">Current odometer: {vehicle?.current_mileage.toLocaleString()} mi</p>
                </div>
              )}

              <div>
                <label className="block text-sm text-slate-300 mb-1">Alert me when within (miles)</label>
                <input type="number" className="input-field" min="1" placeholder="500"
                  value={reminderForm.reminder_miles}
                  onChange={(e) => setReminderForm((p) => ({ ...p, reminder_miles: e.target.value }))} />
                {(() => {
                  const avg = avgMilesPerDay();
                  const lead = Number(reminderForm.reminder_miles) || 500;
                  if (!avg) return <p className="text-slate-500 text-xs mt-1">Add fuel entries to see time estimates.</p>;
                  const days = Math.round(lead / avg);
                  return <p className="text-teal-400 text-xs mt-1">≈ {days} days before due at current driving pace</p>;
                })()}
              </div>

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
              <div className="flex items-center justify-between">
                <FormError msg={formError} />
                <ScanReceiptButton onScan={async (file) => {
                  setFormError('');
                  try {
                    const r = await apiClient.ocrExpense(file);
                    if (r.date) setExpenseForm((p) => ({ ...p, date: r.date }));
                    if (r.amount != null) setExpenseForm((p) => ({ ...p, amount: r.amount }));
                    if (r.description) setExpenseForm((p) => ({ ...p, description: r.description }));
                    if (r.category) setExpenseForm((p) => ({ ...p, category: r.category }));
                    addToast('success', 'Receipt scanned — review and save');
                  } catch (err: any) {
                    setFormError(err.response?.data?.detail || 'Scan failed');
                  }
                }} />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-sm text-slate-300">Category *</label>
                  <button type="button" onClick={() => setExpenseCatsOpen((o) => !o)}
                    className="text-xs text-slate-400 hover:text-teal-400 transition-colors">
                    {expenseCatsOpen ? 'Done' : '✎ Edit list'}
                  </button>
                </div>
                <select className="input-field" value={expenseForm.category}
                  onChange={(e) => setExpenseForm((p) => ({ ...p, category: e.target.value }))}>
                  {ALL_EXPENSE_CATEGORIES.map((c) => (
                    <option key={c} value={c} className="capitalize">{c}</option>
                  ))}
                </select>
                {expenseCatsOpen && (
                  <div className="mt-2 p-3 bg-slate-800 rounded-lg border border-slate-700 space-y-2">
                    {customExpenseCategories.length === 0 && (
                      <p className="text-slate-500 text-xs">No custom categories yet.</p>
                    )}
                    {customExpenseCategories.map((c) => (
                      <div key={c} className="flex items-center justify-between text-sm">
                        <span className="text-slate-300 capitalize">{c}</span>
                        <button type="button" onClick={() => removeExpenseCategory(c)}
                          className="text-slate-500 hover:text-red-400 text-base leading-none transition-colors">×</button>
                      </div>
                    ))}
                    <div className="flex gap-2 pt-1">
                      <input className="input-field flex-1 text-sm py-1" placeholder="Add category..."
                        value={newCatInput} onChange={(e) => setNewCatInput(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addExpenseCategory(newCatInput); } }} />
                      <button type="button" onClick={() => addExpenseCategory(newCatInput)}
                        className="btn-secondary text-sm px-3 py-1">Add</button>
                    </div>
                  </div>
                )}
              </div>
              <div>
                  <label className="block text-sm text-slate-300 mb-1">Amount ($) *</label>
                  <input type="number" className="input-field" min="0" step="0.01" value={expenseForm.amount}
                    onChange={(e) => setExpenseForm((p) => ({ ...p, amount: Number(e.target.value) }))} required />
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

      {/* ── PARTS ───────────────────────────────────────────────────────────────── */}
      {activeTab === 'parts' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Parts & Part Numbers</h2>
            <button onClick={() => {
              setEditPart(null);
              setPartForm({ name: '', part_number: '', brand: '', category: 'filters', notes: '' });
              setFormError('');
              setPartModal(true);
            }} className="btn-primary text-sm">+ Add Part</button>
          </div>

          {parts.length === 0 ? (
            <div className="card text-center py-10 text-slate-400">No parts added yet.</div>
          ) : (
            <div className="space-y-3">
              {(['filters', 'engine', 'drivetrain', 'brakes', 'suspension', 'electrical', 'trailer', 'other'] as const).map((cat) => {
                const catParts = parts.filter((p) => p.category === cat);
                if (catParts.length === 0) return null;
                return (
                  <div key={cat} className="card">
                    <h3 className="text-xs font-semibold text-teal-400 uppercase tracking-wider mb-3 capitalize">{cat}</h3>
                    <div className="space-y-2">
                      {catParts.map((p) => (
                        <div key={p.id} className="flex items-start justify-between gap-4 text-sm border-b border-slate-700 pb-2 last:border-0 last:pb-0">
                          <div className="min-w-0">
                            <p className="text-white font-medium">{p.name}</p>
                            <div className="flex flex-wrap gap-3 mt-0.5 text-slate-400">
                              {p.brand && <span>{p.brand}</span>}
                              {p.part_number && <span className="font-mono text-teal-300">#{p.part_number}</span>}
                              {p.notes && <span className="italic">{p.notes}</span>}
                            </div>
                          </div>
                          <div className="flex gap-2 flex-shrink-0">
                            <button onClick={() => {
                              setEditPart(p);
                              setPartForm({ name: p.name, part_number: p.part_number || '', brand: p.brand || '', category: p.category, notes: p.notes || '' });
                              setFormError('');
                              setPartModal(true);
                            }} className="text-slate-400 hover:text-white transition-colors text-xs">Edit</button>
                            <button onClick={async () => {
                              if (!confirm('Delete this part?')) return;
                              await apiClient.deletePart(id, p.id);
                              loadParts();
                              addToast('success', 'Part deleted');
                            }} className="text-red-400 hover:text-red-300 transition-colors text-xs">Delete</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <Modal isOpen={partModal} onClose={() => setPartModal(false)} title={editPart ? 'Edit Part' : 'Add Part'}>
            <form onSubmit={async (e) => {
              e.preventDefault();
              setSaving(true);
              setFormError('');
              try {
                const payload = { ...partForm, part_number: partForm.part_number || undefined, brand: partForm.brand || undefined, notes: partForm.notes || undefined };
                if (editPart) {
                  await apiClient.updatePart(id, editPart.id, payload);
                } else {
                  await apiClient.createPart(id, payload);
                }
                setPartModal(false);
                loadParts();
                addToast('success', editPart ? 'Part updated' : 'Part added');
              } catch {
                setFormError('Failed to save part');
              } finally {
                setSaving(false);
              }
            }} className="space-y-4">
              <FormError msg={formError} />
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="block text-sm text-slate-300 mb-1">Part Name *</label>
                  <input className="input-field" placeholder="e.g. Oil Filter" value={partForm.name} onChange={(e) => setPartForm((p) => ({ ...p, name: e.target.value }))} required />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Part Number</label>
                  <input className="input-field font-mono" placeholder="e.g. PF63E" value={partForm.part_number} onChange={(e) => setPartForm((p) => ({ ...p, part_number: e.target.value }))} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Brand</label>
                  <input className="input-field" placeholder="e.g. ACDelco" value={partForm.brand} onChange={(e) => setPartForm((p) => ({ ...p, brand: e.target.value }))} />
                </div>
                <div className="col-span-2">
                  <label className="block text-sm text-slate-300 mb-1">Category</label>
                  <select className="input-field" value={partForm.category} onChange={(e) => setPartForm((p) => ({ ...p, category: e.target.value }))}>
                    {['filters', 'engine', 'drivetrain', 'brakes', 'suspension', 'electrical', 'trailer', 'other'].map((c) => (
                      <option key={c} value={c} className="capitalize">{c}</option>
                    ))}
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="block text-sm text-slate-300 mb-1">Notes</label>
                  <input className="input-field" placeholder="Optional notes" value={partForm.notes} onChange={(e) => setPartForm((p) => ({ ...p, notes: e.target.value }))} />
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={saving} className="btn-primary flex-1">{saving ? 'Saving...' : editPart ? 'Update' : 'Add Part'}</button>
                <button type="button" onClick={() => setPartModal(false)} className="btn-secondary flex-1">Cancel</button>
              </div>
            </form>
          </Modal>
        </div>
      )}

      {/* ── SPECS EDIT MODAL ─────────────────────────────────────────────────────── */}
      <Modal isOpen={specsEditModal} onClose={() => setSpecsEditModal(false)} title="Edit Vehicle Specs">
        <form onSubmit={async (e) => {
          e.preventDefault();
          setSaving(true);
          try {
            const overrides: Record<string, string> = {};
            const base = vehicle.nhtsa_data || {};
            for (const [k, v] of Object.entries(specsForm)) {
              if (v !== String(base[k] ?? '')) overrides[k] = v;
            }
            const updated = await apiClient.updateSpecsOverrides(id, overrides);
            setVehicle(updated);
            setSpecsEditModal(false);
            addToast('success', 'Specs updated');
          } catch {
            setFormError('Failed to save');
          } finally {
            setSaving(false);
          }
        }} className="space-y-3">
          <p className="text-slate-400 text-xs">Overridden values shown in teal on the summary tab.</p>
          {([
            ['engine_model', 'Engine Model'],
            ['engine_displacement_l', 'Displacement (L)'],
            ['engine_cylinders', 'Cylinders'],
            ['engine_hp', 'Horsepower'],
            ['turbo', 'Turbocharged'],
            ['fuel_type', 'Fuel Type'],
            ['drive_type', 'Drive Type'],
            ['transmission_type', 'Transmission Style'],
            ['transmission_speeds', 'Transmission Speeds'],
            ['body_class', 'Body Class'],
            ['cab_type', 'Cab Type'],
            ['doors', 'Doors'],
            ['series', 'Series'],
            ['trim', 'Trim'],
            ['gvwr', 'GVWR'],
          ] as [string, string][]).map(([key, label]) => (
            <div key={key}>
              <label className="block text-xs text-slate-400 mb-1">{label}</label>
              <input
                className="input-field text-sm"
                value={specsForm[key] || ''}
                onChange={(e) => setSpecsForm((p) => ({ ...p, [key]: e.target.value }))}
              />
            </div>
          ))}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving} className="btn-primary flex-1">{saving ? 'Saving...' : 'Save Overrides'}</button>
            <button type="button" onClick={() => setSpecsEditModal(false)} className="btn-secondary flex-1">Cancel</button>
          </div>
        </form>
      </Modal>

      {/* ── ANALYTICS ───────────────────────────────────────────────────────────── */}
      {activeTab === 'analytics' && (
        <AnalyticsTab
          isTrailer={isTrailer}
          loading={analyticsLoading}
          fuelEntries={analyticsFuel}
          maintEntries={analyticsMaint}
          expenses={analyticsExpenses}
          tripEntries={analyticsTrips}
        />
      )}
    </div>
  );
}
