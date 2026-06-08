import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { apiClient } from '../services/api';

type Mode = 'checking' | 'login' | 'setup';

export default function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const isLoading = useAuthStore((state) => state.isLoading);
  const error = useAuthStore((state) => state.error);

  const [mode, setMode] = useState<Mode>('checking');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupLoading, setSetupLoading] = useState(false);

  useEffect(() => {
    apiClient.needsSetup()
      .then(({ needs_setup }) => setMode(needs_setup ? 'setup' : 'login'))
      .catch(() => setMode('login'));
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      navigate('/');
    } catch {}
  };

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setSetupError('Passwords do not match');
      return;
    }
    if (password.length < 8) {
      setSetupError('Password must be at least 8 characters');
      return;
    }
    setSetupLoading(true);
    setSetupError('');
    try {
      await apiClient.register(email, password);
      await login(email, password);
      navigate('/');
    } catch (err: any) {
      setSetupError(err.response?.data?.detail || 'Setup failed');
    } finally {
      setSetupLoading(false);
    }
  };

  if (mode === 'checking') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center">
        <div className="text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-slate-800 rounded-lg shadow-xl p-8 border border-slate-700">
        <img src="/tracktion-mark.png" alt="Tracktion" className="h-20 w-20 object-contain mx-auto mb-5" />
        {mode === 'setup' ? (
          <>
            <h1 className="text-3xl font-bold text-white mb-1">Welcome to Tracktion</h1>
            <p className="text-slate-400 mb-8">Create your account to get started.</p>

            {setupError && (
              <div className="mb-4 p-3 bg-red-900 text-red-200 rounded text-sm">{setupError}</div>
            )}

            <form onSubmit={handleSetup} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  placeholder="At least 8 characters"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  placeholder="Repeat password"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={setupLoading}
                className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-900 text-white font-semibold py-2 rounded transition-colors"
              >
                {setupLoading ? 'Creating account...' : 'Create Account & Sign In'}
              </button>
            </form>
          </>
        ) : (
          <>
            <h1 className="text-3xl font-bold text-white mb-2">Tracktion</h1>
            <p className="text-slate-400 mb-8">Sign in to manage your vehicles</p>

            {error && <div className="mb-4 p-3 bg-red-900 text-red-200 rounded text-sm">{error}</div>}

            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  placeholder="you@example.com"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:border-teal-500"
                  placeholder="Enter your password"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-teal-900 text-white font-semibold py-2 rounded transition-colors"
              >
                {isLoading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
