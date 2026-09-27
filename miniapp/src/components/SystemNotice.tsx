import { useEffect, useRef } from 'react';

export default function SystemNotice({
  message,
  tone = 'ok',
  onClear,
}: {
  message: string;
  tone?: 'ok' | 'error';
  onClear: () => void;
}) {
  // Keep the latest callback without restarting the dismiss timer every render.
  const clearRef = useRef(onClear);
  clearRef.current = onClear;

  useEffect(() => {
    const timer = window.setTimeout(() => clearRef.current(), 2500);
    return () => window.clearTimeout(timer);
  }, [message]);

  return (
    <div className={`sys-notice${tone === 'error' ? ' is-error' : ''}`} role="status" aria-live="polite">
      {message}
    </div>
  );
}
