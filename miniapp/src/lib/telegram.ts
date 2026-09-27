import type { Section } from '../types';

interface TelegramWebApp {
  initData: string;
  initDataUnsafe?: { start_param?: string };
  expand?: () => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

function webApp(): TelegramWebApp | undefined {
  return typeof window === 'undefined' ? undefined : window.Telegram?.WebApp;
}

export function initializeTelegram(): void {
  webApp()?.expand?.();
}

export function telegramInitData(): string {
  return webApp()?.initData ?? '';
}

const param = webApp()?.initDataUnsafe?.start_param ?? '';

// startapp carries a section name (profile/claim/shop/guilds) or a guild link
// (guild_<id>, guild-<id>, or bare digits); default profile (home status window).
const guildMatch = /^(?:guild[-_])?(\d+)$/.exec(param);

const sectionParam: Section =
  param === 'profile' || param === 'claim' || param === 'shop' || param === 'guilds'
    ? param
    : guildMatch
      ? 'guilds'
      : 'profile';

export const initialSection: Section = sectionParam;

export function initialGuildId(): number | null {
  return guildMatch ? Number(guildMatch[1]) : null;
}
