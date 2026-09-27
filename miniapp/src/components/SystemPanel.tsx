import type { ReactNode } from 'react';

export default function SystemPanel({
  title,
  suffix,
  meta,
  children,
  className,
}: {
  title: string;
  suffix?: string;
  meta?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`hud-frame scanlines${className ? ` ${className}` : ''}`}>
      <header className="sys-header">
        <span className="sys-header-title">
          {title}
          {suffix ? <> <span className="sys-header-suffix">// {suffix}</span></> : null}
        </span>
        {meta ? <span className="sys-header-meta">{meta}</span> : null}
      </header>
      <div className="sys-body">{children}</div>
    </section>
  );
}
