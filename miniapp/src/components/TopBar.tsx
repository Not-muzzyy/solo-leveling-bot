import { number } from '../lib/format';
import type { MeResponse } from '../types';

export default function TopBar({
  me,
  loading,
  onRefresh,
}: {
  me: MeResponse | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  return (
    <>
      <header className="topbar">
        <div className="system-mark" aria-hidden="true">S</div>
        <div className="topbar-copy">
          <span className="micro-label">HUNTER SYSTEM</span>
          <span className="connection-state"><span className="status-dot" /> ONLINE</span>
        </div>
        <button className="icon-button refresh-button" type="button" aria-label="Refresh System data" onClick={onRefresh} disabled={loading}>
          <span aria-hidden="true">↻</span>
        </button>
      </header>

      {me && (
        <section className="hunter-strip" aria-label="Hunter status">
          <div className="hunter-identity">
            <span className={`rank-seal rank-${me.hunter.rank.toLowerCase().replaceAll(' ', '-')}`}>{me.hunter.rank.slice(0, 1)}</span>
            <div className="identity-copy">
              <strong>{me.hunter.display_name}</strong>
              <span>{me.hunter.rank} RANK <i /> LV. {me.hunter.level}</span>
            </div>
          </div>
          <div className="treasury">
            <span className="micro-label">TREASURY</span>
            <strong><span aria-hidden="true">◈</span> {number(me.hunter.gold)}</strong>
          </div>
        </section>
      )}
    </>
  );
}
