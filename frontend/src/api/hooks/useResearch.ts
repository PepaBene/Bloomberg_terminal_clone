// =============================================================================
// Research — React Query Hooks
// =============================================================================

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../client';
import { RESEARCH } from '../endpoints';

const STALE_30M = 30 * 60 * 1000;

// ---------------------------------------------------------------------------
// Primers
// ---------------------------------------------------------------------------

export function useRecentPrimers(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'primers', 'recent'],
    queryFn: () => api.get(RESEARCH.primers.recent),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function usePrimer(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'primers', entityId],
    queryFn: () => api.get(RESEARCH.primers.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

export function useRefreshPrimer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (entityId: string) => api.post(RESEARCH.primers.refresh(entityId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'primers'] });
    },
  });
}

export function useDownloadPrimer(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'primers', entityId, 'download'],
    queryFn: () => api.get(RESEARCH.primers.download(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

// ---------------------------------------------------------------------------
// Briefings
// ---------------------------------------------------------------------------

export function useTodayBriefing(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'briefings', 'today'],
    queryFn: () => api.get(RESEARCH.briefings.today),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useBriefingHistory(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'briefings', 'history'],
    queryFn: () => api.get(RESEARCH.briefings.history),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useBriefingPreferences(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'briefings', 'preferences'],
    queryFn: () => api.get(RESEARCH.briefings.preferences),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useUpdateBriefingPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.put(RESEARCH.briefings.updatePreferences, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'briefings', 'preferences'] });
    },
  });
}

export function useGenerateBriefing() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.briefings.generate, body),
  });
}

// ---------------------------------------------------------------------------
// Anomalies
// ---------------------------------------------------------------------------

export function useActiveAnomalies(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'anomalies', 'active'],
    queryFn: () => api.get(RESEARCH.anomalies.active),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useCriticalAnomalies(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'anomalies', 'critical'],
    queryFn: () => api.get(RESEARCH.anomalies.critical),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useEntityAnomalies(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'anomalies', entityId],
    queryFn: () => api.get(RESEARCH.anomalies.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

export function useAcknowledgeAnomaly() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (anomalyId: string) =>
      api.post(RESEARCH.anomalies.acknowledge(anomalyId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'anomalies'] });
    },
  });
}

export function useAnomalyHistory(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'anomalies', 'history'],
    queryFn: () => api.get(RESEARCH.anomalies.history),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export function useResearchSearch() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.search.query, body),
  });
}

export function useSearchHistory(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'search', 'history'],
    queryFn: () => api.get(RESEARCH.search.history),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useSuggestedQueries(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'search', 'suggested'],
    queryFn: () => api.get(RESEARCH.search.suggested),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useSavedQueries(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'search', 'saved'],
    queryFn: () => api.get(RESEARCH.search.savedQueries),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useSaveSearchCriteria() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.search.saveCriteria, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'search', 'saved'] });
    },
  });
}

// ---------------------------------------------------------------------------
// Thesis
// ---------------------------------------------------------------------------

export function useRecentTheses(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'thesis', 'recent'],
    queryFn: () => api.get(RESEARCH.thesis.recent),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useEntityThesis(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'thesis', entityId],
    queryFn: () => api.get(RESEARCH.thesis.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

export function useGenerateThesis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.thesis.generate, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'thesis'] });
    },
  });
}

export function useUpdateThesis() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ thesisId, ...body }: Record<string, unknown> & { thesisId: string }) =>
      api.put(RESEARCH.thesis.update(thesisId), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research', 'thesis'] });
    },
  });
}

export function useValidateThesis() {
  return useMutation({
    mutationFn: (thesisId: string) =>
      api.post(RESEARCH.thesis.validate(thesisId)),
  });
}

// ---------------------------------------------------------------------------
// QA
// ---------------------------------------------------------------------------

export function useAskQuestion() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.qa.ask, body),
  });
}

export function useQaHistory(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'qa', 'history'],
    queryFn: () => api.get(RESEARCH.qa.history),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useFollowUp() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.qa.followUp, body),
  });
}

export function useQaSources(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'qa', 'sources'],
    queryFn: () => api.get(RESEARCH.qa.sources),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

// ---------------------------------------------------------------------------
// Themes
// ---------------------------------------------------------------------------

// Note: theme *listing* is `useResearchThemes()` in useIntelligence.ts (hits
// the same real `/v4/research/themes/dashboard` this file's `RESEARCH.themes.list`
// points at) -- no separate `useThemes()` here to avoid two hooks for one endpoint.

export function useThemeDetail(themeId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'themes', themeId, 'summary'],
    queryFn: () => api.get(RESEARCH.themes.detail(themeId)),
    enabled: options?.enabled ?? !!themeId,
    staleTime: STALE_30M,
  });
}

export function useThemeScenarios(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'themes', 'scenarios'],
    queryFn: () => api.get(RESEARCH.themes.scenarios),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useThemeScreen() {
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.themes.screen, body),
  });
}

// No useCreateTheme/useUpdateTheme: themes are engine-assigned exposure
// labels (macro_theme_scores is keyed by entity_id + theme), not
// user-authored resources -- there's nothing for a "create theme" form to
// create. A prior version of this file had CRUD hooks pointed at a
// `/v4/research/themes` create/update pair the backend never implemented.

export function useThemeSecurities(themeId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research', 'themes', themeId, 'securities'],
    queryFn: () => api.get(RESEARCH.themes.securities(themeId)),
    enabled: options?.enabled ?? !!themeId,
    staleTime: STALE_30M,
  });
}

// ---------------------------------------------------------------------------
// Notes
// ---------------------------------------------------------------------------

export function useResearchNotes(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research-notes', 'list'],
    queryFn: () => api.get(RESEARCH.notes.list),
    enabled: options?.enabled ?? true,
    staleTime: STALE_30M,
  });
}

export function useEntityNotes(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['research-notes', entityId],
    queryFn: () => api.get(RESEARCH.notes.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_30M,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post(RESEARCH.notes.create, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-notes'] });
    },
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, ...body }: Record<string, unknown> & { noteId: string }) =>
      api.put(RESEARCH.notes.update(noteId), body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-notes'] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => api.delete(RESEARCH.notes.delete(noteId)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['research-notes'] });
    },
  });
}
