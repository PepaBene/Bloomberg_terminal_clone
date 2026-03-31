import { useState, useEffect, useCallback } from 'react';

export interface Annotation {
  id: string;
  targetId: string;
  note: string;
  color: string;
  createdAt: string;
  position?: { x: number; y: number };
}

const STORAGE_KEY = 'bbdf:annotations';

function loadAnnotations(): Annotation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Annotation[]) : [];
  } catch {
    return [];
  }
}

function saveAnnotations(annotations: Annotation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(annotations));
  } catch {
    // Storage quota exceeded — ignore
  }
}

function generateId(): string {
  return `ann_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

interface UseAnnotationsReturn {
  annotations: Annotation[];
  add: (partial: Omit<Annotation, 'id' | 'createdAt'>) => Annotation;
  update: (id: string, updates: Partial<Omit<Annotation, 'id' | 'createdAt'>>) => void;
  remove: (id: string) => void;
  clear: (targetId?: string) => void;
}

export function useAnnotations(targetId?: string): UseAnnotationsReturn {
  const [all, setAll] = useState<Annotation[]>(() => loadAnnotations());

  // Sync from storage on mount (in case another tab wrote)
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setAll(loadAnnotations());
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const annotations = targetId
    ? all.filter(a => a.targetId === targetId)
    : all;

  const add = useCallback(
    (partial: Omit<Annotation, 'id' | 'createdAt'>): Annotation => {
      const annotation: Annotation = {
        ...partial,
        id: generateId(),
        createdAt: new Date().toISOString(),
      };
      setAll(prev => {
        const next = [...prev, annotation];
        saveAnnotations(next);
        return next;
      });
      return annotation;
    },
    [],
  );

  const update = useCallback(
    (id: string, updates: Partial<Omit<Annotation, 'id' | 'createdAt'>>) => {
      setAll(prev => {
        const next = prev.map(a => (a.id === id ? { ...a, ...updates } : a));
        saveAnnotations(next);
        return next;
      });
    },
    [],
  );

  const remove = useCallback((id: string) => {
    setAll(prev => {
      const next = prev.filter(a => a.id !== id);
      saveAnnotations(next);
      return next;
    });
  }, []);

  const clear = useCallback((tid?: string) => {
    setAll(prev => {
      const next = tid ? prev.filter(a => a.targetId !== tid) : [];
      saveAnnotations(next);
      return next;
    });
  }, []);

  return { annotations, add, update, remove, clear };
}
