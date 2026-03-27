export default function FIScreenerDashboard() {
  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold" style={{ color: 'var(--color-text-primary)', fontFamily: 'var(--font-ui)' }}>Fixed Income Screener</h1>
      <p className="text-sm mt-2" style={{ color: 'var(--color-text-secondary)' }}>Screen bonds by rating, OAS, duration, sector, maturity, and yield.</p>
    </div>
  );
}
