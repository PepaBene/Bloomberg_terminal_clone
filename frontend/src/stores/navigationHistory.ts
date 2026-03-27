import { create } from 'zustand';
import type { Security } from '@/types/security';

interface NavigationHistoryState {
  stack: Security[];
  currentIndex: number;
  push: (security: Security) => void;
  back: () => Security | null;
  forward: () => Security | null;
  recent: (n: number) => Security[];
}

export const useNavigationStore = create<NavigationHistoryState>((set, get) => ({
  stack: [],
  currentIndex: -1,
  push: (security) =>
    set((state) => {
      const newStack = [...state.stack.slice(0, state.currentIndex + 1), security];
      return { stack: newStack, currentIndex: newStack.length - 1 };
    }),
  back: () => {
    const state = get();
    if (state.currentIndex > 0) {
      set({ currentIndex: state.currentIndex - 1 });
      return state.stack[state.currentIndex - 1] ?? null;
    }
    return null;
  },
  forward: () => {
    const state = get();
    if (state.currentIndex < state.stack.length - 1) {
      set({ currentIndex: state.currentIndex + 1 });
      return state.stack[state.currentIndex + 1] ?? null;
    }
    return null;
  },
  recent: (n) => get().stack.slice(-n),
}));
