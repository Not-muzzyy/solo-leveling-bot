import { useEffect, useMemo, useState } from 'react';
import { api } from './api/client';
import BottomNav from './components/BottomNav';
import StatePanels from './components/StatePanels';
import SystemNotice from './components/SystemNotice';
import TopBar from './components/TopBar';
import { errorMessage, getRequestId, number } from './lib/format';
import { initialGuildId, initialSection } from './lib/telegram';
import ClaimScreen from './screens/Claim';
import GuildsScreen from './screens/Guilds';
import ProfileScreen from './screens/Profile';
import ShopScreen from './screens/Shop';
import { ApiError } from './types';
import type {
  GuildSort,
  GuildSummary,
  MeResponse,
  Section,
  ShopCategory,
  ShopItem,
} from './types';

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
  const [noticeTone, setNoticeTone] = useState<'ok' | 'error'>('ok');

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

  function showNotice(message: string, tone: 'ok' | 'error') {
    setNoticeTone(tone);
    setNotice(message);
  }

  async function claimDaily() {
    if (busy || claimRemaining > 0) return;
    setBusy(true);
    setNotice('');
    try {
      const result = await api.claim();
      setMe((current) => current ? { ...current, hunter: result.hunter } : current);
      setClaimRemaining(result.hunter.claim_remaining_seconds);
      showNotice(`Ration secured · +${number(result.gold_reward)} Gold · +${number(result.xp_reward)} XP${result.leveled_up ? ` · Rank ${result.new_rank} reached` : ''}`, 'ok');
    } catch (error) {
      if (error instanceof ApiError && error.code === 'claim_cooldown' && error.remainingSeconds) {
        setClaimRemaining(error.remainingSeconds);
      }
      showNotice(errorMessage(error), 'error');
    } finally {
      setBusy(false);
    }
  }

  async function buy(item: ShopItem) {
    if (!me || busyItem) return;
    if (me.hunter.gold < item.price) {
      showNotice(`Need ${number(item.price)} Gold. Your treasury has ${number(me.hunter.gold)}.`, 'error');
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
      showNotice(`${result.item.name} acquired · −${number(result.price)} Gold`, 'ok');
    } catch (error) {
      showNotice(errorMessage(error), 'error');
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
    profile: { eyebrow: 'Hunter record', title: 'Status Window', detail: 'Your current standing in the System.' },
    claim: { eyebrow: 'Daily allocation', title: 'System Rations', detail: 'Collect your daily Gold and XP.' },
    shop: { eyebrow: 'Exchange depot', title: 'Hunter Shop', detail: 'Spend Gold on equipment and supplies.' },
    guilds: { eyebrow: 'Syndicate registry', title: 'Guild Directory', detail: 'Review guild standings and rosters.' },
  };
  const copy = sectionCopy[section];

  return (
    <main className="app-shell">
      <TopBar me={me} loading={loading} onRefresh={() => void loadSystem()} />

      <section className="section-heading">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h1>{copy.title}</h1>
          <p>{copy.detail}</p>
        </div>
        <span className="heading-mark" aria-hidden="true">◇</span>
      </section>

      {notice && <SystemNotice message={notice} tone={noticeTone} onClear={() => setNotice('')} />}

      <StatePanels loading={loading} error={pageError} hasMe={!!me} onRetry={() => void loadSystem()} />

      {me && !loading && !pageError && (
        <div className="panel-enter" key={section}>
          {section === 'profile' && (
            <ProfileScreen
              me={me}
              claimRemaining={claimRemaining}
              onOpenClaim={() => changeSection('claim')}
              onOpenGuild={() => changeSection('guilds')}
            />
          )}
          {section === 'claim' && (
            <ClaimScreen
              level={me.hunter.level}
              remaining={claimRemaining}
              busy={busy}
              onClaim={() => void claimDaily()}
            />
          )}
          {section === 'shop' && (
            <ShopScreen
              items={visibleItems}
              category={category}
              gold={me.hunter.gold}
              busyItem={busyItem}
              inventoryCount={me.inventory_count}
              onCategory={setCategory}
              onBuy={(item) => void buy(item)}
            />
          )}
          {section === 'guilds' && (
            <GuildsScreen
              guilds={guilds}
              currentGuild={me.guild}
              selectedGuild={selectedGuild}
              sort={guildSort}
              onSort={setGuildSort}
              onSelect={(guild) => void openGuild(guild)}
            />
          )}
        </div>
      )}

      <BottomNav section={section} onChange={changeSection} />
    </main>
  );
}
