import { create } from 'zustand';
import type { Security } from '@/types/security';

interface SecurityContextState {
  primary: Security | null;
  comparisons: Security[];
  setPrimary: (security: Security) => void;
  clearPrimary: () => void;
  addComparison: (security: Security) => void;
  removeComparison: (securityId: string) => void;
  clearComparisons: () => void;
}

export const useSecurityStore = create<SecurityContextState>((set) => ({
  primary: null,
  comparisons: [],
  setPrimary: (security) => set({ primary: security }),
  clearPrimary: () => set({ primary: null }),
  addComparison: (security) =>
    set((state) => ({
      comparisons: state.comparisons.length < 5
        ? [...state.comparisons.filter(s => s.security_id !== security.security_id), security]
        : state.comparisons,
    })),
  removeComparison: (securityId) =>
    set((state) => ({
      comparisons: state.comparisons.filter(s => s.security_id !== securityId),
    })),
  clearComparisons: () => set({ comparisons: [] }),
}));
