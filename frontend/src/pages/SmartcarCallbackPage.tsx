import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiClient } from '../services/api';
import { useToastStore } from '../stores/toastStore';

interface SmartcarVehicle {
  id: string;
  make: string | null;
  model: string | null;
  year: number | null;
}

interface TracktionVehicle {
  id: number;
  nickname?: string;
  make: string;
  model: string;
  year: number;
}

export default function SmartcarCallbackPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const addToast = useToastStore((state) => state.addToast);

  const [status, setStatus] = useState<'loading' | 'mapping' | 'saving' | 'error'>('loading');
  const [error, setError] = useState('');
  const [smartcarUserId, setSmartcarUserId] = useState('');
  const [smartcarVehicles, setSmartcarVehicles] = useState<SmartcarVehicle[]>([]);
  const [tracktionVehicles, setTracktionVehicles] = useState<TracktionVehicle[]>([]);
  // Maps smartcar vehicle id → selected tracktion vehicle id (or '' for skip)
  const [mappings, setMappings] = useState<Record<string, string>>({});

  useEffect(() => {
    const userId = searchParams.get('user_id');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(`Smartcar authorization was denied: ${errorParam}`);
      setStatus('error');
      return;
    }

    if (!userId) {
      setError('No user ID received from Smartcar.');
      setStatus('error');
      return;
    }

    Promise.all([
      apiClient.connectSmartcarUser(userId),
      apiClient.listVehicles(),
    ]).then(([connectData, vehicles]) => {
      setSmartcarUserId(userId);
      setSmartcarVehicles(connectData.vehicles);
      setTracktionVehicles(vehicles);
      const initial: Record<string, string> = {};
      for (const v of connectData.vehicles) initial[v.id] = '';
      setMappings(initial);
      setStatus('mapping');
    }).catch((err) => {
      setError(err?.response?.data?.detail || 'Failed to connect to Smartcar. Check your credentials in Settings.');
      setStatus('error');
    });
  }, []);

  const handleSave = async () => {
    const pairs = Object.entries(mappings).filter(([, tracktionId]) => tracktionId !== '');
    if (pairs.length === 0) {
      addToast('error', 'Select at least one vehicle to link');
      return;
    }
    setStatus('saving');
    try {
      await Promise.all(pairs.map(([smartcarId, tracktionId]) =>
        apiClient.linkSmartcarVehicle(Number(tracktionId), {
          smartcar_vehicle_id: smartcarId,
          smartcar_user_id: smartcarUserId,
        })
      ));
      addToast('success', `${pairs.length} vehicle${pairs.length > 1 ? 's' : ''} linked to Smartcar`);
      navigate('/');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to save vehicle links.');
      setStatus('mapping');
    }
  };

  const vehicleLabel = (v: TracktionVehicle) => v.nickname || `${v.year} ${v.make} ${v.model}`;

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 max-w-lg w-full space-y-6">

        {status === 'loading' && (
          <div className="text-center space-y-3">
            <p className="text-white font-semibold">Connecting to Smartcar...</p>
            <p className="text-slate-400 text-sm">Loading your vehicles</p>
          </div>
        )}

        {status === 'error' && (
          <div className="space-y-4">
            <h2 className="text-white font-semibold text-lg">Connection Failed</h2>
            <p className="text-red-300 text-sm bg-red-900/20 border border-red-700/40 rounded p-3">{error}</p>
            <div className="flex gap-3">
              <button onClick={() => navigate('/settings')} className="btn-secondary flex-1">Settings</button>
              <button onClick={() => navigate('/')} className="btn-primary flex-1">Dashboard</button>
            </div>
          </div>
        )}

        {(status === 'mapping' || status === 'saving') && (
          <div className="space-y-5">
            <div>
              <h2 className="text-white font-semibold text-lg">Link Your Vehicles</h2>
              <p className="text-slate-400 text-sm mt-1">
                Match each vehicle from your connected account to a vehicle in Tracktion.
              </p>
            </div>

            <div className="space-y-4">
              {smartcarVehicles.map((sv) => (
                <div key={sv.id} className="bg-slate-700/50 rounded-lg p-4 space-y-2">
                  <p className="text-white text-sm font-medium">
                    {sv.year} {sv.make} {sv.model}
                    <span className="text-slate-500 font-mono text-xs ml-2">{sv.id.slice(0, 8)}…</span>
                  </p>
                  <select
                    className="input-field text-sm"
                    value={mappings[sv.id] ?? ''}
                    onChange={(e) => setMappings((m) => ({ ...m, [sv.id]: e.target.value }))}
                  >
                    <option value="">— Skip this vehicle —</option>
                    {tracktionVehicles.map((tv) => (
                      <option key={tv.id} value={String(tv.id)}>{vehicleLabel(tv)}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>

            {error && (
              <p className="text-red-300 text-sm bg-red-900/20 border border-red-700/40 rounded p-3">{error}</p>
            )}

            <div className="flex gap-3">
              <button onClick={() => navigate('/')} className="btn-secondary flex-1">Cancel</button>
              <button onClick={handleSave} disabled={status === 'saving'} className="btn-primary flex-1">
                {status === 'saving' ? 'Saving...' : 'Link Vehicles'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
