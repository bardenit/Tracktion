import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './stores/authStore';
import TopNav from './components/TopNav';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import VehiclesPage from './pages/VehiclesPage';
import VehicleDetailPage from './pages/VehicleDetailPage';
import SettingsPage from './pages/SettingsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">{children}</main>
    </div>
  );
}

function App() {
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout><DashboardPage /></Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/vehicles"
          element={
            <ProtectedRoute>
              <Layout><VehiclesPage /></Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/vehicles/:vehicleId"
          element={
            <ProtectedRoute>
              <Layout><VehicleDetailPage /></Layout>
            </ProtectedRoute>
          }
        />
        <Route
          path="/settings"
          element={
            <ProtectedRoute>
              <Layout><SettingsPage /></Layout>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
