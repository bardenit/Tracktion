import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

export default function TopNav() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path: string) =>
    path === '/'
      ? location.pathname === '/'
      : location.pathname.startsWith(path);

  const navLink = (path: string, label: string) => (
    <Link
      to={path}
      className={`text-sm transition-colors ${
        isActive(path) ? 'text-teal-400' : 'text-slate-300 hover:text-white'
      }`}
    >
      {label}
    </Link>
  );

  return (
    <nav className="bg-slate-800 border-b border-slate-700 sticky top-0 z-40"
      style={{ paddingTop: 'env(safe-area-inset-top)' }}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-teal-400 font-bold text-lg tracking-tight">
            <img src="/tracktion-mark.png" alt="" className="h-7 w-7 object-contain" />
            Tracktion
          </Link>
          <div className="hidden sm:flex items-center gap-5">
            {navLink('/', 'Dashboard')}
            {navLink('/vehicles', 'Vehicles')}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-slate-400 text-sm hidden md:block">{user?.email}</span>
          {navLink('/settings', 'Settings')}
          <button
            onClick={handleLogout}
            className="text-sm text-slate-300 hover:text-white bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded transition-colors"
          >
            Logout
          </button>
        </div>
      </div>
    </nav>
  );
}
