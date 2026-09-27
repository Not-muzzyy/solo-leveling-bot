import SystemPanel from '../components/SystemPanel';
import { countdown, number } from '../lib/format';

export default function ClaimScreen({
  level,
  remaining,
  busy,
  onClaim,
}: {
  level: number;
  remaining: number;
  busy: boolean;
  onClaim: () => void;
}) {
  const goldLow = Math.max(0, 50 + level * 10 - 10);
  const goldHigh = 50 + level * 10 + 20;
  const xpLow = Math.max(0, 30 + level * 8 - 5);
  const xpHigh = 30 + level * 8 + 15;
  const ready = remaining <= 0;

  return (
    <SystemPanel title="Daily Ration" suffix="일일 보급" meta={ready ? 'AVAILABLE' : 'COOLDOWN'}>
      <div className="content-stack">
        <div className="ration-core">
          <div className="ration-emblem" aria-hidden="true"><span>◈</span></div>
          <div>
            <span className="micro-label">HUNTER ALLOCATION</span>
            <strong className="ration-title">Daily Ration</strong>
            <p>Rewards scale with your current level.</p>
          </div>
        </div>
        <div className="reward-grid">
          <div className="reward-cell"><span className="micro-label">GOLD</span><strong>{number(goldLow)}–{number(goldHigh)}</strong><small>random allocation</small></div>
          <div className="reward-cell"><span className="micro-label">EXPERIENCE</span><strong>{number(xpLow)}–{number(xpHigh)}</strong><small>random allocation</small></div>
        </div>
        <button className="sys-btn" type="button" onClick={onClaim} disabled={!ready || busy} data-state={busy ? 'loading' : ready ? 'ready' : 'disabled'}>
          {busy ? <><span className="button-spinner" /> Processing allocation</> : ready ? 'SYS:CLAIM' : `Next ration in ${countdown(remaining)}`}
        </button>
        <p className="claim-footnote">One claim becomes available every 24 hours.</p>
        <section className="info-row">
          <span className="info-glyph" aria-hidden="true">⌁</span>
          <p>Your cooldown is saved with your Hunter record. Reopening the app will not reset it.</p>
        </section>
      </div>
    </SystemPanel>
  );
}
