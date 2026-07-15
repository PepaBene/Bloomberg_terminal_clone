import { useEffect } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import { Shell } from '@/components/shell/Shell';
import { AppRouter } from '@/router';
import { useSyncListener } from '@/sync/useSyncListener';
import { api } from '@/api/client';
import { useAuthStore } from '@/stores/authStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

function AppInner() {
  useSyncListener();
  // src/api/client.ts's token is a plain in-memory field, intentionally
  // decoupled from the persisted authStore -- resync it here on load and
  // on every login/logout so a page refresh doesn't silently drop the
  // Authorization header even though the user is still "signed in" per
  // localStorage.
  const token = useAuthStore((s) => s.token);
  useEffect(() => {
    api.setToken(token);
  }, [token]);

  return (
    <Shell>
      <AppRouter />
    </Shell>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppInner />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
