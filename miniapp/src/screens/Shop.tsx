import SystemPanel from '../components/SystemPanel';
import { number } from '../lib/format';
import type { ShopCategory, ShopItem } from '../types';

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

export default function ShopScreen({
  items,
  category,
  gold,
  busyItem,
  inventoryCount,
  onCategory,
  onBuy,
}: {
  items: ShopItem[];
  category: ShopCategory;
  gold: number;
  busyItem: string | null;
  inventoryCount: number;
  onCategory: (category: ShopCategory) => void;
  onBuy: (item: ShopItem) => void;
}) {
  const categories = Object.keys(CATEGORY_LABELS) as ShopCategory[];

  return (
    <SystemPanel title="Exchange Depot" suffix="헌터협회 상점" meta={`${inventoryCount} OWNED`}>
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
    </SystemPanel>
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
