// Panel linking service — synchronized crosshairs and security selection
import { create } from 'zustand';
import { useCallback, useMemo } from 'react';

export type LinkGroup = 'A' | 'B' | 'C' | 'D' | 'none';

export const LINK_COLORS: Record<LinkGroup, string> = {
  A: 'var(--color-chart-1)',
  B: 'var(--color-chart-2)',
  C: 'var(--color-chart-3)',
  D: 'var(--color-chart-4)',
  none: 'transparent',
};

interface CrosshairEvent {
  panelId: string;
  x: number | null;
  timestamp?: number;
}

// Keep subscribers outside of Zustand state to avoid snapshot instability.
// Sets are mutable references and must not live inside the immutable snapshot.
const _subscribers: Record<string, Set<(event: CrosshairEvent) => void>> = {};

interface PanelLinkState {
  // Maps panelId -> LinkGroup
  panelGroups: Record<string, LinkGroup>;
  // Maps LinkGroup -> current crosshair position
  crosshairs: Record<string, CrosshairEvent>;

  setPanelGroup: (panelId: string, group: LinkGroup) => void;
  broadcastCrosshair: (group: LinkGroup, event: CrosshairEvent) => void;
  subscribe: (group: LinkGroup, cb: (event: CrosshairEvent) => void) => () => void;
}

export const usePanelLinkStore = create<PanelLinkState>((set) => ({
  panelGroups: {},
  crosshairs: {},

  setPanelGroup: (panelId, group) =>
    set(state => ({
      panelGroups: { ...state.panelGroups, [panelId]: group },
    })),

  broadcastCrosshair: (group, event) => {
    set(state => ({
      crosshairs: { ...state.crosshairs, [group]: event },
    }));
    const subs = _subscribers[group];
    if (subs) {
      subs.forEach(cb => cb(event));
    }
  },

  subscribe: (group, cb) => {
    if (!_subscribers[group]) {
      _subscribers[group] = new Set();
    }
    _subscribers[group].add(cb);
    return () => {
      const existing = _subscribers[group];
      if (existing) {
        existing.delete(cb);
      }
    };
  },
}));

// Convenience factory — kept for backward compatibility
export function createPanelLinkStore() {
  return usePanelLinkStore;
}

export interface UsePanelLinkReturn {
  linkGroup: LinkGroup;
  setLinkGroup: (group: LinkGroup) => void;
  broadcastCrosshair: (x: number | null) => void;
  subscribeCrosshair: (cb: (event: CrosshairEvent) => void) => () => void;
}

export function usePanelLink(panelId: string): UsePanelLinkReturn {
  // Select individual slices to avoid re-render on unrelated state changes
  const linkGroup: LinkGroup = usePanelLinkStore(
    (s) => s.panelGroups[panelId] ?? 'none',
  );
  const setPanelGroup = usePanelLinkStore((s) => s.setPanelGroup);
  const storeBroadcast = usePanelLinkStore((s) => s.broadcastCrosshair);
  const storeSubscribe = usePanelLinkStore((s) => s.subscribe);

  const setLinkGroup = useCallback(
    (group: LinkGroup) => setPanelGroup(panelId, group),
    [panelId, setPanelGroup],
  );

  const broadcastCrosshair = useCallback(
    (x: number | null) => {
      if (linkGroup === 'none') return;
      storeBroadcast(linkGroup, { panelId, x, timestamp: Date.now() });
    },
    [panelId, linkGroup, storeBroadcast],
  );

  const subscribeCrosshair = useCallback(
    (cb: (event: CrosshairEvent) => void) => {
      if (linkGroup === 'none') return () => {};
      return storeSubscribe(linkGroup, cb);
    },
    [linkGroup, storeSubscribe],
  );

  return useMemo(
    () => ({ linkGroup, setLinkGroup, broadcastCrosshair, subscribeCrosshair }),
    [linkGroup, setLinkGroup, broadcastCrosshair, subscribeCrosshair],
  );
}
