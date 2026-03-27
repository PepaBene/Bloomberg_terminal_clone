export type LayoutTemplate = 'single' | 'split-h' | 'split-v' | 'three-col' | 'golden' | 'quad' | 'dashboard-5' | 'dashboard-7';

export interface PanelConfig {
  id: string;
  type: string;
  position: { row: number; col: number; rowSpan: number; colSpan: number };
  linkGroup: string | null;
  isExpanded: boolean;
  isDetached: boolean;
}
