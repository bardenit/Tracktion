import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { apiClient } from '../services/api';

type Tab = 'account' | 'database';
type DbType = 'sqlite' | 'postgresql' | 'mysql';

const DEFAULT_PORTS: Record<string, number> = { postgresql: 5432, mysql: 3306 };

export default function SettingsPage() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);

  const [activeTab, setActiveTab] = useState<Tab>('account');

  // Password change state
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [pwStatus, setPwStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  // DB settings state
  const [dbType, setDbType] = useState<DbType>('sqlite');
  const [dbHost, setDbHost] = useState('');
  const [dbPort, setDbPort] = useState('');
  const [dbName, setDbName] = useState('');
  const [dbUser, setDbUser] = useState('');
  const [dbPass, setDbPass] = useState('');
  const [dbLoading, setDbLoading] = useState(false);
  const [dbStatus, setDbStatus] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);

  useEffect(() => {
    if (activeTab !== 'database') return;
    apiClient.getDbSettings().then((s) => {
      setDbType((s.type as DbType) || 'sqlite');
      setDbHost(s.host || '');
      setDbPort(s.port ? String(s.port) : '');
      setDbName(s.database || '');
      setDbUser(s.username || '');
    }).catch(() => {});
  }, [activeTab]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setPwStatus({ type: 'error', msg: 'New passwords do not match' });
      return;
    }
    setPwLoading(true);
    setPwStatus(null);
    try {
      await apiClient.changePassword(currentPw, newPw);
      setPwStatus({ type: 'success', msg: 'Password updated successfully' });
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
    } catch (err: any) {
      setPwStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to update password' });
    } finally {
      setPwLoading(false);
    }
  };

  const buildPayload = () => ({
    type: dbType,
    host: dbHost || undefined,
    port: dbPort ? Number(dbPort) : (DEFAULT_PORTS[dbType] || undefined),
    database: dbName || undefined,
    username: dbUser || undefined,
    password: dbPass || undefined,
  });

  const handleTestDb = async () => {
    setDbLoading(true);
    setDbStatus(null);
    try {
      const result = await apiClient.testDbConnection(buildPayload());
      setDbStatus(result.success
        ? { type: 'success', msg: 'Connection successful!' }
        : { type: 'error', msg: result.error || 'Connection failed' });
    } catch {
      setDbStatus({ type: 'error', msg: 'Test request failed' });
    } finally {
      setDbLoading(false);
    }
  };

  const handleSaveDb = async () => {
    setDbLoading(true);
    setDbStatus(null);
    try {
      const result = await apiClient.saveDbSettings(buildPayload());
      setDbStatus({ type: 'info', msg: result.message });
      setDbPass('');
    } catch (err: any) {
      setDbStatus({ type: 'error', msg: err.response?.data?.detail || 'Save failed' });
    } finally {
      setDbLoading(false);
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'account', label: 'Account' },
    { id: 'database', label: 'Database' },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <div className="border-b border-slate-700">
        <nav className="flex">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === t.id
                  ? 'border-teal-500 text-teal-400'
                  : 'border-transparent text-slate-400 hover:text-white'
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'account' && (
        <div className="space-y-4 max-w-md">
          <div className="card space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Account</h2>
            <p className="text-white">{user?.email}</p>
            <button
              onClick={handleLogout}
              className="bg-red-900 hover:bg-red-800 text-red-200 px-4 py-2 rounded transition-colors text-sm"
            >
              Sign Out
            </button>
          </div>

          <div className="card space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Change Password</h2>

            {pwStatus && (
              <div className={`p-3 rounded text-sm ${
                pwStatus.type === 'success'
                  ? 'bg-green-900/30 border border-green-700 text-green-300'
                  : 'bg-red-900/30 border border-red-700 text-red-300'
              }`}>
                {pwStatus.msg}
              </div>
            )}

            <form onSubmit={handleChangePassword} className="space-y-3">
              <div>
                <label className="block text-sm text-slate-300 mb-1">Current Password</label>
                <input
                  type="password"
                  className="input-field"
                  value={currentPw}
                  onChange={(e) => setCurrentPw(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">New Password</label>
                <input
                  type="password"
                  className="input-field"
                  placeholder="At least 8 characters"
                  value={newPw}
                  onChange={(e) => setNewPw(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Confirm New Password</label>
                <input
                  type="password"
                  className="input-field"
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  required
                />
              </div>
              <button type="submit" disabled={pwLoading} className="btn-primary w-full">
                {pwLoading ? 'Updating...' : 'Update Password'}
              </button>
            </form>
          </div>
        </div>
      )}

      {activeTab === 'database' && (
        <div className="card max-w-lg space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">Database</h2>
            <p className="text-slate-500 text-xs">Changes require a container restart to take effect.</p>
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Database Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(['sqlite', 'postgresql', 'mysql'] as DbType[]).map((t) => (
                <button
                  key={t}
                  onClick={() => {
                    setDbType(t);
                    setDbStatus(null);
                    if (DEFAULT_PORTS[t]) setDbPort(String(DEFAULT_PORTS[t]));
                  }}
                  className={`py-2 px-3 rounded border text-sm font-medium transition-colors ${
                    dbType === t
                      ? 'border-teal-500 bg-teal-900/30 text-teal-300'
                      : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }`}
                >
                  {t === 'sqlite' ? 'SQLite' : t === 'postgresql' ? 'PostgreSQL' : 'MySQL'}
                </button>
              ))}
            </div>
          </div>

          {dbType === 'sqlite' ? (
            <div className="bg-slate-700/50 rounded p-4 text-sm">
              <p className="text-slate-300 font-medium mb-1">SQLite — Zero configuration</p>
              <p className="text-slate-400">Data stored in <span className="font-mono text-teal-300">/app/data/tracktion.db</span> inside the container volume. No setup required.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label className="block text-sm text-slate-300 mb-1">Host</label>
                  <input className="input-field" placeholder="e.g. 10.10.10.5" value={dbHost} onChange={(e) => setDbHost(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Port</label>
                  <input className="input-field" type="number" value={dbPort} onChange={(e) => setDbPort(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Database Name</label>
                <input className="input-field" placeholder="e.g. vehicle_tracker" value={dbName} onChange={(e) => setDbName(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Username</label>
                  <input className="input-field" value={dbUser} onChange={(e) => setDbUser(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Password</label>
                  <input className="input-field" type="password" placeholder="Enter to change" value={dbPass} onChange={(e) => setDbPass(e.target.value)} />
                </div>
              </div>
            </div>
          )}

          {dbStatus && (
            <div className={`p-3 rounded text-sm ${
              dbStatus.type === 'success' ? 'bg-green-900/30 border border-green-700 text-green-300' :
              dbStatus.type === 'error' ? 'bg-red-900/30 border border-red-700 text-red-300' :
              'bg-teal-900/30 border border-teal-700 text-teal-300'
            }`}>
              {dbStatus.msg}
              {dbStatus.type === 'info' && (
                <p className="mt-1 text-xs opacity-75">Run <span className="font-mono">docker compose restart api</span> on your server to apply.</p>
              )}
            </div>
          )}

          <div className="flex gap-3">
            {dbType !== 'sqlite' && (
              <button onClick={handleTestDb} disabled={dbLoading} className="btn-secondary flex-1">
                {dbLoading ? 'Testing...' : 'Test Connection'}
              </button>
            )}
            <button onClick={handleSaveDb} disabled={dbLoading} className="btn-primary flex-1">
              {dbLoading ? 'Saving...' : 'Save & Apply on Restart'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
