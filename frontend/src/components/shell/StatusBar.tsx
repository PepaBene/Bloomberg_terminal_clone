export function StatusBar() {
  return (
    <footer className="flex items-center h-[22px] px-3 bg-surface-base border-t border-surface-border text-text-tertiary text-[10px] font-ui gap-4">
      <span>Data as of: {new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC</span>
      <div className="flex-1" />
      <span className="font-data">/ to search</span>
      <span>&bull;</span>
      <span className="font-data">? for shortcuts</span>
    </footer>
  );
}
