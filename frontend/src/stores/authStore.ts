import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  token: string | null;
  username: string | null;
  role: string | null;
  setSession: (token: string, username: string, role: string) => void;
  clearSession: () => void;
}

// Persisted so a page refresh doesn't sign the user out. The API client's
// in-memory token is kept in sync separately (see App.tsx) since this
// store and src/api/client.ts are intentionally independent modules.
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      username: null,
      role: null,
      setSession: (token, username, role) => set({ token, username, role }),
      clearSession: () => set({ token: null, username: null, role: null }),
    }),
    { name: 'bloomberg-auth' }
  )
);

interface LoginModalState {
  open: boolean;
  reason: string | undefined;
  openLoginModal: (reason?: string) => void;
  closeLoginModal: () => void;
}

// Not persisted (UI-only, transient) -- lets any component (e.g. a page
// hitting a 401 on an authenticated action) trigger the shared login
// modal without prop-drilling through the shell.
export const useLoginModalStore = create<LoginModalState>((set) => ({
  open: false,
  reason: undefined,
  openLoginModal: (reason) => set({ open: true, reason }),
  closeLoginModal: () => set({ open: false, reason: undefined }),
}));
