export default function StatePanels({
  loading,
  error,
  hasMe,
  onRetry,
}: {
  loading: boolean;
  error: string;
  hasMe: boolean;
  onRetry: () => void;
}) {
  if (loading) {
    return (
      <section className="state-panel loading-panel" aria-live="polite">
        <span className="loading-orbit" aria-hidden="true" />
        <span className="micro-label">SYNCING CHANNEL RECORDS</span>
        <p>Contacting the Hunter System…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="state-panel error-panel" role="alert">
        <span className="state-icon" aria-hidden="true">!</span>
        <h2>
          {error.includes('Telegram')
            ? 'Open inside Telegram'
            : error.toLowerCase().includes('hunter')
              ? 'Hunter profile required'
              : 'System link unavailable'}
        </h2>
        <p>{error}</p>
        <button className="button button-secondary" type="button" onClick={onRetry}>Retry connection</button>
      </section>
    );
  }

  if (!hasMe) {
    return (
      <section className="state-panel error-panel" role="alert">
        <span className="state-icon" aria-hidden="true">!</span>
        <h2>Hunter profile required</h2>
        <p>Start the bot and awaken as a Hunter before opening this panel.</p>
      </section>
    );
  }

  return null;
}
