import { create } from 'zustand';
import type { AlertEvent } from '@/types/alerts';

interface AlertsState {
  unread: AlertEvent[];
  dismissed: string[];
  addAlerts: (alerts: AlertEvent[]) => void;
  dismiss: (alertId: string) => void;
  dismissAll: () => void;
  unreadCount: () => number;
}

export const useAlertsStore = create<AlertsState>((set, get) => ({
  unread: [],
  dismissed: [],
  addAlerts: (alerts) =>
    set((state) => ({
      unread: [...alerts.filter(a => !state.dismissed.includes(a.id)), ...state.unread],
    })),
  dismiss: (alertId) =>
    set((state) => ({
      unread: state.unread.filter(a => a.id !== alertId),
      dismissed: [...state.dismissed, alertId],
    })),
  dismissAll: () =>
    set((state) => ({
      unread: [],
      dismissed: [...state.dismissed, ...state.unread.map(a => a.id)],
    })),
  unreadCount: () => get().unread.length,
}));
