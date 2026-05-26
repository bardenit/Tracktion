import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import Modal from '../components/Modal';
import VehiclePhoto from '../components/VehiclePhoto';

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
  nhtsa_data?: Record<string, unknown>;
  specs_overrides?: Record<string, unknown>;
}

const FUEL_TYPES = ['gasoline', 'diesel', 'electric', 'hybrid', 'plug-in hybrid'];

function mapNhtsaFuel(nhtsaFuel: string | null | undefined): string {
  if (!nhtsaFuel) return 'gasoline';
  const f = nhtsaFuel.toLowerCase();
  if (f.includes('electric') && f.includes('plug')) return 'plug-in hybrid';
  if (f.includes('electric')) return 'electric';
  if (f.includes('diesel')) return 'diesel';
  if (f.includes('hybrid')) return 'hybrid';
  return 'gasoline';
}

const blankForm = () => ({
  nickname: '',
  vehicle_type: 'vehicle',
  make: '',
  model: '',
  year: new Date().getFullYear(),
  vin: '',
  current_mileage: 0,
  fuel_type: 'gasoline',
  axle_count: '' as string | number,
});

export default function VehiclesPage() {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<Vehicle | null>(null);
  const [form, setForm] = useState(blankForm());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [vinLooking, setVinLooking] = useState(false);
  const [vinLookupDone, setVinLookupDone] = useState(false);

  const load = async () => {
    try {
      const data = await apiClient.listVehicles();
      setVehicles(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openAdd = () => {
    setEditingVehicle(null);
    setForm(blankForm());
    setError('');
    setVinLookupDone(false);
    setShowModal(true);
  };

  const openEdit = (v: Vehicle) => {
    setEditingVehicle(v);
    setForm({
      nickname: v.nickname || '',
      vehicle_type: v.vehicle_type || 'vehicle',
      make: v.make,
      model: v.model,
      year: v.year,
      vin: v.vin || '',
      current_mileage: v.current_mileage,
      fuel_type: v.fuel_type,
      axle_count: v.axle_count ?? '',
    });
    setError('');
    setVinLookupDone(false);
    setShowModal(true);
  };

  const handleVinLookup = async () => {
    if (form.vin.length !== 17) return;
    setVinLooking(true);
    setError('');
    try {
      const result = await apiClient.lookupVin(form.vin);
      const mappedFuel = mapNhtsaFuel(result.fuel_type);
      setForm((prev) => ({
        ...prev,
        make: result.make || prev.make,
        model: result.model || prev.model,
        year: result.year || prev.year,
        fuel_type: mappedFuel,
      }));
      setVinLookupDone(true);
    } catch {
      setError('VIN not found. Enter vehicle details manually.');
      setVinLookupDone(true);
    } finally {
      setVinLooking(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = {
        ...form,
        vin: form.vin || undefined,
        nickname: form.nickname || undefined,
        axle_count: form.axle_count !== '' ? Number(form.axle_count) : undefined,
      };
      if (editingVehicle) {
        await apiClient.updateVehicle(editingVehicle.id, payload);
      } else {
        await apiClient.createVehicle(payload);
      }
      setShowModal(false);
      load();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to save vehicle');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this vehicle and all its data? This cannot be undone.')) return;
    try {
      await apiClient.deleteVehicle(id);
      setVehicles((prev) => prev.filter((v) => v.id !== id));
    } catch (e) {
      console.error(e);
    }
  };

  const setField =
    (key: keyof ReturnType<typeof blankForm>) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      const numericKeys = ['year', 'current_mileage'];
      const val = numericKeys.includes(key) ? Number(e.target.value) : e.target.value;
      setForm((prev) => ({ ...prev, [key]: val }));
    };

  if (loading) {
    return <div className="text-slate-400 py-10 text-center">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Vehicles</h1>
        <button onClick={openAdd} className="btn-primary">
          + Add Vehicle
        </button>
      </div>

      {vehicles.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400 mb-4">No vehicles added yet.</p>
          <button onClick={openAdd} className="btn-primary">
            Add Your First Vehicle
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {vehicles.map((v) => (
            <div key={v.id} className="card">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-start gap-3">
                  <VehiclePhoto
                    vehicleId={v.id}
                    alt={`${v.year} ${v.make} ${v.model}`}
                    className="w-20 h-16 flex-shrink-0 hidden sm:block"
                  />
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-white">
                      {v.nickname ? v.nickname : `${v.year} ${v.make} ${v.model}`}
                    </h2>
                    {v.vehicle_type === 'trailer' && (
                      <span className="text-xs bg-amber-900/50 text-amber-300 border border-amber-700 px-2 py-0.5 rounded">Trailer</span>
                    )}
                  </div>
                  {v.nickname && (
                    <p className="text-slate-400 text-sm">{v.year} {v.make} {v.model}</p>
                  )}
                  {v.vin && (
                    <p className="text-slate-400 text-sm font-mono">VIN: {v.vin}</p>
                  )}
                  <div className="flex flex-wrap gap-4 mt-1 text-sm text-slate-400">
                    <span>Mileage: {v.current_mileage.toLocaleString()} mi</span>
                    {v.vehicle_type !== 'trailer' && <span className="capitalize">Fuel: {v.fuel_type}</span>}
                    {v.vehicle_type === 'trailer' && v.axle_count && <span>{v.axle_count}-axle</span>}
                  </div>
                </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => navigate(`/vehicles/${v.id}`)}
                    className="btn-secondary text-sm py-1.5 px-3"
                  >
                    View
                  </button>
                  <button
                    onClick={() => openEdit(v)}
                    className="btn-secondary text-sm py-1.5 px-3"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDelete(v.id)}
                    className="bg-red-900 hover:bg-red-800 text-red-200 text-sm py-1.5 px-3 rounded transition-colors"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        title={editingVehicle ? 'Edit Vehicle' : 'Add Vehicle'}
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="text-red-400 text-sm bg-red-900/30 border border-red-800 p-3 rounded">
              {error}
            </p>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">Type *</label>
              <select className="input-field" value={form.vehicle_type} onChange={setField('vehicle_type')}>
                <option value="vehicle">Vehicle</option>
                <option value="trailer">Trailer</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">Nickname</label>
              <input
                className="input-field"
                placeholder='e.g. "The Beast"'
                value={form.nickname}
                onChange={setField('nickname')}
              />
            </div>
          </div>

          {!editingVehicle && form.vehicle_type !== 'trailer' && (
            <div>
              <label className="block text-sm text-slate-300 mb-1">VIN Lookup (optional)</label>
              <div className="flex gap-2">
                <input
                  className="input-field font-mono flex-1"
                  placeholder="Enter 17-character VIN to auto-fill"
                  value={form.vin}
                  onChange={(e) => {
                    setField('vin')(e);
                    if (vinLookupDone) setVinLookupDone(false);
                  }}
                  maxLength={17}
                />
                <button
                  type="button"
                  onClick={handleVinLookup}
                  disabled={form.vin.length !== 17 || vinLooking}
                  className="btn-secondary px-4 whitespace-nowrap disabled:opacity-40"
                >
                  {vinLooking ? 'Looking up...' : 'Lookup'}
                </button>
              </div>
              {vinLookupDone && !error && (
                <p className="text-teal-400 text-xs mt-1">VIN decoded — review and edit fields below.</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">Make *</label>
              <input
                className="input-field"
                placeholder="e.g. Toyota"
                value={form.make}
                onChange={setField('make')}
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-300 mb-1">Model *</label>
              <input
                className="input-field"
                placeholder="e.g. Camry"
                value={form.model}
                onChange={setField('model')}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">Year *</label>
              <input
                className="input-field"
                type="number"
                min="1900"
                max={new Date().getFullYear() + 2}
                value={form.year}
                onChange={setField('year')}
                required
              />
            </div>
            {form.vehicle_type === 'trailer' ? (
              <div>
                <label className="block text-sm text-slate-300 mb-1">Axle Count</label>
                <input
                  className="input-field"
                  type="number"
                  min="1"
                  max="10"
                  placeholder="e.g. 2"
                  value={form.axle_count}
                  onChange={setField('axle_count')}
                />
              </div>
            ) : (
              <div>
                <label className="block text-sm text-slate-300 mb-1">Fuel Type *</label>
                <select className="input-field" value={form.fuel_type} onChange={setField('fuel_type')}>
                  {FUEL_TYPES.map((ft) => (
                    <option key={ft} value={ft}>{ft}</option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {editingVehicle && (
            <div>
              <label className="block text-sm text-slate-300 mb-1">VIN</label>
              <input
                className="input-field font-mono"
                placeholder="17-character VIN"
                value={form.vin}
                onChange={setField('vin')}
                maxLength={17}
              />
            </div>
          )}

          <div>
            <label className="block text-sm text-slate-300 mb-1">Current Mileage</label>
            <input
              className="input-field"
              type="number"
              min="0"
              value={form.current_mileage}
              onChange={setField('current_mileage')}
            />
          </div>
          <div className="flex gap-3 pt-1">
            <button type="submit" disabled={saving} className="btn-primary flex-1">
              {saving ? 'Saving...' : editingVehicle ? 'Update Vehicle' : 'Add Vehicle'}
            </button>
            <button type="button" onClick={() => setShowModal(false)} className="btn-secondary flex-1">
              Cancel
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
