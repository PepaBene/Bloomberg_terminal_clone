import { create } from 'zustand';
import { parseCommand, type ParsedCommand } from '@/api/commandParser';

/* ── Types ────────────────────────────────────────────────── */

export interface CommandBarResult {
  id: string;
  type: 'security' | 'command' | 'recent' | 'navigation';
  title: string;
  subtitle?: string;
  meta?: string;
}

interface CommandBarState {
  isOpen: boolean;
  query: string;
  results: CommandBarResult[];
  activeIndex: number;
  open: () => void;
  close: () => void;
  toggle: () => void;
  setQuery: (q: string) => void;
  setResults: (results: CommandBarResult[]) => void;
  setActiveIndex: (i: number) => void;
  executeCommand: (input: string) => ParsedCommand;
}

/* ── Store ────────────────────────────────────────────────── */

export const useCommandBar = create<CommandBarState>((set) => ({
  isOpen: false,
  query: '',
  results: [],
  activeIndex: 0,

  open: () => set({ isOpen: true, query: '', results: [], activeIndex: 0 }),
  close: () => set({ isOpen: false }),
  toggle: () =>
    set((state) =>
      state.isOpen
        ? { isOpen: false }
        : { isOpen: true, query: '', results: [], activeIndex: 0 },
    ),

  setQuery: (q: string) => set({ query: q, activeIndex: 0 }),
  setResults: (results: CommandBarResult[]) => set({ results }),
  setActiveIndex: (i: number) => set({ activeIndex: i }),

  executeCommand: (input: string) => parseCommand(input),
}));
