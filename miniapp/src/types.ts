export type Section = 'claim' | 'shop' | 'guilds';
export type ShopCategory = 'weapon' | 'armor' | 'accessory' | 'consumable' | 'material';
export type GuildSort = 'power' | 'level' | 'gold' | 'members';

export interface HunterSummary {
  display_name: string;
  rank: string;
  level: number;
  xp: number;
  xp_needed: number;
  gold: number;
  power: number;
  last_claim_time: number;
  claim_remaining_seconds: number;
  guild_id: number | null;
}

export interface ShopStats {
  attack: number;
  defense: number;
  hp: number;
  speed: number;
}

export interface ShopItem {
  key: string;
  name: string;
  type: ShopCategory;
  rarity: string;
  price: number;
  stats: ShopStats;
}

export interface GuildMember {
  display_name: string;
  role: 'owner' | 'member';
  rank: string;
  level: number;
  power: number;
}

export interface GuildSummary {
  id: number;
  name: string;
  description: string;
  owner_name: string;
  member_count: number;
  max_members: number;
  total_power: number;
  average_level: number;
  total_gold: number;
  war_score: number;
  war_wins: number;
  war_losses: number;
  xp_bonus_percent: number;
  members: GuildMember[];
}

export interface MeResponse {
  hunter: HunterSummary;
  inventory_count: number;
  guild: GuildSummary | null;
}

export interface ClaimResponse {
  gold_reward: number;
  xp_reward: number;
  leveled_up: boolean;
  new_rank: string | null;
  hunter: HunterSummary;
}

export interface ShopCatalog {
  categories: ShopCategory[];
  items: ShopItem[];
}

export interface PurchaseResponse {
  item: {
    id: number;
    name: string;
    type: ShopCategory;
    rarity: string;
    stats: ShopStats;
  };
  price: number;
  hunter: HunterSummary;
}

export class ApiError extends Error {
  code: string;
  status: number;
  remainingSeconds?: number;

  constructor(message: string, status: number, code = 'request_failed', remainingSeconds?: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.remainingSeconds = remainingSeconds;
  }
}
