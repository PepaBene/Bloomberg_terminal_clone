import { useRef, useState, useEffect, useCallback, RefObject } from 'react';
import { GridCell, snapToGrid } from './gridEngine';

const GRID_COLS = 12;
const GRID_ROWS = 12;

interface DragResizeState {
  dragHandleRef: RefObject<HTMLDivElement | null>;
  resizeHandleRef: RefObject<HTMLDivElement | null>;
  isDragging: boolean;
  isResizing: boolean;
  currentCell: GridCell;
}

export function useDragResize(
  panelId: string,
  initialCell: GridCell,
  onLayoutChange: (id: string, cell: GridCell) => void,
): DragResizeState {
  const dragHandleRef = useRef<HTMLDivElement | null>(null);
  const resizeHandleRef = useRef<HTMLDivElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [currentCell, setCurrentCell] = useState<GridCell>(initialCell);

  // Keep a ref to current cell to avoid stale closures
  const cellRef = useRef<GridCell>(initialCell);
  cellRef.current = currentCell;

  // Track pixel cell dimensions via parent container
  const containerRef = useRef<HTMLElement | null>(null);

  const getCellDimensions = useCallback(() => {
    const parent = dragHandleRef.current?.closest('[data-grid-container]') as HTMLElement | null;
    if (!parent) return { cellW: 80, cellH: 60 };
    const rect = parent.getBoundingClientRect();
    return {
      cellW: rect.width / GRID_COLS,
      cellH: rect.height / GRID_ROWS,
    };
  }, []);

  // ── Drag ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    const handle = dragHandleRef.current;
    if (!handle) return;

    let startMouseX = 0;
    let startMouseY = 0;
    let startCellX = 0;
    let startCellY = 0;
    let active = false;

    const onMouseDown = (e: MouseEvent) => {
      e.preventDefault();
      active = true;
      startMouseX = e.clientX;
      startMouseY = e.clientY;
      startCellX = cellRef.current.x;
      startCellY = cellRef.current.y;
      setIsDragging(true);
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!active) return;
      const { cellW, cellH } = getCellDimensions();
      const deltaX = e.clientX - startMouseX;
      const deltaY = e.clientY - startMouseY;
      const snapped = snapToGrid(
        startCellX * cellW + deltaX,
        startCellY * cellH + deltaY,
        cellW,
        cellH,
      );
      const newX = Math.max(0, Math.min(snapped.x, GRID_COLS - cellRef.current.w));
      const newY = Math.max(0, snapped.y);
      setCurrentCell(prev => ({ ...prev, x: newX, y: newY }));
    };

    const onMouseUp = () => {
      if (!active) return;
      active = false;
      setIsDragging(false);
      onLayoutChange(panelId, cellRef.current);
    };

    handle.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      handle.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [panelId, getCellDimensions, onLayoutChange]);

  // ── Resize ────────────────────────────────────────────────────────────────
  useEffect(() => {
    const handle = resizeHandleRef.current;
    if (!handle) return;

    let startMouseX = 0;
    let startMouseY = 0;
    let startW = 0;
    let startH = 0;
    let active = false;

    const onMouseDown = (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      active = true;
      startMouseX = e.clientX;
      startMouseY = e.clientY;
      startW = cellRef.current.w;
      startH = cellRef.current.h;
      setIsResizing(true);
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!active) return;
      const { cellW, cellH } = getCellDimensions();
      const deltaX = e.clientX - startMouseX;
      const deltaY = e.clientY - startMouseY;
      const newW = Math.max(1, Math.round(startW + deltaX / cellW));
      const newH = Math.max(1, Math.round(startH + deltaY / cellH));
      const clampedW = Math.min(newW, GRID_COLS - cellRef.current.x);
      setCurrentCell(prev => ({ ...prev, w: clampedW, h: newH }));
    };

    const onMouseUp = () => {
      if (!active) return;
      active = false;
      setIsResizing(false);
      onLayoutChange(panelId, cellRef.current);
    };

    handle.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      handle.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, [panelId, getCellDimensions, onLayoutChange]);

  // Sync external initialCell changes (e.g. layout reset)
  useEffect(() => {
    setCurrentCell(initialCell);
  }, [initialCell.x, initialCell.y, initialCell.w, initialCell.h]);

  // Suppress unused ref warning
  void containerRef;

  return { dragHandleRef, resizeHandleRef, isDragging, isResizing, currentCell };
}
