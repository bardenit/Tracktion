import { create } from 'zustand';
import { apiClient } from '../services/api';
import type { User } from '../types';
import { purgeTracktionCaches } from '../services/serviceWorker';

interface AuthStore {
  user: User | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  isLoading: false,
  error: null,
  isAuthenticated: !!localStorage.getItem('accessToken'),

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await purgeTracktionCaches();
      await apiClient.login(email, password);
      const user = await apiClient.getCurrentUser();
      apiClient.setAuthenticatedUser(user.id);
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Login failed';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  register: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const user = await apiClient.register(email, password);
      set({ user, isLoading: false });
    } catch (error: any) {
      const message = error.response?.data?.detail || 'Registration failed';
      set({ error: message, isLoading: false });
      throw error;
    }
  },

  logout: () => {
    void purgeTracktionCaches();
    apiClient.setAuthenticatedUser(null);
    apiClient.logout();
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    set({ isLoading: true });
    if (!localStorage.getItem('accessToken')) {
      apiClient.setAuthenticatedUser(null);
      set({ user: null, isAuthenticated: false, isLoading: false });
      return;
    }
    // Optimistically trust stored tokens — the interceptor handles expiry/refresh
    // and calls logout() (which triggers onLogout → clears store) if unrecoverable
    set({ isAuthenticated: true });
    try {
      const user = await apiClient.getCurrentUser();
      apiClient.setAuthenticatedUser(user.id);
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      // Interceptor already handled it; don't touch auth state here
      set({ isLoading: false });
    }
  },
}));

// When the API client's refresh chain fails it calls logout(), which now
// notifies the store directly so the user is sent to the login page.
apiClient.setOnLogout(() => {
  apiClient.setAuthenticatedUser(null);
  void purgeTracktionCaches();
  useAuthStore.setState({ user: null, isAuthenticated: false });
});
