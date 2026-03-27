import { create } from 'zustand';
import type { LayoutTemplate, PanelConfig } from '@/types/workspace';

interface WorkspaceState {
  layout: LayoutTemplate;
  panels: PanelConfig[];
  activePanelId: string | null;
  setLayout: (layout: LayoutTemplate) => void;
  addPanel: (panel: PanelConfig) => void;
  removePanel: (id: string) => void;
  updatePanel: (id: string, updates: Partial<PanelConfig>) => void;
  setActivePanel: (id: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  layout: 'dashboard-7',
  panels: [],
  activePanelId: null,
  setLayout: (layout) => set({ layout }),
  addPanel: (panel) => set((state) => ({ panels: [...state.panels, panel] })),
  removePanel: (id) => set((state) => ({ panels: state.panels.filter(p => p.id !== id) })),
  updatePanel: (id, updates) =>
    set((state) => ({
      panels: state.panels.map(p => p.id === id ? { ...p, ...updates } : p),
    })),
  setActivePanel: (id) => set({ activePanelId: id }),
}));
