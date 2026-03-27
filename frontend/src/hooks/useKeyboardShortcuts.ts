import { useEffect, useCallback, useRef } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface ShortcutDef {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  description: string;
  action: () => void;
  category: string;
}

export interface ShortcutEntry {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  description: string;
  category: string;
}

/* ── Helpers ──────────────────────────────────────────────── */

function isInputTarget(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (el.isContentEditable) return true;
  return false;
}

function matchesShortcut(e: KeyboardEvent, def: ShortcutDef): boolean {
  const wantsCtrl = def.ctrl ?? false;
  const wantsMeta = def.meta ?? false;
  const wantsShift = def.shift ?? false;

  // Ctrl/Cmd modifier: match either ctrlKey or metaKey for cross-platform
  const hasCtrlOrMeta = e.ctrlKey || e.metaKey;
  const needsCtrlOrMeta = wantsCtrl || wantsMeta;

  if (needsCtrlOrMeta !== hasCtrlOrMeta) return false;
  if (wantsShift !== e.shiftKey) return false;

  // For non-modifier shortcuts, reject if Alt is held
  if (e.altKey) return false;

  // Normalise key comparison
  const eventKey = e.key.toLowerCase();
  const defKey = def.key.toLowerCase();

  // Handle special key names
  if (defKey === 'escape') return eventKey === 'escape';
  if (defKey === 'enter') return eventKey === 'enter';
  if (defKey === 'tab') return eventKey === 'tab';
  if (defKey === 'arrowup') return eventKey === 'arrowup';
  if (defKey === 'arrowdown') return eventKey === 'arrowdown';
  if (defKey === 'arrowleft') return eventKey === 'arrowleft';
  if (defKey === 'arrowright') return eventKey === 'arrowright';

  return eventKey === defKey;
}

/* ── Hook ─────────────────────────────────────────────────── */

/**
 * Global keyboard shortcut hook.
 *
 * Registers a set of keyboard shortcuts on `keydown` and fires
 * the associated action. Shortcuts are ignored when the user is
 * focused on an input, textarea, select, or contentEditable element
 * — unless the shortcut uses a Ctrl/Cmd modifier.
 *
 * Returns a stable `shortcuts` array (without action callbacks)
 * suitable for rendering in the ShortcutReference modal.
 */
export function useKeyboardShortcuts(defs: ShortcutDef[]): ShortcutEntry[] {
  // Keep a ref to always have the latest defs without re-attaching the listener
  const defsRef = useRef(defs);
  defsRef.current = defs;

  const handler = useCallback((e: KeyboardEvent) => {
    const currentDefs = defsRef.current;

    for (const def of currentDefs) {
      if (!matchesShortcut(e, def)) continue;

      // For non-modifier shortcuts, ignore if user is in an input field
      const needsModifier = def.ctrl || def.meta;
      if (!needsModifier && isInputTarget(e)) continue;

      e.preventDefault();
      def.action();
      return;
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [handler]);

  // Return a stable descriptive array (no action callbacks)
  // Memoisation is intentionally skipped — callers should memoise
  // the defs array if they need referential stability.
  const entries: ShortcutEntry[] = defs.map(({ key, ctrl, meta, shift, description, category }) => ({
    key,
    ...(ctrl ? { ctrl } : {}),
    ...(meta ? { meta } : {}),
    ...(shift ? { shift } : {}),
    description,
    category,
  }));

  return entries;
}
