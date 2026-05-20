import React from 'react';
import { useParams } from 'react-router-dom';

export default function VehicleDetailPage() {
  const { vehicleId } = useParams();

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">Vehicle #{vehicleId}</h1>
      <p className="text-slate-400">Vehicle detail page - Coming soon</p>
    </div>
  );
}
