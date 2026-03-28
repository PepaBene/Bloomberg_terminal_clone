import { useState, useCallback, useEffect, useRef } from 'react';

/* ── Types ────────────────────────────────────────────────── */

export interface TableConfig {
  columnOrder: string[];
  columnWidths: Record<string, number>;
  hiddenColumns: string[];
  sortColumn: string | null;
  sortDirection: 'asc' | 'desc' | null;
}

export interface UseTableConfigReturn {
  config: TableConfig;
  setColumnWidth: (key: string, width: number) => void;
  toggleColumn: (key: string) => void;
  reorderColumns: (from: number, to: number) => void;
  setSort: (column: string | null, direction: 'asc' | 'desc' | null) => void;
  resetConfig: () => void;
}

/* ── Helpers ──────────────────────────────────────────────── */

function storageKey(tableId: string): string {
  return `table-config-${tableId}`;
}

function buildDefault(columns: string[]): TableConfig {
  return {
    columnOrder: columns,
    columnWidths: {},
    hiddenColumns: [],
    sortColumn: null,
    sortDirection: null,
  };
}

function loadConfig(tableId: string, defaults: string[]): TableConfig {
  try {
    const raw = localStorage.getItem(storageKey(tableId));
    if (!raw) return buildDefault(defaults);
    const stored = JSON.parse(raw) as TableConfig;

    // Merge: add any new default columns that aren't in the stored order
    const storedSet = new Set(stored.columnOrder);
    const merged = [...stored.columnOrder];
    for (const col of defaults) {
      if (!storedSet.has(col)) {
        merged.push(col);
      }
    }

    // Remove columns no longer in defaults
    const defaultSet = new Set(defaults);
    const pruned = merged.filter((c) => defaultSet.has(c));

    return {
      ...stored,
      columnOrder: pruned,
      hiddenColumns: stored.hiddenColumns.filter((c) => defaultSet.has(c)),
    };
  } catch {
    return buildDefault(defaults);
  }
}

function saveConfig(tableId: string, config: TableConfig): void {
  try {
    localStorage.setItem(storageKey(tableId), JSON.stringify(config));
  } catch {
    // Storage full or unavailable — silently ignore
  }
}

/* ── Hook ─────────────────────────────────────────────────── */

export function useTableConfig(
  tableId: string,
  defaultColumns: string[],
): UseTableConfigReturn {
  const [config, setConfig] = useState<TableConfig>(() =>
    loadConfig(tableId, defaultColumns),
  );

  // Track previous tableId so we reload when it changes
  const prevTableId = useRef(tableId);
  useEffect(() => {
    if (prevTableId.current !== tableId) {
      prevTableId.current = tableId;
      setConfig(loadConfig(tableId, defaultColumns));
    }
  }, [tableId, defaultColumns]);

  // Persist on every change
  useEffect(() => {
    saveConfig(tableId, config);
  }, [tableId, config]);

  const setColumnWidth = useCallback((key: string, width: number) => {
    setConfig((prev) => ({
      ...prev,
      columnWidths: { ...prev.columnWidths, [key]: width },
    }));
  }, []);

  const toggleColumn = useCallback((key: string) => {
    setConfig((prev) => {
      const hidden = new Set(prev.hiddenColumns);
      if (hidden.has(key)) {
        hidden.delete(key);
      } else {
        hidden.add(key);
      }
      return { ...prev, hiddenColumns: Array.from(hidden) };
    });
  }, []);

  const reorderColumns = useCallback((from: number, to: number) => {
    setConfig((prev) => {
      const order = [...prev.columnOrder];
      const [removed] = order.splice(from, 1);
      if (removed !== undefined) {
        order.splice(to, 0, removed);
      }
      return { ...prev, columnOrder: order };
    });
  }, []);

  const setSort = useCallback(
    (column: string | null, direction: 'asc' | 'desc' | null) => {
      setConfig((prev) => ({
        ...prev,
        sortColumn: column,
        sortDirection: direction,
      }));
    },
    [],
  );

  const resetConfig = useCallback(() => {
    setConfig(buildDefault(defaultColumns));
  }, [defaultColumns]);

  return {
    config,
    setColumnWidth,
    toggleColumn,
    reorderColumns,
    setSort,
    resetConfig,
  };
}
