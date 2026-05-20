import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export default function SettingsPage() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);
  const user = useAuthStore((state) => state.user);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Settings</h1>
      <div className="max-w-2xl bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-2">Account</h2>
          <p className="text-slate-400">{user?.email}</p>
        </div>
        <button
          onClick={handleLogout}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded"
        >
          Logout
        </button>
      </div>
    </div>
  );
}
