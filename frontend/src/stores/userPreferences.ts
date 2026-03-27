import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { LayoutTemplate } from '@/types/workspace';
import type { TimeRange } from '@/types/charts';

interface UserPreferencesState {
  compactMode: boolean;
  defaultDateRange: TimeRange;
  defaultLayout: LayoutTemplate;
  token: string | null;
  setCompactMode: (compact: boolean) => void;
  setDefaultDateRange: (range: TimeRange) => void;
  setDefaultLayout: (layout: LayoutTemplate) => void;
  setToken: (token: string | null) => void;
}

export const usePreferencesStore = create<UserPreferencesState>()(
  persist(
    (set) => ({
      compactMode: false,
      defaultDateRange: '1Y',
      defaultLayout: 'dashboard-7',
      token: null,
      setCompactMode: (compactMode) => set({ compactMode }),
      setDefaultDateRange: (defaultDateRange) => set({ defaultDateRange }),
      setDefaultLayout: (defaultLayout) => set({ defaultLayout }),
      setToken: (token) => set({ token }),
    }),
    { name: 'bloomberg-preferences' }
  )
);
