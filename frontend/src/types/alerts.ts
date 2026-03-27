export interface AlertEvent {
  id: string;
  entity_id: string | null;
  alert_type: string;
  severity: string;
  title: string;
  description: string;
  is_acknowledged: boolean;
  created_at: string;
}

export interface AlertRule {
  id: string;
  user_id: string;
  alert_type: string;
  is_enabled: boolean;
  threshold_value: number | null;
  entity_scope: Record<string, unknown> | null;
  conditions: Record<string, unknown> | null;
}
