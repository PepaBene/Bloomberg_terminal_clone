import { ReactNode } from 'react';
import { TopBar } from './TopBar';
import { NavRail } from './NavRail';
import { StatusBar } from './StatusBar';

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div className="grid h-screen overflow-hidden" style={{
      gridTemplateRows: '40px 1fr 22px',
      gridTemplateColumns: '56px 1fr',
      gridTemplateAreas: `"topbar topbar" "nav workspace" "status status"`,
    }}>
      <div style={{ gridArea: 'topbar' }}>
        <TopBar />
      </div>
      <div style={{ gridArea: 'nav' }}>
        <NavRail />
      </div>
      <div style={{ gridArea: 'workspace' }} className="overflow-auto bg-surface-void p-1">
        {children}
      </div>
      <div style={{ gridArea: 'status' }}>
        <StatusBar />
      </div>
    </div>
  );
}
