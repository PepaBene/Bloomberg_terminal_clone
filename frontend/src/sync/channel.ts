const CHANNEL_NAME = 'frp_terminal_state';

type MessageType =
  | 'SECURITY_CONTEXT_CHANGE'
  | 'COMPARISON_CONTEXT_CHANGE'
  | 'WORKSPACE_LAYOUT_CHANGE'
  | 'ALERT_DISMISSED';

interface StateMessage {
  type: MessageType;
  payload: unknown;
  source: string;
}

const windowId = `window_${Date.now()}_${Math.random().toString(36).slice(2)}`;
let channel: BroadcastChannel | null = null;

export function getChannel(): BroadcastChannel {
  if (!channel) {
    channel = new BroadcastChannel(CHANNEL_NAME);
  }
  return channel;
}

export function broadcastMessage(type: MessageType, payload: unknown): void {
  getChannel().postMessage({ type, payload, source: windowId } satisfies StateMessage);
}

export function getWindowId(): string {
  return windowId;
}

export type { StateMessage, MessageType };
