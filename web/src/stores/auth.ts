/**
 * Auth store: manages login state, JWT tokens, and user info.
 */
import { defineStore } from "pinia";
import { authApi, type User } from "../api/client";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  loading: boolean;
  error: string | null;
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    user: null,
    accessToken: localStorage.getItem("access_token"),
    refreshToken: localStorage.getItem("refresh_token"),
    loading: false,
    error: null,
  }),

  getters: {
    isAuthenticated: (state) => !!state.accessToken,
  },

  actions: {
    async login(email: string, password: string) {
      this.loading = true;
      this.error = null;
      try {
        const tokens = await authApi.login(email, password);
        this.accessToken = tokens.access_token;
        this.refreshToken = tokens.refresh_token;
        localStorage.setItem("access_token", tokens.access_token);
        localStorage.setItem("refresh_token", tokens.refresh_token);

        this.user = await authApi.me();
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : "Login failed";
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async register(email: string, password: string, displayName: string) {
      this.loading = true;
      this.error = null;
      try {
        await authApi.register(email, password, displayName);
        // Auto-login after registration
        await this.login(email, password);
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : "Registration failed";
        throw err;
      } finally {
        this.loading = false;
      }
    },

    async fetchUser() {
      if (!this.accessToken) return;
      try {
        this.user = await authApi.me();
      } catch {
        this.logout();
      }
    },

    logout() {
      this.user = null;
      this.accessToken = null;
      this.refreshToken = null;
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    },
  },
});
