import { useEffect, useRef, useState } from 'react';
import { apiClient } from '../services/api';

interface Props {
  vehicleId: number;
  alt?: string;
  className?: string;
}

export default function VehiclePhoto({ vehicleId, alt = 'Vehicle photo', className = '' }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const blobRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiClient.getVehiclePhoto(vehicleId).then((blob) => {
      if (cancelled) return;
      if (blob) {
        const u = URL.createObjectURL(blob);
        blobRef.current = u;
        setUrl(u);
      }
      setReady(true);
    });
    return () => {
      cancelled = true;
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current);
        blobRef.current = null;
      }
    };
  }, [vehicleId]);

  if (!ready) return <div className={`bg-slate-800 animate-pulse rounded-lg ${className}`} />;
  if (!url) return null;
  return <img src={url} alt={alt} className={`rounded-lg ${className}`} />;
}
