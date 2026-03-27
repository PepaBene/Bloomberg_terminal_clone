import { useEffect } from 'react';
import { getChannel, getWindowId } from './channel';
import { useSecurityStore } from '../stores/securityContext';
import { useAlertsStore } from '../stores/alertsState';
import type { StateMessage } from './channel';
import type { Security } from '../types/security';

export function useSyncListener(): void {
  useEffect(() => {
    const channel = getChannel();
    const myId = getWindowId();

    const handler = (event: MessageEvent<StateMessage>) => {
      if (event.data.source === myId) return;
      switch (event.data.type) {
        case 'SECURITY_CONTEXT_CHANGE':
          useSecurityStore.getState().setPrimary(event.data.payload as Security);
          break;
        case 'ALERT_DISMISSED':
          useAlertsStore.getState().dismiss(event.data.payload as string);
          break;
      }
    };

    channel.addEventListener('message', handler);
    return () => channel.removeEventListener('message', handler);
  }, []);
}
