export interface Vehicle {
  id: number;
  nickname?: string;
  vehicle_type: string;
  make: string;
  model: string;
  year: number;
  vin?: string;
  license_plate?: string;
  current_mileage: number;
  fuel_type: string;
  axle_count?: number;
  tank_size_gallons?: number;
  created_at: string;
  nhtsa_data?: Record<string, unknown>;
  specs_overrides?: Record<string, unknown>;
}

export interface FuelEntry {
  id: number;
  date: string;
  mileage: number;
  gallons: number;
  cost: number;
  location?: string;
  notes?: string;
  octane?: number;
  mpg?: number;
  cost_per_mile?: number;
}

export interface MaintenanceEntry {
  id: number;
  date: string;
  mileage: number;
  type: string;
  cost: number;
  service_provider?: string;
  notes?: string;
}

export interface Reminder {
  id: number;
  service_type: string;
  interval_miles?: number;
  interval_days?: number;
  target_mileage?: number;
  reminder_miles?: number;
  last_performed_mileage?: number;
  next_due_mileage?: number;
  next_due_date?: string;
  is_overdue: boolean;
}

export interface TripEntry {
  id: number;
  date: string;
  miles: number;
  destination?: string;
  notes?: string;
}

export interface Expense {
  id: number;
  category: string;
  amount: number;
  date: string;
  description: string;
  expires_on?: string;
}

export interface VehicleDocument {
  id: number;
  document_type: string;
  filename: string;
  uploaded_at: string;
}

export interface VehiclePhoto {
  id: number;
  filename?: string;
  uploaded_at: string;
}

export interface VehiclePart {
  id: number;
  name: string;
  part_number?: string;
  brand?: string;
  category: string;
  notes?: string;
  needs_order: boolean;
}

export interface InspectionItem {
  id: number;
  name: string;
  category: string;
  last_checked_at: string | null;
  order_index: number;
}

export interface TireEvent {
  id: number;
  event_type: 'install' | 'rotation' | 'pressure' | 'tread';
  date: string;
  mileage: number;
  brand?: string;
  size?: string;
  pressure_fl?: number;
  pressure_fr?: number;
  pressure_rl?: number;
  pressure_rr?: number;
  tread_fl?: number;
  tread_fr?: number;
  tread_rl?: number;
  tread_rr?: number;
  notes?: string;
}
