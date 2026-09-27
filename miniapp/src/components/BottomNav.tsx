import type { Section } from '../types';

const NAV_ITEMS: { section: Section; icon: string; label: string }[] = [
  { section: 'profile', icon: '▤', label: 'Status' },
  { section: 'claim', icon: '◈', label: 'Claim' },
  { section: 'shop', icon: '⚔', label: 'Shop' },
  { section: 'guilds', icon: '♜', label: 'Guilds' },
];

export default function BottomNav({
  section,
  onChange,
}: {
  section: Section;
  onChange: (section: Section) => void;
}) {
  return (
    <nav className="bottom-nav" aria-label="Hunter System sections">
      {NAV_ITEMS.map((item) => (
        <button
          key={item.section}
          className={`nav-item${section === item.section ? ' is-active' : ''}`}
          type="button"
          aria-current={section === item.section ? 'page' : undefined}
          onClick={() => onChange(item.section)}
        >
          <span className="nav-icon" aria-hidden="true">{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
