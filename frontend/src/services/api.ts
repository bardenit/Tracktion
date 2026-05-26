import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = (import.meta.env.VITE_API_URL as string) || '/api';

class ApiClient {
  private client: AxiosInstance;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private onLogoutCallback: (() => void) | null = null;

  setOnLogout(cb: () => void) {
    this.onLogoutCallback = cb;
  }

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
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
        if (error.response?.status === 401 && this.refreshToken && !this.isRefreshing) {
          this.isRefreshing = true;
          try {
            const response = await this.refreshAccessToken();
            this.accessToken = response.access_token;
            this.refreshToken = response.refresh_token;
            this.saveTokens();
            this.isRefreshing = false;

            // Retry original request
            const originalConfig = error.config;
            originalConfig.headers.Authorization = `Bearer ${this.accessToken}`;
            return this.client(originalConfig);
          } catch {
            this.isRefreshing = false;
            this.logout();
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
    const response = await this.client.post('/auth/login', { email, password });
    this.accessToken = response.data.access_token;
    this.refreshToken = response.data.refresh_token;
    this.saveTokens();
    return response.data;
  }

  async refreshAccessToken() {
    if (!this.refreshToken) throw new Error('No refresh token');
    const response = await this.client.post('/auth/refresh', { refresh_token: this.refreshToken });
    return response.data;
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  logout() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    this.onLogoutCallback?.();
  }

  // Vehicle endpoints
  async createVehicle(vehicleData: any) {
    const response = await this.client.post('/vehicles/', vehicleData);
    return response.data;
  }

  async listVehicles() {
    const response = await this.client.get('/vehicles/');
    return response.data;
  }

  async getVehicle(vehicleId: number) {
    const response = await this.client.get(`/vehicles/${vehicleId}`);
    return response.data;
  }

  async updateVehicle(vehicleId: number, vehicleData: any) {
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

  async updateSpecsOverrides(vehicleId: number, overrides: Record<string, string>) {
    const response = await this.client.put(`/vehicles/${vehicleId}`, { specs_overrides: overrides });
    return response.data;
  }

  // Parts endpoints
  async listParts(vehicleId: number) {
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
  async listTrips(vehicleId: number) {
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

  async updateVehicleMileage(vehicleId: number, mileage: number) {
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
    const response = await this.client.post('/settings/storage', settings);
    return response.data;
  }

  async listStorageBuckets(settings: any) {
    const response = await this.client.post('/settings/storage/buckets', settings);
    return response.data;
  }

  async getIntegrationsSettings() {
    const response = await this.client.get('/settings/integrations');
    return response.data;
  }

  async testIntegrationsSettings(key?: string) {
    const response = await this.client.post('/settings/integrations/test', key ? { anthropic_api_key: key } : {});
    return response.data;
  }

  async saveIntegrationsSettings(settings: any) {
    const response = await this.client.post('/settings/integrations', settings);
    return response.data;
  }

  async ocrFuel(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await this.client.post('/ocr/fuel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  async ocrExpense(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await this.client.post('/ocr/expense', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }

  // Fuel endpoints
  async createFuelEntry(vehicleId: number, entryData: any) {
    const response = await this.client.post(`/fuel/${vehicleId}/entries`, entryData);
    return response.data;
  }

  async listFuelEntries(vehicleId: number) {
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

  async listMaintenanceEntries(vehicleId: number) {
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

  async listExpenses(vehicleId: number) {
    const response = await this.client.get(`/expenses/${vehicleId}/entries`);
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
  async uploadDocument(vehicleId: number, file: File, documentType: string) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    const response = await this.client.post(`/documents/${vehicleId}/documents`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async listDocuments(vehicleId: number) {
    const response = await this.client.get(`/documents/${vehicleId}/documents`);
    return response.data;
  }

  async deleteDocument(vehicleId: number, documentId: number) {
    const response = await this.client.delete(`/documents/${vehicleId}/documents/${documentId}`);
    return response.data;
  }
}

export const apiClient = new ApiClient();
