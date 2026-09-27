export function number(value: number): string {
  return new Intl.NumberFormat().format(value);
}

export function countdown(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return hours > 0 ? `${hours}h ${String(minutes).padStart(2, '0')}m` : `${minutes}m ${String(secs).padStart(2, '0')}s`;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'The System could not complete that request.';
}

export function getRequestId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
