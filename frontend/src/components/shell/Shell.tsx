import { ReactNode } from 'react';
import { TopBar } from './TopBar';
import { NavRail } from './NavRail';
import { StatusBar } from './StatusBar';

interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div
      className="grid h-screen overflow-hidden"
      style={{
        gridTemplateRows: '40px 1fr 22px',
        gridTemplateColumns: '56px 1fr',
        gridTemplateAreas: `"topbar topbar" "nav workspace" "status status"`,
      }}
    >
      <div style={{ gridArea: 'topbar' }}>
        <TopBar />
      </div>
      <div style={{ gridArea: 'nav' }}>
        <NavRail />
      </div>
      <div
        style={{
          gridArea: 'workspace',
          boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.45), inset 1px 0 2px rgba(0,0,0,0.2)',
          backgroundImage: `
            url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.025'/%3E%3C/svg%3E")
          `,
          backgroundRepeat: 'repeat',
          backgroundSize: '128px 128px',
        }}
        className="overflow-auto bg-surface-void p-1"
      >
        <div
          style={{
            animation: 'shellFadeIn 180ms ease-out both',
          }}
        >
          {children}
        </div>
        <style>{`
          @keyframes shellFadeIn {
            from { opacity: 0; transform: translateY(2px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
      <div style={{ gridArea: 'status' }}>
        <StatusBar />
      </div>
    </div>
  );
}
