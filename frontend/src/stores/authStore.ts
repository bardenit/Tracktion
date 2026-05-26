import { create } from 'zustand';
import { apiClient } from '../services/api';

interface User {
  id: number;
  email: string;
  created_at: string;
}

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
  isAuthenticated: false,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await apiClient.login(email, password);
      const user = await apiClient.getCurrentUser();
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
    apiClient.logout();
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    if (!localStorage.getItem('accessToken')) {
      set({ user: null, isAuthenticated: false });
      return;
    }
    // Optimistically trust stored tokens — the interceptor handles expiry/refresh
    // and calls logout() (which triggers onLogout → clears store) if unrecoverable
    set({ isAuthenticated: true });
    try {
      const user = await apiClient.getCurrentUser();
      set({ user, isAuthenticated: true });
    } catch {
      // Interceptor already handled it; don't touch auth state here
    }
  },
}));

// When the API client's refresh chain fails it calls logout(), which now
// notifies the store directly so the user is sent to the login page.
apiClient.setOnLogout(() => {
  useAuthStore.setState({ user: null, isAuthenticated: false });
});
