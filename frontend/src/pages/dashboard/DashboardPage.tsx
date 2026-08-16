// ---------------------------------------------------------------------------
// Custom Dashboard — routes the drag/resize panel-builder (previously built
// but never mounted anywhere) so it's reachable from the nav rail. Panel
// bodies render real, data-backed widgets via PanelRenderer.
// ---------------------------------------------------------------------------
import { DashboardBuilder } from '@/components/dashboard-builder';

export default function DashboardPage() {
  return (
    <div style={{ height: '100%' }}>
      <DashboardBuilder />
    </div>
  );
}
