// =============================================================================
// News Domain — React Query Hooks
// Wraps /v3/news endpoints for news & media intelligence
// =============================================================================

import { useQuery, useMutation } from '@tanstack/react-query';
import { api } from '../client';
import { NEWS } from '../endpoints';

const STALE_5M = 5 * 60 * 1000;

// ---------------------------------------------------------------------------
// Entity News
// ---------------------------------------------------------------------------

export function useEntityNews(entityId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['news', 'byEntity', entityId],
    queryFn: () => api.get(NEWS.byEntity(entityId)),
    enabled: options?.enabled ?? !!entityId,
    staleTime: STALE_5M,
  });
}

// ---------------------------------------------------------------------------
// Latest & Trending
// ---------------------------------------------------------------------------

export function useLatestNews() {
  return useQuery({
    queryKey: ['news', 'latest'],
    queryFn: () => api.get(NEWS.latest),
    staleTime: STALE_5M,
  });
}

export function useTrendingNews() {
  return useQuery({
    queryKey: ['news', 'trending'],
    queryFn: () => api.get(NEWS.trending),
    staleTime: STALE_5M,
  });
}

// ---------------------------------------------------------------------------
// Search — POST mutation
// ---------------------------------------------------------------------------

export function useNewsSearch() {
  return useMutation({
    mutationFn: (query: Record<string, unknown>) =>
      api.post(NEWS.search, query),
  });
}

// ---------------------------------------------------------------------------
// By Sector & Topic
// ---------------------------------------------------------------------------

export function useNewsBySector(sector: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['news', 'bySector', sector],
    queryFn: () => api.get(NEWS.bySector(sector)),
    enabled: options?.enabled ?? !!sector,
    staleTime: STALE_5M,
  });
}

export function useNewsByTopic(topic: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['news', 'byTopic', topic],
    queryFn: () => api.get(NEWS.byTopic(topic)),
    enabled: options?.enabled ?? !!topic,
    staleTime: STALE_5M,
  });
}

// ---------------------------------------------------------------------------
// Article Detail & Sources
// ---------------------------------------------------------------------------

export function useNewsArticle(articleId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['news', 'detail', articleId],
    queryFn: () => api.get(NEWS.detail(articleId)),
    enabled: options?.enabled ?? !!articleId,
    staleTime: STALE_5M,
  });
}

export function useNewsSources() {
  return useQuery({
    queryKey: ['news', 'sources'],
    queryFn: () => api.get(NEWS.sources),
    staleTime: STALE_5M,
  });
}
