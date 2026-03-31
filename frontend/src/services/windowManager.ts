// Tauri multi-window management with graceful web fallback

const isTauri = (): boolean =>
  typeof window !== 'undefined' && !!((window as unknown as Record<string, unknown>).__TAURI_INTERNALS__);

interface TauriWebviewWindow {
  label: string;
  title?: string;
}

async function getTauriWebviewWindow(
  label: string,
  title: string,
): Promise<TauriWebviewWindow | null> {
  try {
    // Dynamic import to avoid hard dependency at build time
    const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow' as string);
    return new (WebviewWindow as new (label: string, opts: Record<string, unknown>) => TauriWebviewWindow)(label, {
      url: `/#detached/${label}`,
      title,
      decorations: true,
      width: 1024,
      height: 768,
      resizable: true,
      transparent: false,
    });
  } catch {
    return null;
  }
}

// Track open detached windows (web mode)
const detachedWindows = new Map<string, Window>();

export async function detachPanel(panelId: string, title: string): Promise<void> {
  if (isTauri()) {
    const win = await getTauriWebviewWindow(panelId, title);
    if (win) return;
    // Fallback if creation failed — continue to web mode
  }

  // Web fallback: open browser window
  const existing = detachedWindows.get(panelId);
  if (existing && !existing.closed) {
    existing.focus();
    return;
  }
  const url = `${window.location.origin}${window.location.pathname}#detached/${panelId}`;
  const win = window.open(url, `panel_${panelId}`, 'width=1024,height=768,resizable=yes');
  if (win) {
    win.document.title = title;
    detachedWindows.set(panelId, win);
  }
}

export async function focusDetachedWindow(panelId: string): Promise<void> {
  if (isTauri()) {
    try {
      const { WebviewWindow } = await import('@tauri-apps/api/webviewWindow' as string);
      const win = (WebviewWindow as { getByLabel: (label: string) => unknown }).getByLabel(panelId);
      if (win && typeof (win as Record<string, unknown>).setFocus === 'function') {
        await (win as { setFocus: () => Promise<void> }).setFocus();
      }
    } catch {
      // Ignore Tauri errors
    }
    return;
  }

  const win = detachedWindows.get(panelId);
  if (win && !win.closed) {
    win.focus();
  }
}

export function isDetached(): boolean {
  if (typeof window === 'undefined') return false;
  return window.location.hash.startsWith('#detached/');
}

export function getDetachedPanelId(): string | null {
  if (!isDetached()) return null;
  return window.location.hash.replace('#detached/', '') || null;
}
