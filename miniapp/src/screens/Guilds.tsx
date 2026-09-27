import SystemPanel from '../components/SystemPanel';
import { number } from '../lib/format';
import type { GuildSort, GuildSummary } from '../types';

const SORT_LABELS: Record<GuildSort, string> = {
  power: 'Power',
  level: 'Level',
  gold: 'Gold',
  members: 'Members',
};

export default function GuildsScreen({
  guilds,
  currentGuild,
  selectedGuild,
  sort,
  onSort,
  onSelect,
}: {
  guilds: GuildSummary[];
  currentGuild: GuildSummary | null;
  selectedGuild: GuildSummary | null;
  sort: GuildSort;
  onSort: (sort: GuildSort) => void;
  onSelect: (guild: GuildSummary) => void;
}) {
  const sortOptions = Object.keys(SORT_LABELS) as GuildSort[];
  const shownGuild = selectedGuild ?? currentGuild;
  return (
    <div className="content-stack">
      {shownGuild ? (
        <SystemPanel title="Guild Registry" suffix="길드 정보" meta={currentGuild?.id === shownGuild.id ? 'YOUR SYNDICATE' : `#${shownGuild.id}`}>
          <GuildDetail guild={shownGuild} />
        </SystemPanel>
      ) : (
        <section className="empty-guild-card">
          <span className="empty-sigil" aria-hidden="true">♜</span>
          <div><span className="micro-label">NO ACTIVE AFFILIATION</span><h2>Guild records are open</h2><p>Browse the registry below to review Hunter guilds.</p></div>
        </section>
      )}
      <section className="directory-section">
        <div className="subsection-heading"><div><span className="micro-label">SYSTEM REGISTRY</span><h2>Guild standings</h2></div><span className="count-badge">{guilds.length}</span></div>
        <div className="sort-list" aria-label="Sort guilds">
          {sortOptions.map((option) => <button key={option} className={`sort-chip${sort === option ? ' is-selected' : ''}`} type="button" aria-pressed={sort === option} onClick={() => onSort(option)}>{SORT_LABELS[option]}</button>)}
        </div>
        {guilds.length ? (
          <div className="guild-list">
            {guilds.map((guild, index) => (
              <button className={`guild-row${currentGuild?.id === guild.id ? ' is-mine' : ''}`} type="button" key={guild.id} onClick={() => onSelect(guild)} aria-label={`View ${guild.name}`}>
                <span className="guild-place">{String(index + 1).padStart(2, '0')}</span>
                <span className="guild-row-sigil" aria-hidden="true">♜</span>
                <span className="guild-row-copy"><strong>{guild.name}</strong><small>{guild.member_count}/{guild.max_members} hunters · {guild.owner_name}</small></span>
                <span className="guild-row-score"><b>{number(guild.total_power)}</b><small>POWER</small></span>
                <span className="row-chevron" aria-hidden="true">›</span>
              </button>
            ))}
          </div>
        ) : (
          <section className="state-panel compact-state"><p>No guilds have entered the registry yet.</p></section>
        )}
      </section>
    </div>
  );
}

function GuildDetail({ guild }: { guild: GuildSummary }) {
  return (
    <>
      <div className="guild-title-row"><span className="guild-crest" aria-hidden="true">♜</span><div><h2>{guild.name}</h2><span className="guild-owner">Sovereign · {guild.owner_name}</span></div></div>
      <p className="guild-description">{guild.description}</p>
      <div className="guild-metrics">
        <Metric label="ROSTER" value={`${guild.member_count}/${guild.max_members}`} />
        <Metric label="TOTAL POWER" value={number(guild.total_power)} />
        <Metric label="AVG LEVEL" value={String(guild.average_level)} />
      </div>
      <div className="guild-bonus"><span aria-hidden="true">✦</span><span><b>+{guild.xp_bonus_percent}% HUNT XP</b><small>Active syndicate perk</small></span><span className="bonus-state">ACTIVE</span></div>
      <div className="roster-heading"><span className="micro-label">HUNTER ROSTER</span><span>{guild.member_count} registered</span></div>
      <div className="roster-list">
        {guild.members.map((member, index) => (
          <div className="roster-row" key={`${member.display_name}-${index}`}>
            <span className="roster-index">{String(index + 1).padStart(2, '0')}</span>
            <span className={`roster-rank rank-${member.rank.toLowerCase().replaceAll(' ', '-')}`}>{member.rank.slice(0, 1)}</span>
            <span className="roster-person"><strong>{member.display_name}</strong><small>{member.role === 'owner' ? 'SOVEREIGN' : 'HUNTER'} · LV. {member.level}</small></span>
            <span className="roster-power"><b>{number(member.power)}</b><small>POWER</small></span>
          </div>
        ))}
      </div>
      <div className="war-record"><span className="micro-label">WAR RECORD</span><span><b>{guild.war_wins}</b> W <i /> <b>{guild.war_losses}</b> L</span><strong>{number(guild.war_score)} PTS</strong></div>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="guild-metric"><span className="micro-label">{label}</span><strong>{value}</strong></div>;
}
