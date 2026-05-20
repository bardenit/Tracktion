import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';
import Modal from '../components/Modal';

interface Vehicle {
  id: number;
  make: string;
  model: string;
  year: number;
  vin?: string;
  current_mileage: number;
  fuel_type: string;
}

const FUEL_TYPES = ['gasoline', 'diesel', 'electric', 'hybrid', 'plug-in hybrid'];

const blankForm = () => ({
  make: '',
  model: '',
  year: new Date().getFullYear(),
  vin: '',
  current_mileage: 0,
  fuel_type: 'gasoline',
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
    setShowModal(true);
  };

  const openEdit = (v: Vehicle) => {
    setEditingVehicle(v);
    setForm({
      make: v.make,
      model: v.model,
      year: v.year,
      vin: v.vin || '',
      current_mileage: v.current_mileage,
      fuel_type: v.fuel_type,
    });
    setError('');
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const payload = { ...form, vin: form.vin || undefined };
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
      const val =
        key === 'year' || key === 'current_mileage' ? Number(e.target.value) : e.target.value;
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
                <div>
                  <h2 className="text-lg font-semibold text-white">
                    {v.year} {v.make} {v.model}
                  </h2>
                  {v.vin && (
                    <p className="text-slate-400 text-sm mt-0.5 font-mono">VIN: {v.vin}</p>
                  )}
                  <div className="flex flex-wrap gap-4 mt-2 text-sm text-slate-400">
                    <span>Mileage: {v.current_mileage.toLocaleString()} mi</span>
                    <span className="capitalize">Fuel: {v.fuel_type}</span>
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
            <div>
              <label className="block text-sm text-slate-300 mb-1">Fuel Type *</label>
              <select className="input-field" value={form.fuel_type} onChange={setField('fuel_type')}>
                {FUEL_TYPES.map((ft) => (
                  <option key={ft} value={ft}>
                    {ft}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-1">VIN (optional)</label>
            <input
              className="input-field font-mono"
              placeholder="17-character VIN"
              value={form.vin}
              onChange={setField('vin')}
              maxLength={17}
            />
          </div>
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
