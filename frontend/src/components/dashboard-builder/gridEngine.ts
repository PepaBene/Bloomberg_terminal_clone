// Grid calculation utilities — pure functions, no React

export interface GridCell {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PanelLayout {
  id: string;
  cell: GridCell;
  title: string;
  componentType: string;
}

// Default layout fills a 12-column grid with reasonable panels
export function createDefaultLayout(cols: number): PanelLayout[] {
  const half = Math.floor(cols / 2);
  const third = Math.floor(cols / 3);
  return [
    { id: 'panel-1', cell: { x: 0, y: 0, w: half, h: 4 }, title: 'Price Chart', componentType: 'PriceChart' },
    { id: 'panel-2', cell: { x: half, y: 0, w: cols - half, h: 4 }, title: 'Company Overview', componentType: 'CompanyOverview' },
    { id: 'panel-3', cell: { x: 0, y: 4, w: third, h: 4 }, title: 'Fundamentals', componentType: 'Fundamentals' },
    { id: 'panel-4', cell: { x: third, y: 4, w: third, h: 4 }, title: 'Watchlist', componentType: 'Watchlist' },
    { id: 'panel-5', cell: { x: third * 2, y: 4, w: cols - third * 2, h: 4 }, title: 'News', componentType: 'News' },
  ];
}

export function snapToGrid(
  x: number,
  y: number,
  cellW: number,
  cellH: number,
): { x: number; y: number } {
  return {
    x: Math.round(x / cellW),
    y: Math.round(y / cellH),
  };
}

function cellsOverlap(a: GridCell, b: GridCell): boolean {
  return (
    a.x < b.x + b.w &&
    a.x + a.w > b.x &&
    a.y < b.y + b.h &&
    a.y + a.h > b.y
  );
}

export function canPlace(
  layout: PanelLayout[],
  id: string,
  cell: GridCell,
  cols: number,
  rows: number,
): boolean {
  // Boundary check
  if (cell.x < 0 || cell.y < 0) return false;
  if (cell.x + cell.w > cols) return false;
  if (cell.y + cell.h > rows) return false;
  if (cell.w < 1 || cell.h < 1) return false;

  // Collision check against all other panels
  for (const panel of layout) {
    if (panel.id === id) continue;
    if (cellsOverlap(cell, panel.cell)) return false;
  }
  return true;
}

// Compact layout: push all panels as far up as possible, then as far left as possible
export function compactLayout(layout: PanelLayout[]): PanelLayout[] {
  // Sort by y first, then x
  const sorted = [...layout].sort((a, b) =>
    a.cell.y !== b.cell.y ? a.cell.y - b.cell.y : a.cell.x - b.cell.x,
  );

  const compacted: PanelLayout[] = [];

  for (const panel of sorted) {
    let { x, y, w, h } = panel.cell;

    // Try to move panel up as far as possible
    let newY = 0;
    while (newY < y) {
      const testCell: GridCell = { x, y: newY, w, h };
      const conflicts = compacted.some(p => cellsOverlap(testCell, p.cell));
      if (!conflicts) {
        y = newY;
        break;
      }
      newY++;
    }

    compacted.push({ ...panel, cell: { x, y, w, h } });
  }

  return compacted;
}
