import SystemPanel from '../components/SystemPanel';
import { countdown, number } from '../lib/format';
import type { MeResponse } from '../types';

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

  return (
    <SystemPanel title="Status Window" suffix="상태창">
      <div className="content-stack">
        <div className="profile-identity">
          <span className="rank-seal profile-seal">{hunter.rank.slice(0, 1)}</span>
          <div className="identity-copy">
            <strong>{hunter.display_name}</strong>
            <span>{hunter.rank} RANK <i /> LV. {hunter.level} <i /> {hunter.title}</span>
          </div>
        </div>
        <div className="profile-facts">
          <span>XP <b>{number(hunter.xp)} / {number(hunter.xp_needed)}</b></span>
          <span>POWER <b>{number(hunter.power)}</b></span>
          <span>GOLD <b>{number(hunter.gold)}</b></span>
        </div>
        <button className="button button-secondary" type="button" onClick={onOpenClaim}>
          {ready ? 'Daily ration ready' : `Next ration in ${countdown(claimRemaining)}`}
        </button>
        {me.guild && (
          <button className="button button-secondary" type="button" onClick={onOpenGuild}>
            Guild · {me.guild.name}
          </button>
        )}
      </div>
    </SystemPanel>
  );
}
