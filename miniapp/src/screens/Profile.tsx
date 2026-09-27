import SystemPanel from '../components/SystemPanel';
import { countdown, number } from '../lib/format';
import type { MeResponse } from '../types';

const STAT_ROWS: { key: 'str_stat' | 'agi' | 'vit' | 'int_stat' | 'per'; label: string; name: string }[] = [
  { key: 'str_stat', label: 'STR', name: 'Strength' },
  { key: 'agi', label: 'AGI', name: 'Agility' },
  { key: 'vit', label: 'VIT', name: 'Vitality' },
  { key: 'int_stat', label: 'INT', name: 'Intelligence' },
  { key: 'per', label: 'PER', name: 'Perception' },
];

export default function ProfileScreen({
  me,
  claimRemaining,
  onOpenClaim,
  onOpenGuild,
}: {
  me: MeResponse;
  claimRemaining: number;
  onOpenClaim: () => void;
  onOpenGuild: () => void;
}) {
  const hunter = me.hunter;
  const ready = claimRemaining <= 0;
  const pct = Math.min(100, Math.round((hunter.xp / Math.max(1, hunter.xp_needed)) * 100));
  const rankClass = `rank-${hunter.rank.toLowerCase().replaceAll(' ', '-')}`;

  return (
    <SystemPanel title="Status Window" suffix="상태창" meta={`LV. ${hunter.level}`}>
      <div className="content-stack">
        <div className="profile-identity">
          <span className={`rank-seal profile-seal ${rankClass}`}>{hunter.rank.slice(0, 1)}</span>
          <div className="identity-copy">
            <strong>{hunter.display_name}</strong>
            <span>{hunter.rank} RANK <i /> LV. {hunter.level}</span>
            <em className="profile-title">{hunter.title}</em>
          </div>
        </div>

        <div className="profile-xp">
          <div className="profile-xp-head">
            <span className="micro-label">EXPERIENCE</span>
            <span className="profile-xp-num">{number(hunter.xp)} / {number(hunter.xp_needed)} · {pct}%</span>
          </div>
          <div className="xp-bar is-sweeping" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Experience">
            <div className="xp-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <div className="status-grid">
          {STAT_ROWS.map((row) => {
            const value = hunter[row.key];
            const gauge = Math.min(100, Math.round((value / Math.max(40, value)) * 100));
            return (
              <div className="stat-row" key={row.label}>
                <span className="stat-row-label">{row.label}</span>
                <span className="stat-row-name">{row.name}</span>
                <span className="stat-row-value">{value}</span>
                <span className="stat-gauge"><span className="stat-gauge-fill" style={{ width: `${gauge}%` }} /></span>
              </div>
            );
          })}
        </div>

        <div className="profile-facts">
          <span>POWER <b>{number(hunter.power)}</b></span>
          <span>GOLD <b>◈ {number(hunter.gold)}</b></span>
          <span>STORAGE <b>{me.inventory_count}</b></span>
        </div>

        <div className="profile-cta">
          <button className="sys-btn" type="button" onClick={onOpenClaim} disabled={!ready}>
            {ready ? 'Daily ration ready' : `Next ration in ${countdown(claimRemaining)}`}
          </button>
          {me.guild && (
            <button className="button button-secondary" type="button" onClick={onOpenGuild}>
              Guild · {me.guild.name}
            </button>
          )}
        </div>
      </div>
    </SystemPanel>
  );
}
