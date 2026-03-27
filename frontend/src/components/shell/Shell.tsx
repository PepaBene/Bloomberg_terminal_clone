import { ReactNode, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { TopBar } from './TopBar';
import { NavRail } from './NavRail';
import { StatusBar } from './StatusBar';
import { ShortcutReference } from '../ui/ShortcutReference';
import { ExportMenu } from '../ui/ExportMenu';
import { useKeyboardShortcuts, type ShortcutDef } from '@/hooks/useKeyboardShortcuts';
import { useNavigationStore } from '@/stores/navigationHistory';

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  const navigate = useNavigate();
  const navBack = useNavigationStore((s) => s.back);
  const navForward = useNavigationStore((s) => s.forward);

  /* ── Modal / menu state ───────────────────────────────────── */
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  /* ── Shortcut actions (stable refs) ───────────────────────── */
  const openCommandBar = useCallback(() => {
    // Dispatch a synthetic Ctrl+K so TopBar's existing handler opens the CommandBar
    window.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', ctrlKey: true, bubbles: true }),
    );
  }, []);

  const toggleShortcuts = useCallback(() => {
    setShortcutsOpen((prev) => !prev);
  }, []);

  const closeModals = useCallback(() => {
    if (shortcutsOpen) {
      setShortcutsOpen(false);
      return;
    }
    if (exportOpen) {
      setExportOpen(false);
      return;
    }
  }, [shortcutsOpen, exportOpen]);

  const goBackSecurity = useCallback(() => {
    const sec = navBack();
    if (sec) navigate(`/company?ticker=${sec.ticker}`);
  }, [navBack, navigate]);

  const goForwardSecurity = useCallback(() => {
    const sec = navForward();
    if (sec) navigate(`/company?ticker=${sec.ticker}`);
  }, [navForward, navigate]);

  const toggleExport = useCallback(() => {
    setExportOpen((prev) => !prev);
  }, []);

  /* ── Shortcut definitions ─────────────────────────────────── */
  const shortcutDefs: ShortcutDef[] = useMemo(
    () => [
      // ── Navigation ──
      {
        key: '/',
        description: 'Open command bar',
        action: openCommandBar,
        category: 'Navigation',
      },
      {
        key: 'k',
        ctrl: true,
        description: 'Open command bar',
        action: openCommandBar,
        category: 'Navigation',
      },
      {
        key: 'ArrowRight',
        ctrl: true,
        description: 'Next security in history',
        action: goForwardSecurity,
        category: 'Navigation',
      },
      {
        key: 'ArrowLeft',
        ctrl: true,
        description: 'Previous security in history',
        action: goBackSecurity,
        category: 'Navigation',
      },

      // ── Panel ──
      {
        key: 'f',
        description: 'Fullscreen current panel',
        action: () => {
          // Dispatch a custom event that Panel components can listen for
          window.dispatchEvent(new CustomEvent('terminal:panel-fullscreen'));
        },
        category: 'Panel',
      },
      {
        key: 'Escape',
        description: 'Close modal / collapse panel',
        action: closeModals,
        category: 'Panel',
      },
      {
        key: 'z',
        ctrl: true,
        description: 'Collapse all to overview',
        action: () => {
          window.dispatchEvent(new CustomEvent('terminal:collapse-all'));
        },
        category: 'Panel',
      },

      // ── Data ──
      {
        key: 'd',
        ctrl: true,
        description: 'Add to watchlist',
        action: () => {
          window.dispatchEvent(new CustomEvent('terminal:add-to-watchlist'));
        },
        category: 'Data',
      },
      {
        key: 'e',
        ctrl: true,
        description: 'Export panel data',
        action: toggleExport,
        category: 'Data',
      },
      {
        key: 'l',
        ctrl: true,
        description: 'Link / unlink panel from global context',
        action: () => {
          window.dispatchEvent(new CustomEvent('terminal:toggle-panel-link'));
        },
        category: 'Data',
      },

      // ── Search ──
      {
        key: '?',
        shift: true,
        description: 'Keyboard shortcuts reference',
        action: toggleShortcuts,
        category: 'Search',
      },
    ],
    [openCommandBar, goBackSecurity, goForwardSecurity, closeModals, toggleExport, toggleShortcuts],
  );

  /* ── Register shortcuts ───────────────────────────────────── */
  const shortcutEntries = useKeyboardShortcuts(shortcutDefs);

  /* ── Export handlers (placeholder implementations) ─────────── */
  const handleExportCSV = useCallback(() => {
    window.dispatchEvent(new CustomEvent('terminal:export', { detail: { format: 'csv' } }));
  }, []);

  const handleExportJSON = useCallback(() => {
    window.dispatchEvent(new CustomEvent('terminal:export', { detail: { format: 'json' } }));
  }, []);

  const handleExportPNG = useCallback(() => {
    window.dispatchEvent(new CustomEvent('terminal:export', { detail: { format: 'png' } }));
  }, []);

  const handleExportSVG = useCallback(() => {
    window.dispatchEvent(new CustomEvent('terminal:export', { detail: { format: 'svg' } }));
  }, []);

  return (
    <div
      className="grid h-screen overflow-hidden"
      style={{
        gridTemplateRows: '40px 1fr 22px',
        gridTemplateColumns: '56px 1fr',
        gridTemplateAreas: `"topbar topbar" "nav workspace" "status status"`,
      }}
    >
      <div style={{ gridArea: 'topbar' }}>
        <TopBar />
      </div>
      <div style={{ gridArea: 'nav' }}>
        <NavRail />
      </div>
      <div
        style={{
          gridArea: 'workspace',
          boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.45), inset 1px 0 2px rgba(0,0,0,0.2)',
          backgroundImage: `
            url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.025'/%3E%3C/svg%3E")
          `,
          backgroundRepeat: 'repeat',
          backgroundSize: '128px 128px',
        }}
        className="overflow-auto bg-surface-void p-1"
      >
        <div
          style={{
            animation: 'shellFadeIn 180ms ease-out both',
          }}
        >
          {children}
        </div>
        <style>{`
          @keyframes shellFadeIn {
            from { opacity: 0; transform: translateY(2px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
      <div style={{ gridArea: 'status' }}>
        <StatusBar />
      </div>

      {/* ── Shortcut Reference Modal ── */}
      <ShortcutReference
        open={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
        shortcuts={shortcutEntries}
      />

      {/* ── Export Menu ── */}
      <ExportMenu
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        onExportCSV={handleExportCSV}
        onExportJSON={handleExportJSON}
        onExportPNG={handleExportPNG}
        onExportSVG={handleExportSVG}
      />
    </div>
  );
}
