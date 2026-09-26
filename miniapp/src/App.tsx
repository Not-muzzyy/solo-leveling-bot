import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import { initialGuildId, initialSection } from './lib/telegram';
import { ApiError } from './types';
import type {
  GuildSort,
  GuildSummary,
  MeResponse,
  Section,
  ShopCategory,
  ShopItem,
} from './types';

const CATEGORY_LABELS: Record<ShopCategory, string> = {
  weapon: 'Weapons',
  armor: 'Armor',
  accessory: 'Accessories',
  consumable: 'Consumables',
  material: 'Materials',
};

const CATEGORY_SINGULAR: Record<ShopCategory, string> = {
  weapon: 'Weapon',
  armor: 'Armor',
  accessory: 'Accessory',
  consumable: 'Consumable',
  material: 'Material',
};

const SORT_LABELS: Record<GuildSort, string> = {
  power: 'Power',
  level: 'Level',
  gold: 'Gold',
  members: 'Members',
};

function number(value: number): string {
  return new Intl.NumberFormat().format(value);
}

function countdown(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return hours > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${minutes}m ${String(secs).padStart(2, '0')}s`;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The System could not complete that request.';
}

function getRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function App() {
  const [section, setSection] = useState<Section>(initialSection);
  const launchGuildId = initialGuildId();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [shopItems, setShopItems] = useState<ShopItem[]>([]);
  const [guilds, setGuilds] = useState<GuildSummary[]>([]);
  const [guildSort, setGuildSort] = useState<GuildSort>('power');
  const [selectedGuild, setSelectedGuild] = useState<GuildSummary | null>(null);
  const [category, setCategory] = useState<ShopCategory>('weapon');
  const [claimRemaining, setClaimRemaining] = useState(0);
  const [busy, setBusy] = useState(false);
  const [busyItem, setBusyItem] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState('');
  const [notice, setNotice] = useState('');

  async function loadSystem() {
    setLoading(true);
    setPageError('');
    try {
      const [profile, catalog, directory] = await Promise.all([
        api.me(),
        api.catalog(),
        api.guilds(guildSort),
      ]);
      let startingGuild = profile.guild ?? directory.guilds[0] ?? null;
      if (launchGuildId !== null) {
        try {
          startingGuild = await api.guild(launchGuildId);
        } catch {
          // The requested guild may have changed since its Telegram link was sent.
        }
      }
      setMe(profile);
      setShopItems(catalog.items);
      setGuilds(directory.guilds);
      setClaimRemaining(profile.hunter.claim_remaining_seconds);
      setSelectedGuild(startingGuild);
    } catch (error) {
      setPageError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSystem();
    // Startup load is intentionally tied to the initial Mini App session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setClaimRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void api.guilds(guildSort).then((result) => {
      if (!cancelled) setGuilds(result.guilds);
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [guildSort]);

  const visibleItems = useMemo(
    () => shopItems.filter((item) => item.type === category),
    [shopItems, category],
  );

  async function claimDaily() {
    if (busy || claimRemaining > 0) return;
    setBusy(true);
    setNotice('');
    try {
      const result = await api.claim();
      setMe((current) => current ? { ...current, hunter: result.hunter } : current);
      setClaimRemaining(result.hunter.claim_remaining_seconds);
      setNotice(`Ration secured · +${number(result.gold_reward)} Gold · +${number(result.xp_reward)} XP${result.leveled_up ? ` · Rank ${result.new_rank} reached` : ''}`);
    } catch (error) {
      if (error instanceof ApiError && error.code === 'claim_cooldown' && error.remainingSeconds) {
        setClaimRemaining(error.remainingSeconds);
      }
      setNotice(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function buy(item: ShopItem) {
    if (!me || busyItem) return;
    if (me.hunter.gold < item.price) {
      setNotice(`Need ${number(item.price)} Gold. Your treasury has ${number(me.hunter.gold)}.`);
      return;
    }
    setBusyItem(item.key);
    setNotice('');
    try {
      const result = await api.purchase(item.key, getRequestId());
      setMe((current) => current ? {
        ...current,
        hunter: result.hunter,
        inventory_count: current.inventory_count + 1,
      } : current);
      setNotice(`${result.item.name} acquired · −${number(result.price)} Gold`);
    } catch (error) {
      setNotice(errorMessage(error));
    } finally {
      setBusyItem(null);
    }
  }

  async function openGuild(guild: GuildSummary) {
    setSelectedGuild(guild);
    try {
      const latest = await api.guild(guild.id);
      setSelectedGuild(latest);
    } catch {
      // Keep the directory summary visible if detail refresh fails.
    }
  }

  function changeSection(next: Section) {
    setSection(next);
    setNotice('');
  }

  const sectionCopy: Record<Section, { eyebrow: string; title: string; detail: string }> = {
    claim: { eyebrow: 'Daily allocation', title: 'System Rations', detail: 'Collect your daily Gold and XP.' },
    shop: { eyebrow: 'Exchange depot', title: 'Hunter Shop', detail: 'Spend Gold on equipment and supplies.' },
    guilds: { eyebrow: 'Syndicate registry', title: 'Guild Directory', detail: 'Review guild standings and rosters.' },
  };
  const copy = sectionCopy[section];

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="system-mark" aria-hidden="true">S</div>
        <div className="topbar-copy">
          <span className="micro-label">HUNTER SYSTEM</span>
          <span className="connection-state"><span className="status-dot" /> ONLINE</span>
        </div>
        <button className="icon-button refresh-button" type="button" aria-label="Refresh System data" onClick={() => void loadSystem()} disabled={loading}>
          <span aria-hidden="true">↻</span>
        </button>
      </header>

      {me && (
        <section className="hunter-strip" aria-label="Hunter status">
          <div className="hunter-identity">
            <span className="rank-seal">{me.hunter.rank.slice(0, 1)}</span>
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

      <section className="section-heading">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h1>{copy.title}</h1>
          <p>{copy.detail}</p>
        </div>
        <span className="heading-mark" aria-hidden="true">◇</span>
      </section>

      {notice && <div className="notice" role="status" aria-live="polite">{notice}</div>}

      {loading ? (
        <section className="state-panel loading-panel" aria-live="polite">
          <span className="loading-orbit" aria-hidden="true" />
          <span className="micro-label">SYNCING CHANNEL RECORDS</span>
          <p>Contacting the Hunter System…</p>
        </section>
      ) : pageError ? (
        <section className="state-panel error-panel" role="alert">
          <span className="state-icon" aria-hidden="true">!</span>
          <h2>{pageError.includes('Telegram') ? 'Open inside Telegram' : pageError.toLowerCase().includes('hunter') ? 'Hunter profile required' : 'System link unavailable'}</h2>
          <p>{pageError}</p>
          <button className="button button-secondary" type="button" onClick={() => void loadSystem()}>Retry connection</button>
        </section>
      ) : !me ? (
        <section className="state-panel error-panel" role="alert">
          <span className="state-icon" aria-hidden="true">!</span>
          <h2>Hunter profile required</h2>
          <p>Start the bot and awaken as a Hunter before opening this panel.</p>
        </section>
      ) : (
        <>
          {section === 'claim' && (
            <ClaimPanel
              level={me.hunter.level}
              remaining={claimRemaining}
              busy={busy}
              onClaim={() => void claimDaily()}
            />
          )}
          {section === 'shop' && (
            <ShopPanel
              items={visibleItems}
              category={category}
              gold={me.hunter.gold}
              busyItem={busyItem}
              onCategory={setCategory}
              onBuy={(item) => void buy(item)}
            />
          )}
          {section === 'guilds' && (
            <GuildPanel
              guilds={guilds}
              currentGuild={me.guild}
              selectedGuild={selectedGuild}
              sort={guildSort}
              onSort={setGuildSort}
              onSelect={(guild) => void openGuild(guild)}
            />
          )}
        </>
      )}

      <nav className="bottom-nav" aria-label="Hunter System sections">
        <NavButton active={section === 'claim'} icon="◈" label="Claim" onClick={() => changeSection('claim')} />
        <NavButton active={section === 'shop'} icon="⚔" label="Shop" onClick={() => changeSection('shop')} />
        <NavButton active={section === 'guilds'} icon="♜" label="Guilds" onClick={() => changeSection('guilds')} />
      </nav>
    </main>
  );
}

function NavButton({ active, icon, label, onClick }: { active: boolean; icon: string; label: string; onClick: () => void }) {
  return (
    <button className={`nav-item${active ? ' is-active' : ''}`} type="button" aria-current={active ? 'page' : undefined} onClick={onClick}>
      <span className="nav-icon" aria-hidden="true">{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function ClaimPanel({ level, remaining, busy, onClaim }: { level: number; remaining: number; busy: boolean; onClaim: () => void }) {
  const goldLow = Math.max(0, 50 + level * 10 - 10);
  const goldHigh = 50 + level * 10 + 20;
  const xpLow = Math.max(0, 30 + level * 8 - 5);
  const xpHigh = 30 + level * 8 + 15;
  const ready = remaining <= 0;

  return (
    <div className="content-stack">
      <section className={`ration-card${ready ? ' is-ready' : ''}`}>
        <div className="ration-topline">
          <span className="micro-label">SUPPLY DROP / 24H</span>
          <span className={`availability${ready ? ' available' : ''}`}><i /> {ready ? 'AVAILABLE' : 'COOLDOWN'}</span>
        </div>
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
        <button className="button button-primary claim-button" type="button" onClick={onClaim} disabled={!ready || busy} data-state={busy ? 'loading' : ready ? 'ready' : 'disabled'}>
          {busy ? <><span className="button-spinner" /> Processing allocation</> : ready ? 'Collect daily ration' : `Next ration in ${countdown(remaining)}`}
        </button>
        <p className="claim-footnote">One claim becomes available every 24 hours.</p>
      </section>
      <section className="info-row">
        <span className="info-glyph" aria-hidden="true">⌁</span>
        <p>Your cooldown is saved with your Hunter record. Reopening the app will not reset it.</p>
      </section>
    </div>
  );
}

function ShopPanel({
  items,
  category,
  gold,
  busyItem,
  onCategory,
  onBuy,
}: {
  items: ShopItem[];
  category: ShopCategory;
  gold: number;
  busyItem: string | null;
  onCategory: (category: ShopCategory) => void;
  onBuy: (item: ShopItem) => void;
}) {
  const categories = Object.keys(CATEGORY_LABELS) as ShopCategory[];
  return (
    <div className="content-stack">
      <div className="shop-toolbar">
        <span className="micro-label">AVAILABLE TREASURY</span>
        <strong><span aria-hidden="true">◈</span> {number(gold)} G</strong>
      </div>
      <div className="category-list" role="tablist" aria-label="Shop categories">
        {categories.map((entry) => (
          <button key={entry} role="tab" aria-selected={category === entry} className={`category-chip${category === entry ? ' is-selected' : ''}`} type="button" onClick={() => onCategory(entry)}>
            {CATEGORY_LABELS[entry]}
          </button>
        ))}
      </div>
      {items.length ? (
        <div className="item-list">
          {items.map((item) => <ShopCard key={item.key} item={item} gold={gold} busy={busyItem === item.key} disabled={busyItem !== null} onBuy={() => onBuy(item)} />)}
        </div>
      ) : (
        <section className="state-panel"><span className="state-icon" aria-hidden="true">◇</span><h2>Department quiet</h2><p>No exchange items are listed here yet.</p></section>
      )}
    </div>
  );
}

function ShopCard({ item, gold, busy, disabled, onBuy }: { item: ShopItem; gold: number; busy: boolean; disabled: boolean; onBuy: () => void }) {
  const stats = [
    ['ATK', item.stats.attack], ['DEF', item.stats.defense], ['HP', item.stats.hp], ['SPD', item.stats.speed],
  ].filter(([, value]) => Number(value) !== 0);
  const affordable = gold >= item.price;
  return (
    <article className={`item-card rarity-${item.rarity.toLowerCase()}`}>
      <div className="item-card-main">
        <div className="item-symbol" aria-hidden="true">{item.type === 'weapon' ? '⚔' : item.type === 'armor' ? '⬡' : item.type === 'accessory' ? '◇' : item.type === 'consumable' ? '✦' : '▧'}</div>
        <div className="item-copy">
          <span className="item-rarity">{item.rarity} · {CATEGORY_SINGULAR[item.type]}</span>
          <h3>{item.name}</h3>
          <div className="stat-list">{stats.length ? stats.map(([label, value]) => <span key={label}>{label} <b>+{number(Number(value))}</b></span>) : <span>Crafting material</span>}</div>
        </div>
      </div>
      <div className="item-card-action">
        <span className="item-price"><span aria-hidden="true">◈</span>{number(item.price)} G</span>
        <button className="button button-buy" type="button" onClick={onBuy} disabled={disabled || !affordable} data-state={busy ? 'loading' : affordable ? 'ready' : 'disabled'}>
          {busy ? <><span className="button-spinner" /> Buying</> : affordable ? 'Acquire' : 'Need more'}
        </button>
      </div>
    </article>
  );
}

function GuildPanel({
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
        <GuildDetail guild={shownGuild} isMine={currentGuild?.id === shownGuild.id} />
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

function GuildDetail({ guild, isMine }: { guild: GuildSummary; isMine: boolean }) {
  return (
    <section className="guild-card">
      <div className="guild-card-topline"><span className="micro-label">{isMine ? 'YOUR SYNDICATE' : 'GUILD RECORD'}</span><span className="guild-id">#{guild.id}</span></div>
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
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="guild-metric"><span className="micro-label">{label}</span><strong>{value}</strong></div>;
}
