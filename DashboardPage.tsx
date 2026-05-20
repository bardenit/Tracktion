import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../services/api';

export default function DashboardPage() {
  const navigate = useNavigate();
  const [vehicles, setVehicles] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadVehicles = async () => {
      try {
        const data = await apiClient.listVehicles();
        setVehicles(data);
      } catch (error) {
        console.error('Failed to load vehicles:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadVehicles();
  }, []);

  if (isLoading) {
    return <div className="p-8">Loading...</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>
      <p className="text-slate-400 mb-4">You have {vehicles.length} vehicle(s)</p>
      <button
        onClick={() => navigate('/vehicles')}
        className="bg-teal-600 hover:bg-teal-700 text-white px-4 py-2 rounded"
      >
        Manage Vehicles
      </button>
    </div>
  );
}
