import { create } from 'zustand';

export type ToastVariant = 'error' | 'success' | 'info' | 'warning';

export interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: ToastItem[];
  showToast: (message: string, variant?: ToastVariant) => void;
  dismissToast: (id: string) => void;
}

const AUTO_DISMISS_MS = 6000;

// Not persisted (transient, UI-only) -- a minimal, reusable toast/inline-
// error surface (P4-F-023 / P4-F-021). Previously there was no toast
// component anywhere in the app; failures on PortfolioList.tsx,
// PortfolioDetail.tsx, and WatchlistView.tsx were surfaced only via
// console.warn/console.error, invisible to the user. Any component can call
// `useToastStore.getState().showToast(...)` (imperatively, e.g. from a
// mutation's onError) or `useToastStore((s) => s.showToast)` (as a hook).
export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  showToast: (message, variant = 'error') => {
    const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    set((state) => ({ toasts: [...state.toasts, { id, message, variant }] }));
    setTimeout(() => {
      get().dismissToast(id);
    }, AUTO_DISMISS_MS);
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));
