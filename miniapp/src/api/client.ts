import { telegramInitData } from '../lib/telegram';
import type {
  ClaimResponse,
  GuildSort,
  GuildSummary,
  MeResponse,
  PurchaseResponse,
  ShopCatalog,
} from '../types';
import { ApiError } from '../types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_BASE) {
    throw new ApiError('Mini App API URL is not configured.', 0, 'api_not_configured');
  }

  const initData = telegramInitData();
  if (!initData) {
    throw new ApiError('Open the Hunter System from Telegram to load your profile.', 401, 'telegram_required');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': initData,
      ...init.headers,
    },
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body?.detail;
    throw new ApiError(
      typeof detail === 'string' ? detail : detail?.message || 'The System could not complete that request.',
      response.status,
      detail?.code,
      detail?.remaining_seconds,
    );
  }
  return body as T;
}

export const api = {
  me: () => request<MeResponse>('/api/v1/me'),
  claim: () => request<ClaimResponse>('/api/v1/claim', { method: 'POST', body: '{}' }),
  catalog: () => request<ShopCatalog>('/api/v1/shop/catalog'),
  purchase: (itemKey: string, requestId: string) => request<PurchaseResponse>('/api/v1/shop/purchases', {
    method: 'POST',
    body: JSON.stringify({ item_key: itemKey, request_id: requestId }),
  }),
  guilds: (sort: GuildSort) => request<{ sort: GuildSort; guilds: GuildSummary[] }>(`/api/v1/guilds?sort=${sort}`),
  guild: (guildId: number) => request<GuildSummary>(`/api/v1/guilds/${guildId}`),
};
