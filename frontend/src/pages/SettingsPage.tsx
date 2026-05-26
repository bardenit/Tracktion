import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useToastStore } from '../stores/toastStore';
import { apiClient } from '../services/api';

type Tab = 'account' | 'database' | 'storage' | 'integrations';
type DbType = 'sqlite' | 'postgresql' | 'mysql';
type StorageType = 'local' | 's3' | 'webdav';

const DEFAULT_PORTS: Record<string, number> = { postgresql: 5432, mysql: 3306 };

export default function SettingsPage() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);
  const addToast = useToastStore((state) => state.addToast);

  const [activeTab, setActiveTab] = useState<Tab>('account');

  // ── Password ──────────────────────────────────────────────────────────────
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwLoading, setPwLoading] = useState(false);
  const [pwStatus, setPwStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  // ── Database ──────────────────────────────────────────────────────────────
  const [dbStatus2, setDbStatus2] = useState<{ type: string; display: string } | null>(null);
  const [dbType, setDbType] = useState<DbType>('sqlite');
  const [dbHost, setDbHost] = useState('');
  const [dbPort, setDbPort] = useState('');
  const [dbName, setDbName] = useState('');
  const [dbUser, setDbUser] = useState('');
  const [dbPass, setDbPass] = useState('');
  const [dbLoading, setDbLoading] = useState(false);
  const [dbStatus, setDbStatus] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);

  // ── Storage ───────────────────────────────────────────────────────────────
  const [storageType, setStorageType] = useState<StorageType>('local');
  const [s3Endpoint, setS3Endpoint] = useState('');
  const [s3Bucket, setS3Bucket] = useState('');
  const [s3Region, setS3Region] = useState('');
  const [s3AccessKey, setS3AccessKey] = useState('');
  const [s3SecretKey, setS3SecretKey] = useState('');
  const [wdUrl, setWdUrl] = useState('');
  const [wdUsername, setWdUsername] = useState('');
  const [wdPassword, setWdPassword] = useState('');
  const [wdPath, setWdPath] = useState('/tracktion');
  const [storageHasSecret, setStorageHasSecret] = useState(false);
  const [storageLoading, setStorageLoading] = useState(false);
  const [storageStatus, setStorageStatus] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);

  // ── Integrations ──────────────────────────────────────────────────────────
  const [anthropicKey, setAnthropicKey] = useState('');
  const [anthropicKeySet, setAnthropicKeySet] = useState(false);
  const [anthropicKeyPreview, setAnthropicKeyPreview] = useState<string | null>(null);
  const [intLoading, setIntLoading] = useState(false);
  const [intStatus, setIntStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

  useEffect(() => {
    if (activeTab === 'database') {
      apiClient.getDbStatus().then(setDbStatus2).catch(() => {});
      apiClient.getDbSettings().then((s) => {
        setDbType((s.type as DbType) || 'sqlite');
        setDbHost(s.host || '');
        setDbPort(s.port ? String(s.port) : '');
        setDbName(s.database || '');
        setDbUser(s.username || '');
      }).catch(() => {});
    }
    if (activeTab === 'storage') {
      apiClient.getStorageSettings().then((s) => {
        setStorageType((s.type as StorageType) || 'local');
        setS3Endpoint(s.endpoint || '');
        setS3Bucket(s.bucket || '');
        setS3Region(s.region || '');
        setS3AccessKey(s.access_key || '');
        setWdUrl(s.url || '');
        setWdUsername(s.username || '');
        setWdPath(s.path || '/tracktion');
        setStorageHasSecret(s.has_secret || false);
      }).catch(() => {});
    }
    if (activeTab === 'integrations') {
      apiClient.getIntegrationsSettings().then((s) => {
        setAnthropicKeySet(s.anthropic_api_key_set || false);
        setAnthropicKeyPreview(s.anthropic_api_key_preview || null);
      }).catch(() => {});
    }
  }, [activeTab]);

  const handleLogout = () => { logout(); navigate('/login'); };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPw !== confirmPw) { setPwStatus({ type: 'error', msg: 'New passwords do not match' }); return; }
    setPwLoading(true);
    setPwStatus(null);
    try {
      await apiClient.changePassword(currentPw, newPw);
      setPwStatus({ type: 'success', msg: 'Password updated successfully' });
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
    } catch (err: any) {
      setPwStatus({ type: 'error', msg: err.response?.data?.detail || 'Failed to update password' });
    } finally { setPwLoading(false); }
  };

  const buildDbPayload = () => ({
    type: dbType,
    host: dbHost || undefined,
    port: dbPort ? Number(dbPort) : (DEFAULT_PORTS[dbType] || undefined),
    database: dbName || undefined,
    username: dbUser || undefined,
    password: dbPass || undefined,
  });

  const handleTestDb = async () => {
    setDbLoading(true); setDbStatus(null);
    try {
      const r = await apiClient.testDbConnection(buildDbPayload());
      setDbStatus(r.success ? { type: 'success', msg: 'Connection successful!' } : { type: 'error', msg: r.error || 'Connection failed' });
    } catch { setDbStatus({ type: 'error', msg: 'Test request failed' }); }
    finally { setDbLoading(false); }
  };

  const handleSaveDb = async () => {
    setDbLoading(true); setDbStatus(null);
    try {
      const r = await apiClient.saveDbSettings(buildDbPayload());
      setDbStatus({ type: 'info', msg: r.message });
      setDbPass('');
    } catch (err: any) { setDbStatus({ type: 'error', msg: err.response?.data?.detail || 'Save failed' }); }
    finally { setDbLoading(false); }
  };

  const buildStoragePayload = () => ({
    type: storageType,
    ...(storageType === 's3' ? {
      endpoint: s3Endpoint || undefined,
      bucket: s3Bucket || undefined,
      region: s3Region || undefined,
      access_key: s3AccessKey || undefined,
      secret_key: s3SecretKey || undefined,
    } : {}),
    ...(storageType === 'webdav' ? {
      url: wdUrl || undefined,
      username: wdUsername || undefined,
      password: wdPassword || undefined,
      path: wdPath || '/tracktion',
    } : {}),
  });

  const handleTestStorage = async () => {
    setStorageLoading(true); setStorageStatus(null);
    try {
      const r = await apiClient.testStorageConnection(buildStoragePayload());
      setStorageStatus(r.success ? { type: 'success', msg: 'Connection successful!' } : { type: 'error', msg: r.error || 'Connection failed' });
    } catch { setStorageStatus({ type: 'error', msg: 'Test request failed' }); }
    finally { setStorageLoading(false); }
  };

  const handleSaveStorage = async () => {
    setStorageLoading(true); setStorageStatus(null);
    try {
      const r = await apiClient.saveStorageSettings(buildStoragePayload());
      setStorageStatus({ type: 'info', msg: r.message });
      setS3SecretKey(''); setWdPassword('');
      addToast('success', 'Storage settings saved');
    } catch (err: any) { setStorageStatus({ type: 'error', msg: err.response?.data?.detail || 'Save failed' }); }
    finally { setStorageLoading(false); }
  };

  const handleTestIntegrations = async () => {
    setIntLoading(true); setIntStatus(null);
    try {
      const r = await apiClient.testIntegrationsSettings();
      setIntStatus(r.success ? { type: 'success', msg: 'API key is valid!' } : { type: 'error', msg: r.error || 'Invalid API key' });
    } catch { setIntStatus({ type: 'error', msg: 'Test request failed' }); }
    finally { setIntLoading(false); }
  };

  const handleSaveIntegrations = async () => {
    setIntLoading(true); setIntStatus(null);
    try {
      await apiClient.saveIntegrationsSettings({ anthropic_api_key: anthropicKey || undefined });
      setAnthropicKeySet(!!anthropicKey || anthropicKeySet);
      setAnthropicKey('');
      addToast('success', 'Integration settings saved');
      const s = await apiClient.getIntegrationsSettings();
      setAnthropicKeySet(s.anthropic_api_key_set);
      setAnthropicKeyPreview(s.anthropic_api_key_preview);
    } catch (err: any) { setIntStatus({ type: 'error', msg: err.response?.data?.detail || 'Save failed' }); }
    finally { setIntLoading(false); }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'account', label: 'Account' },
    { id: 'database', label: 'Database' },
    { id: 'storage', label: 'Storage' },
    { id: 'integrations', label: 'Integrations' },
  ];

  const statusCls = (type: string) =>
    type === 'success' ? 'bg-green-900/30 border border-green-700 text-green-300' :
    type === 'error' ? 'bg-red-900/30 border border-red-700 text-red-300' :
    'bg-teal-900/30 border border-teal-700 text-teal-300';

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      <div className="border-b border-slate-700">
        <nav className="flex overflow-x-auto">
          {tabs.map((t) => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`px-4 py-3 text-sm font-medium whitespace-nowrap border-b-2 transition-colors ${
                activeTab === t.id ? 'border-teal-500 text-teal-400' : 'border-transparent text-slate-400 hover:text-white'
              }`}>
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ── ACCOUNT ── */}
      {activeTab === 'account' && (
        <div className="space-y-4 max-w-md">
          <div className="card space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Account</h2>
            <p className="text-white">{user?.email}</p>
            <button onClick={handleLogout} className="bg-red-900 hover:bg-red-800 text-red-200 px-4 py-2 rounded transition-colors text-sm">
              Sign Out
            </button>
          </div>
          <div className="card space-y-4">
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Change Password</h2>
            {pwStatus && <div className={`p-3 rounded text-sm ${statusCls(pwStatus.type)}`}>{pwStatus.msg}</div>}
            <form onSubmit={handleChangePassword} className="space-y-3">
              {[
                { label: 'Current Password', value: currentPw, set: setCurrentPw },
                { label: 'New Password', value: newPw, set: setNewPw, placeholder: 'At least 8 characters' },
                { label: 'Confirm New Password', value: confirmPw, set: setConfirmPw },
              ].map(({ label, value, set, placeholder }: any) => (
                <div key={label}>
                  <label className="block text-sm text-slate-300 mb-1">{label}</label>
                  <input type="password" className="input-field" value={value} placeholder={placeholder}
                    onChange={(e) => set(e.target.value)} required />
                </div>
              ))}
              <button type="submit" disabled={pwLoading} className="btn-primary w-full">
                {pwLoading ? 'Updating...' : 'Update Password'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* ── DATABASE ── */}
      {activeTab === 'database' && (
        <div className="card max-w-lg space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">Database</h2>
            {dbStatus2 && (
              <div className="flex items-center gap-2 bg-slate-700/50 rounded px-3 py-2 text-sm">
                <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                <span className="text-slate-300"><span className="text-slate-400">Active: </span>
                  <span className="text-white font-medium">{dbStatus2.display}</span></span>
              </div>
            )}
            <p className="text-slate-500 text-xs mt-2">Changes require a container restart to take effect.</p>
          </div>
          <div>
            <label className="block text-sm text-slate-300 mb-2">Database Type</label>
            <div className="grid grid-cols-3 gap-2">
              {(['sqlite', 'postgresql', 'mysql'] as DbType[]).map((t) => (
                <button key={t} onClick={() => { setDbType(t); setDbStatus(null); if (DEFAULT_PORTS[t]) setDbPort(String(DEFAULT_PORTS[t])); }}
                  className={`py-2 px-3 rounded border text-sm font-medium transition-colors ${
                    dbType === t ? 'border-teal-500 bg-teal-900/30 text-teal-300' : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }`}>
                  {t === 'sqlite' ? 'SQLite' : t === 'postgresql' ? 'PostgreSQL' : 'MySQL'}
                </button>
              ))}
            </div>
          </div>
          {dbType === 'sqlite' ? (
            <div className="bg-slate-700/50 rounded p-4 text-sm">
              <p className="text-slate-300 font-medium mb-1">SQLite — Zero configuration</p>
              <p className="text-slate-400">Data stored in <span className="font-mono text-teal-300">/app/data/tracktion.db</span> inside the container volume.</p>
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
                <input className="input-field" value={dbName} onChange={(e) => setDbName(e.target.value)} />
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
            <div className={`p-3 rounded text-sm ${statusCls(dbStatus.type)}`}>
              {dbStatus.msg}
              {dbStatus.type === 'info' && <p className="mt-1 text-xs opacity-75">Run <span className="font-mono">docker compose restart api</span> on your server to apply.</p>}
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

      {/* ── STORAGE ── */}
      {activeTab === 'storage' && (
        <div className="card max-w-lg space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">Document Storage</h2>
            <p className="text-slate-500 text-xs">Where uploaded documents are stored. New uploads use the active backend immediately — no restart needed.</p>
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Storage Backend</label>
            <div className="grid grid-cols-3 gap-2">
              {([
                { id: 'local', label: 'Local' },
                { id: 's3', label: 'S3-compatible' },
                { id: 'webdav', label: 'WebDAV' },
              ] as { id: StorageType; label: string }[]).map((t) => (
                <button key={t.id} onClick={() => { setStorageType(t.id); setStorageStatus(null); }}
                  className={`py-2 px-3 rounded border text-sm font-medium transition-colors ${
                    storageType === t.id ? 'border-teal-500 bg-teal-900/30 text-teal-300' : 'border-slate-600 text-slate-400 hover:border-slate-500'
                  }`}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {storageType === 'local' && (
            <div className="bg-slate-700/50 rounded p-4 text-sm space-y-1">
              <p className="text-slate-300 font-medium">Local — Zero configuration</p>
              <p className="text-slate-400">Files stored in <span className="font-mono text-teal-300">/app/data/documents</span> inside the container volume.</p>
              <p className="text-slate-500 text-xs mt-2">Tip: point your Docker volume at a TrueNAS NFS/SMB mount and files will live on your NAS automatically.</p>
            </div>
          )}

          {storageType === 's3' && (
            <div className="space-y-3">
              <p className="text-slate-500 text-xs">Works with AWS S3, Backblaze B2, Wasabi, Cloudflare R2, and any S3-compatible service.</p>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Endpoint URL <span className="text-slate-500">(leave blank for AWS)</span></label>
                <input className="input-field font-mono text-sm" placeholder="https://s3.us-west-002.backblazeb2.com" value={s3Endpoint} onChange={(e) => setS3Endpoint(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Bucket</label>
                  <input className="input-field" placeholder="my-tracktion-docs" value={s3Bucket} onChange={(e) => setS3Bucket(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Region</label>
                  <input className="input-field" placeholder="us-east-1" value={s3Region} onChange={(e) => setS3Region(e.target.value)} />
                </div>
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Access Key ID</label>
                <input className="input-field font-mono text-sm" value={s3AccessKey} onChange={(e) => setS3AccessKey(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">
                  Secret Access Key {storageHasSecret && <span className="text-slate-500">(stored — leave blank to keep)</span>}
                </label>
                <input className="input-field font-mono text-sm" type="password" placeholder={storageHasSecret ? '••••••••' : ''} value={s3SecretKey} onChange={(e) => setS3SecretKey(e.target.value)} />
              </div>
            </div>
          )}

          {storageType === 'webdav' && (
            <div className="space-y-3">
              <p className="text-slate-500 text-xs">Works with TrueNAS WebDAV (enable in Services → WebDAV), Nextcloud, ownCloud, and any WebDAV server.</p>
              <div>
                <label className="block text-sm text-slate-300 mb-1">WebDAV URL</label>
                <input className="input-field font-mono text-sm" placeholder="http://192.168.1.100:8080" value={wdUrl} onChange={(e) => setWdUrl(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm text-slate-300 mb-1">Base Path</label>
                <input className="input-field font-mono text-sm" placeholder="/tracktion" value={wdPath} onChange={(e) => setWdPath(e.target.value)} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-slate-300 mb-1">Username</label>
                  <input className="input-field" value={wdUsername} onChange={(e) => setWdUsername(e.target.value)} />
                </div>
                <div>
                  <label className="block text-sm text-slate-300 mb-1">
                    Password {storageHasSecret && <span className="text-slate-500">(stored)</span>}
                  </label>
                  <input className="input-field" type="password" placeholder={storageHasSecret ? '••••••••' : ''} value={wdPassword} onChange={(e) => setWdPassword(e.target.value)} />
                </div>
              </div>
            </div>
          )}

          {storageStatus && (
            <div className={`p-3 rounded text-sm ${statusCls(storageStatus.type)}`}>{storageStatus.msg}</div>
          )}

          <div className="flex gap-3">
            {storageType !== 'local' && (
              <button onClick={handleTestStorage} disabled={storageLoading} className="btn-secondary flex-1">
                {storageLoading ? 'Testing...' : 'Test Connection'}
              </button>
            )}
            <button onClick={handleSaveStorage} disabled={storageLoading} className="btn-primary flex-1">
              {storageLoading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      )}

      {/* ── INTEGRATIONS ── */}
      {activeTab === 'integrations' && (
        <div className="card max-w-lg space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-1">Anthropic API</h2>
            <p className="text-slate-500 text-xs">Required for OCR — scanning receipts and fuel pump screens to auto-fill forms.</p>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-sm text-slate-300 mb-1">
                API Key
                {anthropicKeySet && anthropicKeyPreview && (
                  <span className="ml-2 text-slate-500 text-xs">Current: <span className="font-mono text-teal-400">{anthropicKeyPreview}</span></span>
                )}
              </label>
              <input
                className="input-field font-mono text-sm"
                type="password"
                placeholder={anthropicKeySet ? 'Enter new key to replace' : 'sk-ant-...'}
                value={anthropicKey}
                onChange={(e) => setAnthropicKey(e.target.value)}
              />
            </div>

            {anthropicKeySet && (
              <div className="flex items-center gap-2 bg-slate-700/50 rounded px-3 py-2 text-sm">
                <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                <span className="text-slate-300">API key configured — OCR features are available</span>
              </div>
            )}

            {intStatus && (
              <div className={`p-3 rounded text-sm ${statusCls(intStatus.type)}`}>{intStatus.msg}</div>
            )}
          </div>

          <div className="flex gap-3">
            <button onClick={handleTestIntegrations} disabled={intLoading || !anthropicKeySet} className="btn-secondary flex-1">
              {intLoading ? 'Testing...' : 'Test Key'}
            </button>
            <button onClick={handleSaveIntegrations} disabled={intLoading || !anthropicKey} className="btn-primary flex-1">
              {intLoading ? 'Saving...' : 'Save Key'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
