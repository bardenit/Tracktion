import axios, { AxiosInstance } from 'axios';
import type {
  Vehicle, FuelEntry, MaintenanceEntry, TripEntry, Expense,
  VehiclePart, TireEvent, InspectionItem, VehicleDocument,
  RecallsResponse, VehicleCosts, SafetyRatings, ComplaintsSummary, EpaRating,
} from '../types';

const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || '/api';
const LEGACY_OFFLINE_FUEL_KEY = 'tracktion-offline-fuel';
const OFFLINE_FUEL_QUARANTINE_KEY = 'tracktion-offline-fuel:quarantine';
const OFFLINE_FUEL_VERSION = 2;

export interface OfflineFuelQueueItem {
  operationId: string;
  vehicleId: number;
  payload: Record<string, unknown>;
  queuedAt: string;
  status: 'pending' | 'conflict';
  conflictReason?: string;
}

export interface BulkImportResponse { operation_id: string; imported_count: number }
export interface FuelImportEntry { date: string; mileage: number; gallons: number; cost: number; location?: string; notes?: string; octane?: number; missed_fillup: boolean; partial_fillup: boolean }
export interface MaintenanceImportEntry { date: string; mileage: number; type: string; cost: number; service_provider?: string; notes?: string }
export interface ExpenseImportEntry { category: string; amount: number; date: string; description: string; expires_on?: string }

// ── OCR providers ────────────────────────────────────────────────────────────

export type OcrProviderType = 'ollama' | 'anthropic' | 'openai';

export interface OcrProvider {
  id: string;
  type: OcrProviderType;
  label: string;
  model: string;
  base_url?: string | null;
  /** Never populated by the API; only set when submitting a new or changed key. */
  api_key?: string;
  api_key_set?: boolean;
  api_key_preview?: string | null;
}

export interface OcrSettingsResponse { active: string; providers: OcrProvider[] }
export interface OcrSettingsPayload { active: string; providers: OcrProvider[] }

export interface OcrProviderRef { id: string; label: string }

/** Asked when the active provider is unreachable. Resolve with a provider id to
 *  retry, or null to give up. A photo is only sent elsewhere on an explicit yes. */
export type OcrFallbackPrompt = (message: string, alternatives: OcrProviderRef[]) => Promise<string | null>;

export interface OcrOptions {
  provider?: string;
  onProviderUnreachable?: OcrFallbackPrompt;
}

export interface OcrFuelResult {
  cost?: number; gallons?: number; price_per_gallon?: number;
  date?: string; location?: string; mileage?: number;
  warnings: string[];
}

export interface OcrExpenseResult {
  amount?: number; date?: string; description?: string; category?: string;
  warnings: string[];
}

export interface OcrDocumentResult {
  expires_on?: string; description?: string; category?: string; amount?: number;
  warnings: string[];
}

/** The 503 fallback response carries an object detail, so rendering
 *  `err.response.data.detail` straight into JSX would throw. */
export function ocrErrorMessage(err: any, fallback = 'Scan failed'): string {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail.detail === 'string') return detail.detail;
  return fallback;
}

/** Default confirmation for an unreachable provider. */
export function confirmOcrFallback(message: string, alternatives: OcrProviderRef[]): Promise<string | null> {
  const first = alternatives[0];
  if (!first) return Promise.resolve(null);
  const ok = confirm(`${message}\n\nRetry this scan with ${first.label}?`);
  return Promise.resolve(ok ? first.id : null);
}

function resizeImageForUpload(
  file: File,
  maxDim: number,
  quality: number,
  filename: string,
  preserveAlpha = false,
): Promise<File> {
  if (!file.type.startsWith('image/')) return Promise.resolve(file);

  // Keep PNG transparency intact (JPEG has no alpha channel and would
  // flatten transparent areas onto black).
  const asPng = preserveAlpha && file.type === 'image/png';

  const resize = new Promise<File>((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      try {
        const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
        const w = Math.round(img.width * scale);
        const h = Math.round(img.height * scale);
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext('2d');
        if (!ctx) { reject(new Error('No 2d context')); return; }
        ctx.drawImage(img, 0, 0, w, h);
        const outType = asPng ? 'image/png' : 'image/jpeg';
        const outName = asPng ? filename.replace(/\.jpe?g$/i, '.png') : filename;
        canvas.toBlob(
          (blob) => blob
            ? resolve(new File([blob], outName, { type: outType }))
            : reject(new Error('toBlob returned null')),
          outType,
          asPng ? undefined : quality,
        );
      } catch (err) {
        reject(err);
      }
    };
    img.onerror = () => { URL.revokeObjectURL(objectUrl); reject(new Error('Image load failed')); };
    img.src = objectUrl;
  });

  // Fall back to the original file if resize hangs or fails
  return resize.catch(() => file);
}

class ApiClient {
  private client: AxiosInstance;
  private refreshClient: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private refreshPromise: Promise<string> | null = null;
  private offlineSync: { userId: number; promise: Promise<{ synced: number; conflicts: number; remaining: number }> } | null = null;
  private authGeneration = 0;
  private onLogoutCallback: (() => void) | null = null;
  private authenticatedUserId: number | null = null;
  private pendingDeletes = new Map<string, Promise<unknown>>();

  deleteOnce<T>(key: string, request: () => Promise<T>): Promise<T> {
    const pending = this.pendingDeletes.get(key) as Promise<T> | undefined;
    if (pending) return pending;
    const next = request().finally(() => this.pendingDeletes.delete(key));
    this.pendingDeletes.set(key, next);
    return next;
  }

  setOnLogout(cb: () => void) {
    this.onLogoutCallback = cb;
  }

  setAuthenticatedUser(userId: number | null) {
    if (this.authenticatedUserId !== userId) this.authGeneration++;
    this.authenticatedUserId = userId;
    const legacy = localStorage.getItem(LEGACY_OFFLINE_FUEL_KEY);
    if (legacy !== null) {
      localStorage.setItem(OFFLINE_FUEL_QUARANTINE_KEY, legacy);
      localStorage.removeItem(LEGACY_OFFLINE_FUEL_KEY);
    }
  }

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });
    this.refreshClient = axios.create({
      baseURL: API_BASE_URL,
      headers: { 'Content-Type': 'application/json' },
    });

    // Load tokens from localStorage
    this.loadTokens();

    // Add request interceptor to attach token
    this.client.interceptors.request.use((config) => {
      if (this.accessToken) {
        config.headers.Authorization = `Bearer ${this.accessToken}`;
      }
      return config;
    });

    // Add response interceptor to handle 401
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401 && this.refreshToken && !error.config?._retry) {
          const originalConfig = error.config;
          originalConfig._retry = true;
          const generation = this.authGeneration;
          try {
            const token = await this.getSharedRefresh();
            if (generation !== this.authGeneration) throw new Error('Authentication changed during refresh');
            originalConfig.headers.Authorization = `Bearer ${token}`;
            return this.client(originalConfig);
          } catch (refreshError) {
            if (generation === this.authGeneration) this.logout();
            return Promise.reject(refreshError);
          }
        }
        return Promise.reject(error);
      }
    );
  }

  private loadTokens() {
    this.accessToken = localStorage.getItem('accessToken');
    this.refreshToken = localStorage.getItem('refreshToken');
  }

  private saveTokens() {
    if (this.accessToken) localStorage.setItem('accessToken', this.accessToken);
    if (this.refreshToken) localStorage.setItem('refreshToken', this.refreshToken);
  }

  // Auth endpoints
  async register(email: string, password: string) {
    const response = await this.client.post('/auth/register', { email, password });
    return response.data;
  }

  async login(email: string, password: string) {
    const generation = ++this.authGeneration;
    const response = await this.client.post('/auth/login', { email, password });
    if (generation !== this.authGeneration) throw new Error('Authentication changed during login');
    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token;
    this.saveTokens();
    return response.data;
  }

  async refreshAccessToken() {
    if (!this.refreshToken) throw new Error('No refresh token');
    const response = await this.refreshClient.post('/auth/refresh', { refresh_token: this.refreshToken });
    return response.data;
  }

  private getSharedRefresh(): Promise<string> {
    if (!this.refreshPromise) {
      const generation = this.authGeneration;
      this.refreshPromise = this.refreshAccessToken()
        .then((response) => {
          if (generation !== this.authGeneration) throw new Error('Authentication changed during refresh');
          this.accessToken = response.access_token;
          this.refreshToken = response.refresh_token;
          this.saveTokens();
          return response.access_token;
        })
        .finally(() => { this.refreshPromise = null; });
    }
    return this.refreshPromise;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  logout() {
    this.authGeneration++;
    const refreshToken = this.refreshToken;
    if (refreshToken) {
      void this.refreshClient.post('/auth/logout', { refresh_token: refreshToken }).catch(() => undefined);
    }
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    this.onLogoutCallback?.();
  }

  // Vehicle endpoints
  async createVehicle(vehicleData: any): Promise<Vehicle> {
    const response = await this.client.post('/vehicles/', vehicleData);
    return response.data;
  }

  async listVehicles(): Promise<Vehicle[]> {
    const response = await this.client.get('/vehicles/');
    return response.data;
  }

  async getVehicle(vehicleId: number): Promise<Vehicle> {
    const response = await this.client.get(`/vehicles/${vehicleId}`);
    return response.data;
  }

  async updateVehicle(vehicleId: number, vehicleData: any): Promise<Vehicle> {
    const response = await this.client.put(`/vehicles/${vehicleId}`, vehicleData);
    return response.data;
  }

  async deleteVehicle(vehicleId: number) {
    const response = await this.client.delete(`/vehicles/${vehicleId}`);
    return response.data;
  }

  async decodeVin(vehicleId: number, vin: string) {
    const response = await this.client.post(`/vehicles/${vehicleId}/decode-vin`, { vin });
    return response.data;
  }

  async lookupVin(vin: string) {
    const response = await this.client.get(`/vehicles/vin-lookup`, { params: { vin } });
    return response.data;
  }

  async getVehicleCosts(vehicleId: number): Promise<VehicleCosts> {
    const response = await this.client.get(`/vehicles/${vehicleId}/costs`);
    return response.data;
  }

  async getVehicleRecalls(vehicleId: number): Promise<RecallsResponse> {
    const response = await this.client.get(`/vehicles/${vehicleId}/recalls`);
    return response.data;
  }

  async getSafetyRatings(vehicleId: number): Promise<SafetyRatings> {
    const response = await this.client.get(`/vehicles/${vehicleId}/safety-ratings`);
    return response.data;
  }

  async getComplaints(vehicleId: number): Promise<ComplaintsSummary> {
    const response = await this.client.get(`/vehicles/${vehicleId}/complaints`);
    return response.data;
  }

  async getEpaRating(vehicleId: number): Promise<EpaRating> {
    const response = await this.client.get(`/vehicles/${vehicleId}/epa`);
    return response.data;
  }

  async getRecallStatus(vehicleId: number): Promise<{ available: boolean; new_count: number; new_recalls: { campaign_number?: string; component?: string }[] }> {
    const response = await this.client.get(`/vehicles/${vehicleId}/recall-status`);
    return response.data;
  }

  async getVehicleReport(vehicleId: number): Promise<Blob> {
    const response = await this.client.get(`/vehicles/${vehicleId}/report`, { responseType: 'blob' });
    return response.data as Blob;
  }

  async updateSpecsOverrides(vehicleId: number, overrides: Record<string, string>): Promise<Vehicle> {
    const response = await this.client.put(`/vehicles/${vehicleId}`, { specs_overrides: overrides });
    return response.data;
  }

  // Parts endpoints
  async listParts(vehicleId: number): Promise<VehiclePart[]> {
    const response = await this.client.get(`/parts/${vehicleId}/parts`);
    return response.data;
  }

  async createPart(vehicleId: number, partData: any) {
    const response = await this.client.post(`/parts/${vehicleId}/parts`, partData);
    return response.data;
  }

  async updatePart(vehicleId: number, partId: number, partData: any) {
    const response = await this.client.put(`/parts/${vehicleId}/parts/${partId}`, partData);
    return response.data;
  }

  async deletePart(vehicleId: number, partId: number) {
    const response = await this.client.delete(`/parts/${vehicleId}/parts/${partId}`);
    return response.data;
  }

  // Trip endpoints
  async listTrips(vehicleId: number): Promise<TripEntry[]> {
    const response = await this.client.get(`/trips/${vehicleId}/entries`);
    return response.data;
  }

  async createTrip(vehicleId: number, tripData: any) {
    const response = await this.client.post(`/trips/${vehicleId}/entries`, tripData);
    return response.data;
  }

  async updateTrip(vehicleId: number, tripId: number, tripData: any) {
    const response = await this.client.put(`/trips/${vehicleId}/entries/${tripId}`, tripData);
    return response.data;
  }

  async deleteTrip(vehicleId: number, tripId: number) {
    const response = await this.client.delete(`/trips/${vehicleId}/entries/${tripId}`);
    return response.data;
  }

  async getTripStats(vehicleId: number) {
    const response = await this.client.get(`/trips/${vehicleId}/stats`);
    return response.data;
  }

  // Setup / Settings
  async changePassword(currentPassword: string, newPassword: string) {
    const response = await this.client.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  }

  async updateVehicleMileage(vehicleId: number, mileage: number): Promise<Vehicle> {
    const response = await this.client.put(`/vehicles/${vehicleId}`, { current_mileage: mileage });
    return response.data;
  }

  async needsSetup() {
    const response = await this.client.get('/auth/needs-setup');
    return response.data;
  }

  async getDbStatus() {
    const response = await this.client.get('/settings/db/status');
    return response.data;
  }

  async getDbSettings() {
    const response = await this.client.get('/settings/db');
    return response.data;
  }

  async testDbConnection(settings: any) {
    const response = await this.client.post('/settings/db/test', settings);
    return response.data;
  }

  async saveDbSettings(settings: any) {
    const response = await this.client.post('/settings/db', settings);
    return response.data;
  }

  async getStorageSettings() {
    const response = await this.client.get('/settings/storage');
    return response.data;
  }

  async testStorageConnection(settings: any) {
    const response = await this.client.post('/settings/storage/test', settings);
    return response.data;
  }

  async saveStorageSettings(settings: any) {
    const response = await this.client.post('/settings/storage/migrations', settings);
    return response.data;
  }

  async startStorageMigration(id: number) {
    const response = await this.client.post(`/settings/storage/migrations/${id}/start`);
    return response.data;
  }

  async getStorageMigration(id: number) {
    const response = await this.client.get(`/settings/storage/migrations/${id}`);
    return response.data;
  }

  async resumeStorageMigration(id: number) {
    const response = await this.client.post(`/settings/storage/migrations/${id}/resume`);
    return response.data;
  }

  async cancelStorageMigration(id: number) {
    const response = await this.client.post(`/settings/storage/migrations/${id}/cancel`);
    return response.data;
  }

  async listStorageBuckets(settings: any) {
    const response = await this.client.post('/settings/storage/buckets', settings);
    return response.data;
  }

  async getIntegrationsSettings(): Promise<OcrSettingsResponse> {
    const response = await this.client.get('/settings/integrations');
    return response.data;
  }

  async testIntegrationsSettings(id?: string) {
    const response = await this.client.post('/settings/integrations/test', id ? { id } : {});
    return response.data;
  }

  async saveIntegrationsSettings(settings: OcrSettingsPayload) {
    const response = await this.client.post('/settings/integrations', settings);
    return response.data;
  }

  async setActiveOcrProvider(id: string) {
    const response = await this.client.post('/settings/integrations/active', { id });
    return response.data;
  }

  /** Warm the model so the next scan does not pay the cold load.
   *  Fire-and-forget: a failure here only means the next scan is cold. */
  async preloadOcr(provider?: string) {
    const formData = new FormData();
    formData.append('provider', provider || '');
    await this.client.post('/ocr/preload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  /** Posts an image to an OCR route, offering a configured alternative if the
   *  active provider is unreachable. The retry sends a provider *id*, never a
   *  URL — the backend resolves it against stored config. */
  private async ocrPost(path: string, file: File, maxDim: number, quality: number, name: string, opts?: OcrOptions) {
    const resized = await resizeImageForUpload(file, maxDim, quality, name);
    const send = async (provider?: string) => {
      const formData = new FormData();
      formData.append('file', resized);
      if (provider) formData.append('provider', provider);
      const response = await this.client.post(path, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    };
    try {
      return await send(opts?.provider);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const alternatives: OcrProviderRef[] = detail?.alternatives || [];
      if (err?.response?.status !== 503 || !detail?.provider_unreachable) throw err;
      if (!opts?.onProviderUnreachable || alternatives.length === 0) throw err;
      const chosen = await opts.onProviderUnreachable(detail.detail || 'The OCR provider is unreachable.', alternatives);
      if (!chosen) throw err;
      return await send(chosen);
    }
  }

  async ocrFuel(file: File, opts?: OcrOptions): Promise<OcrFuelResult> {
    // 640/0.65 measured against 1024, 1600 and 2048 from 12MP and 24MP
    // originals: accuracy was indistinguishable, while the payload is ~7x
    // smaller and inference ~2x faster. That matters on a phone over cellular.
    // Only the OCR request is shrunk — uploadDocument keeps its own resize, so
    // anything stored against the vehicle is unaffected.
    return this.ocrPost('/ocr/fuel', file, 640, 0.65, 'receipt.jpg', opts);
  }

  async ocrExpense(file: File, opts?: OcrOptions): Promise<OcrExpenseResult> {
    return this.ocrPost('/ocr/expense', file, 1024, 0.70, 'receipt.jpg', opts);
  }

  async ocrVin(file: File, opts?: OcrOptions): Promise<{ vin: string; check_digit_ok: boolean }> {
    return this.ocrPost('/ocr/vin', file, 1600, 0.85, 'vin.jpg', opts);
  }

  async ocrDocumentExpiry(file: File, opts?: OcrOptions): Promise<OcrDocumentResult> {
    return this.ocrPost('/ocr/document-expiry', file, 1500, 0.78, 'document.jpg', opts);
  }

  // Fuel endpoints
  async createFuelEntry(vehicleId: number, entryData: any) {
    const response = await this.client.post(`/fuel/${vehicleId}/entries`, entryData);
    return response.data;
  }

  async importFuelEntries(vehicleId: number, operationId: string, entries: FuelImportEntry[]): Promise<BulkImportResponse> {
    const response = await this.client.post(`/fuel/${vehicleId}/entries/bulk`, { operation_id: operationId, entries });
    return response.data;
  }

  // ── Offline fuel queue ──────────────────────────────────────────────────
  // Fill-ups logged with no signal are stored locally and synced when back online.

  private offlineFuelKey(): string | null {
    return this.authenticatedUserId === null
      ? null
      : `tracktion-offline-fuel:v${OFFLINE_FUEL_VERSION}:user:${this.authenticatedUserId}`;
  }

  getOfflineFuelQueue(): OfflineFuelQueueItem[] {
    const key = this.offlineFuelKey();
    if (!key) return [];
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  queueFuelEntry(vehicleId: number, payload: any, operationId = crypto.randomUUID()) {
    const key = this.offlineFuelKey();
    if (!key) throw new Error('Authentication must resolve before queueing offline fuel');
    const queue = this.getOfflineFuelQueue();
    queue.push({ operationId, vehicleId, payload: { ...payload }, queuedAt: new Date().toISOString(), status: 'pending' });
    localStorage.setItem(key, JSON.stringify(queue));
  }

  syncOfflineFuelEntries(): Promise<{ synced: number; conflicts: number; remaining: number }> {
    const userId = this.authenticatedUserId;
    if (userId === null) return Promise.resolve({ synced: 0, conflicts: 0, remaining: 0 });
    if (!this.offlineSync || this.offlineSync.userId !== userId) {
      const generation = this.authGeneration;
      const promise = this.performOfflineFuelSync(userId, generation)
        .finally(() => {
          if (this.offlineSync?.promise === promise) this.offlineSync = null;
        });
      this.offlineSync = { userId, promise };
    }
    return this.offlineSync.promise;
  }

  private async performOfflineFuelSync(userId: number, generation: number): Promise<{ synced: number; conflicts: number; remaining: number }> {
    const key = `tracktion-offline-fuel:v${OFFLINE_FUEL_VERSION}:user:${userId}`;
    const isCurrent = () => this.authenticatedUserId === userId && this.authGeneration === generation;
    let queue: OfflineFuelQueueItem[];
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || '[]');
      queue = Array.isArray(parsed) ? parsed : [];
    } catch {
      queue = [];
    }
    if (queue.length === 0) return { synced: 0, conflicts: 0, remaining: 0 };

    // Oldest fill-up first so server-side mileage validation sees them in order
    queue.sort((a, b) =>
      String(a.payload.date || '').localeCompare(String(b.payload.date || '')) || a.queuedAt.localeCompare(b.queuedAt));

    let synced = 0;
    let conflicts = 0;
    const remaining: typeof queue = [];
    for (const item of queue) {
      if (!isCurrent()) return { synced, conflicts, remaining: queue.length - synced };
      if (item.status === 'conflict') {
        conflicts++;
        remaining.push(item);
        continue;
      }
      try {
        await this.createFuelEntry(item.vehicleId, { ...item.payload, operation_id: item.operationId });
        synced++;
      } catch (err: any) {
        const status = err?.response?.status;
        if (status === 400 || status === 409 || status === 422) {
          const detail = err?.response?.data?.detail;
          item.status = 'conflict';
          item.conflictReason = typeof detail === 'string' ? detail : 'The server rejected this fill-up';
          conflicts++;
        }
        // Network, auth, timeout, rate limit, server, and validation failures all remain visible.
        remaining.push(item);
      }
    }
    if (isCurrent()) localStorage.setItem(key, JSON.stringify(remaining));
    return { synced, conflicts, remaining: remaining.length };
  }

  async listFuelEntries(vehicleId: number): Promise<FuelEntry[]> {
    const response = await this.client.get(`/fuel/${vehicleId}/entries`);
    return response.data;
  }

  async getFuelEntry(vehicleId: number, entryId: number) {
    const response = await this.client.get(`/fuel/${vehicleId}/entries/${entryId}`);
    return response.data;
  }

  async updateFuelEntry(vehicleId: number, entryId: number, entryData: any) {
    const response = await this.client.put(`/fuel/${vehicleId}/entries/${entryId}`, entryData);
    return response.data;
  }

  async deleteFuelEntry(vehicleId: number, entryId: number) {
    const response = await this.client.delete(`/fuel/${vehicleId}/entries/${entryId}`);
    return response.data;
  }

  async getFuelStats(vehicleId: number) {
    const response = await this.client.get(`/fuel/${vehicleId}/stats`);
    return response.data;
  }

  // Maintenance endpoints
  async createMaintenanceEntry(vehicleId: number, entryData: any) {
    const response = await this.client.post(`/maintenance/${vehicleId}/entries`, entryData);
    return response.data;
  }

  async importMaintenanceEntries(vehicleId: number, operationId: string, entries: MaintenanceImportEntry[]): Promise<BulkImportResponse> {
    const response = await this.client.post(`/maintenance/${vehicleId}/entries/bulk`, { operation_id: operationId, entries });
    return response.data;
  }

  async listMaintenanceEntries(vehicleId: number): Promise<MaintenanceEntry[]> {
    const response = await this.client.get(`/maintenance/${vehicleId}/entries`);
    return response.data;
  }

  async getMaintenanceEntry(vehicleId: number, entryId: number) {
    const response = await this.client.get(`/maintenance/${vehicleId}/entries/${entryId}`);
    return response.data;
  }

  async updateMaintenanceEntry(vehicleId: number, entryId: number, entryData: any) {
    const response = await this.client.put(`/maintenance/${vehicleId}/entries/${entryId}`, entryData);
    return response.data;
  }

  async deleteMaintenanceEntry(vehicleId: number, entryId: number) {
    const response = await this.client.delete(`/maintenance/${vehicleId}/entries/${entryId}`);
    return response.data;
  }

  async createMaintenanceReminder(vehicleId: number, reminderData: any) {
    const response = await this.client.post(`/maintenance/${vehicleId}/reminders`, reminderData);
    return response.data;
  }

  async listMaintenanceReminders(vehicleId: number) {
    const response = await this.client.get(`/maintenance/${vehicleId}/reminders`);
    return response.data;
  }

  async updateMaintenanceReminder(vehicleId: number, reminderId: number, reminderData: any) {
    const response = await this.client.put(`/maintenance/${vehicleId}/reminders/${reminderId}`, reminderData);
    return response.data;
  }

  async completeMaintenanceReminder(vehicleId: number, reminderId: number, completionData: any) {
    const response = await this.client.post(`/maintenance/${vehicleId}/reminders/${reminderId}/complete`, completionData);
    return response.data;
  }

  async deleteMaintenanceReminder(vehicleId: number, reminderId: number) {
    const response = await this.client.delete(`/maintenance/${vehicleId}/reminders/${reminderId}`);
    return response.data;
  }

  async getMaintenanceStats(vehicleId: number) {
    const response = await this.client.get(`/maintenance/${vehicleId}/stats`);
    return response.data;
  }

  // Expense endpoints
  async createExpense(vehicleId: number, expenseData: any) {
    const response = await this.client.post(`/expenses/${vehicleId}/entries`, expenseData);
    return response.data;
  }

  async importExpenses(vehicleId: number, operationId: string, entries: ExpenseImportEntry[]): Promise<BulkImportResponse> {
    const response = await this.client.post(`/expenses/${vehicleId}/entries/bulk`, { operation_id: operationId, entries });
    return response.data;
  }

  async listExpenses(vehicleId: number): Promise<Expense[]> {
    const response = await this.client.get(`/expenses/${vehicleId}/entries`);
    return response.data;
  }

  async updateExpense(vehicleId: number, expenseId: number, expenseData: any) {
    const response = await this.client.put(`/expenses/${vehicleId}/entries/${expenseId}`, expenseData);
    return response.data;
  }

  async deleteExpense(vehicleId: number, expenseId: number) {
    const response = await this.client.delete(`/expenses/${vehicleId}/entries/${expenseId}`);
    return response.data;
  }

  async getExpenseStats(vehicleId: number) {
    const response = await this.client.get(`/expenses/${vehicleId}/stats`);
    return response.data;
  }

  // Document endpoints
  async uploadDocument(vehicleId: number, file: File, documentType: string, maintenanceEntryId?: number) {
    const resized = await resizeImageForUpload(file, 1500, 0.78, 'document.jpg');
    const formData = new FormData();
    formData.append('file', resized);
    formData.append('document_type', documentType);
    if (maintenanceEntryId != null) formData.append('maintenance_entry_id', String(maintenanceEntryId));

    const response = await this.client.post(`/documents/${vehicleId}/documents`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async listDocuments(vehicleId: number): Promise<VehicleDocument[]> {
    const response = await this.client.get(`/documents/${vehicleId}/documents`);
    return response.data;
  }

  async deleteDocument(vehicleId: number, documentId: number) {
    const response = await this.client.delete(`/documents/${vehicleId}/documents/${documentId}`);
    return response.data;
  }

  async downloadDocument(vehicleId: number, documentId: number): Promise<Blob> {
    const response = await this.client.get(`/documents/${vehicleId}/documents/${documentId}/download`, { responseType: 'blob' });
    return response.data as Blob;
  }

  async listVehiclePhotos(vehicleId: number) {
    const response = await this.client.get(`/documents/${vehicleId}/photos`);
    return response.data;
  }

  async deleteVehiclePhotoById(vehicleId: number, photoId: number) {
    const response = await this.client.delete(`/documents/${vehicleId}/photos/${photoId}`);
    return response.data;
  }

  async getVehiclePhotoById(vehicleId: number, photoId: number): Promise<Blob> {
    const response = await this.client.get(`/documents/${vehicleId}/documents/${photoId}/download`, { responseType: 'blob' });
    return response.data as Blob;
  }

  async listInspectionItems(vehicleId: number): Promise<InspectionItem[]> {
    const response = await this.client.get(`/inspection/${vehicleId}/items`);
    return response.data;
  }

  async checkInspectionItem(vehicleId: number, itemId: number) {
    const response = await this.client.post(`/inspection/${vehicleId}/items/${itemId}/check`);
    return response.data;
  }

  async resetInspection(vehicleId: number) {
    const response = await this.client.post(`/inspection/${vehicleId}/reset`);
    return response.data;
  }

  async createInspectionItem(vehicleId: number, data: { name: string; category: string }) {
    const response = await this.client.post(`/inspection/${vehicleId}/items`, data);
    return response.data;
  }

  async deleteInspectionItem(vehicleId: number, itemId: number) {
    const response = await this.client.delete(`/inspection/${vehicleId}/items/${itemId}`);
    return response.data;
  }

  async listTireEvents(vehicleId: number): Promise<TireEvent[]> {
    const response = await this.client.get(`/tires/${vehicleId}/events`);
    return response.data;
  }

  async createTireEvent(vehicleId: number, data: any) {
    const response = await this.client.post(`/tires/${vehicleId}/events`, data);
    return response.data;
  }

  async updateTireEvent(vehicleId: number, eventId: number, data: any) {
    const response = await this.client.put(`/tires/${vehicleId}/events/${eventId}`, data);
    return response.data;
  }

  async deleteTireEvent(vehicleId: number, eventId: number) {
    const response = await this.client.delete(`/tires/${vehicleId}/events/${eventId}`);
    return response.data;
  }

  async getVehiclePhoto(vehicleId: number): Promise<Blob | null> {
    try {
      const response = await this.client.get(`/documents/${vehicleId}/photo`, { responseType: 'blob' });
      return response.data as Blob;
    } catch {
      return null;
    }
  }

  async uploadVehiclePhoto(vehicleId: number, file: File): Promise<void> {
    const resized = await resizeImageForUpload(file, 1200, 0.80, 'photo.jpg', true);
    const form = new FormData();
    form.append('file', resized);
    await this.client.post(`/documents/${vehicleId}/photo`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  async deleteVehiclePhoto(vehicleId: number): Promise<void> {
    await this.client.delete(`/documents/${vehicleId}/photo`);
  }
}

export const apiClient = new ApiClient();
