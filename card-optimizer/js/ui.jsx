// ui.jsx — shared UI primitives (theme-driven). Exports to window.

/* ------------------------------ ICONS ------------------------------ */
function Icon({ name, size = 22, color = 'currentColor', sw = 1.8, style }) {
  const p = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: color, strokeWidth: sw, strokeLinecap: 'round', strokeLinejoin: 'round', style };
  const P = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.6"/><rect x="14" y="3" width="7" height="7" rx="1.6"/><rect x="3" y="14" width="7" height="7" rx="1.6"/><rect x="14" y="14" width="7" height="7" rx="1.6"/></>,
    scan: <><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/></>,
    wallet: <><rect x="3" y="6" width="18" height="14" rx="2.6"/><path d="M3 10.5h18"/><circle cx="17" cy="15.2" r="1.25" fill={color} stroke="none"/></>,
    chart: <><path d="M4 19V5"/><path d="M4 19h16"/><path d="M8 16v-4M12 16V8M16 16v-6"/></>,
    bell: <><path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    up: <><path d="M7 17 17 7M9 7h8v8"/></>,
    down: <><path d="M17 7 7 17M15 17H7V9"/></>,
    dining: <><path d="M6 3v8M6 11a2 2 0 0 0 2-2V3M6 11v10M18 3c-1.5 0-2.5 2-2.5 5S16.5 14 18 14m0-11v18"/></>,
    cart: <><circle cx="9" cy="20" r="1.3"/><circle cx="18" cy="20" r="1.3"/><path d="M2 3h2.2l2.2 12.4a1.6 1.6 0 0 0 1.6 1.3h8.4a1.6 1.6 0 0 0 1.6-1.3L21 7H5.4"/></>,
    plane: <><path d="M17.8 19.8 12 14l-5.8 5.8L7 16 3 13.5 21 4l-5.5 18z"/></>,
    bed: <><path d="M3 18v-6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v6"/><path d="M3 18h18M3 14h18"/><path d="M7 10V8a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2"/></>,
    car: <><path d="M5 13l1.5-4.5A2 2 0 0 1 8.4 7h7.2a2 2 0 0 1 1.9 1.5L19 13"/><path d="M5 13h14v4a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1H8v1a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1z"/><circle cx="7.5" cy="14.5" r=".6" fill={color} stroke="none"/><circle cx="16.5" cy="14.5" r=".6" fill={color} stroke="none"/></>,
    gas: <><rect x="4" y="3" width="9" height="18" rx="1.6"/><path d="M4 9h9"/><path d="M13 8l3 2v7a2 2 0 0 0 2 2 2 2 0 0 0 2-2V9l-3-3"/></>,
    play: <><rect x="3" y="4" width="18" height="14" rx="2.5"/><path d="M10 8.5v5l4-2.5z" fill={color} stroke="none"/><path d="M8 21h8"/></>,
    bag: <><path d="M6 8h12l-1 12a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"/><path d="M9 8a3 3 0 0 1 6 0"/></>,
    pill: <><rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(45 12 12)"/><path d="M8.5 8.5 15.5 15.5"/></>,
    bolt: <><path d="M13 2 4 14h6l-1 8 9-12h-6z"/></>,
    dot: <><circle cx="12" cy="12" r="3.2"/></>,
    check: <><path d="M5 12.5 10 17.5 19.5 7"/></>,
    chev: <><path d="M9 6l6 6-6 6"/></>,
    chevd: <><path d="M6 9l6 6 6-6"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    upload: <><path d="M12 16V4M7 9l5-5 5 5"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></>,
    sparkle: <><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 4v3M20.5 5.5h-3" strokeWidth={sw*0.8}/></>,
    target: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".7" fill={color} stroke="none"/></>,
    cal: <><rect x="3" y="5" width="18" height="16" rx="2.4"/><path d="M3 9.5h18M8 3v4M16 3v4"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></>,
    x: <><path d="M6 6l12 12M18 6 6 18"/></>,
    swap: <><path d="M7 4 3 8l4 4"/><path d="M3 8h13a4 4 0 0 1 0 8h-1"/><path d="M17 20l4-4-4-4" opacity="0"/></>,
    transfer: <><path d="M4 8h13l-3-3M4 8l3 3"/><path d="M20 16H7l3 3M20 16l-3-3"/></>,
    trophy: <><path d="M7 4h10v4a5 5 0 0 1-10 0z"/><path d="M7 6H4v1a3 3 0 0 0 3 3M17 6h3v1a3 3 0 0 1-3 3"/><path d="M12 13v3M9 20h6M10 20l.5-4h3l.5 4"/></>,
    clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></>,
    fire: <><path d="M12 3c.5 3-2 4-2 7a2 2 0 0 0 4 0c0-1 .8-1.5 1-2 1 1.5 2 3 2 5a5 5 0 0 1-10 0c0-4 3-6 5-10z"/></>,
    pin: <><path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z"/><circle cx="12" cy="10" r="2.4"/></>,
    file: <><path d="M7 3h7l5 5v13a0 0 0 0 1 0 0H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M14 3v5h5"/></>,
  };
  return <svg {...p}>{P[name] || P.dot}</svg>;
}

/* ------------------------------ CHIP ------------------------------- */
function Chip({ children, t, tone = 'soft', size = 'sm', icon }) {
  const map = {
    soft:   { background: t.accentSoft, color: t.accent },
    accent: { background: t.accent, color: t.accentInk },
    neutral:{ background: t.sunk, color: t.sub },
    warn:   { background: t.warnSoft, color: t.warn },
    danger: { background: t.dangerSoft, color: t.danger },
    good:   { background: t.goodSoft, color: t.good },
    outline:{ background: 'transparent', color: t.sub, boxShadow: `inset 0 0 0 1px ${t.line}` },
  };
  const sz = size === 'md' ? { fontSize: 12, padding: '4px 10px' } : { fontSize: 10.5, padding: '3px 8px' };
  return (
    <span style={{ ...map[tone], ...sz, fontWeight: 700, borderRadius: 999, whiteSpace: 'nowrap',
      display: 'inline-flex', alignItems: 'center', gap: 4, lineHeight: 1.3 }}>
      {icon && <Icon name={icon} size={sz.fontSize + 1} sw={2.1} />}{children}
    </span>
  );
}

/* ------------------------------ METER ------------------------------ */
function Meter({ pct, t, color, h = 7, track }) {
  const c = color || t.accent;
  return (
    <div style={{ height: h, background: track || t.line, borderRadius: 999, overflow: 'hidden' }}>
      <div style={{ width: Math.max(0, Math.min(100, pct)) + '%', height: '100%', background: c,
        borderRadius: 999, transition: 'width .5s cubic-bezier(.2,.7,.3,1)' }} />
    </div>
  );
}

/* --------------------------- PROGRESS RING ------------------------- */
function Ring({ pct, size = 64, sw = 7, t, color, children }) {
  const r = (size - sw) / 2, c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(100, pct)) / 100);
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={t.line} strokeWidth={sw} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color || t.accent} strokeWidth={sw}
          strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset .6s cubic-bezier(.2,.7,.3,1)' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }}>{children}</div>
    </div>
  );
}

/* ----------------------------- PANEL ------------------------------- */
function Panel({ t, children, style, pad = 16, onClick, hover }) {
  return (
    <div onClick={onClick} style={{ background: t.panel, border: `1px solid ${t.line}`,
      borderRadius: 18, padding: pad, boxShadow: t.shadowSm, ...(onClick ? { cursor: 'pointer' } : {}), ...style }}>
      {children}
    </div>
  );
}

/* --------------------------- CARD ART ------------------------------ */
function CardArt({ card, t, w = 38, h = 27, r = 6 }) {
  return (
    <div style={{ width: w, height: h, borderRadius: r, flexShrink: 0, background: t[card.art] || t.csp,
      boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.10)', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: h*0.28, left: w*0.14, width: w*0.20, height: h*0.26,
        borderRadius: 2, background: 'linear-gradient(135deg,#E9C679,#C99A42)', opacity: 0.9 }} />
    </div>
  );
}

/* --------------------------- SEGMENTED ----------------------------- */
function Segmented({ options, value, onChange, t }) {
  return (
    <div style={{ display: 'flex', gap: 4, background: t.sunk, padding: 4, borderRadius: 12, border: `1px solid ${t.line}` }}>
      {options.map(o => {
        const v = typeof o === 'string' ? o : o.value, lb = typeof o === 'string' ? o : o.label;
        const on = v === value;
        return (
          <button key={v} onClick={() => onChange(v)} style={{ flex: 1, border: 'none', cursor: 'pointer',
            background: on ? t.panel : 'transparent', color: on ? t.ink : t.sub, fontWeight: on ? 700 : 600,
            fontSize: 12.5, padding: '7px 6px', borderRadius: 9, fontFamily: 'inherit',
            boxShadow: on ? t.shadowSm : 'none', transition: 'all .15s' }}>{lb}</button>
        );
      })}
    </div>
  );
}

/* --------------------------- STAT / KV ----------------------------- */
function Stat({ label, value, sub, t, color, big }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: t.sub, fontWeight: 600 }}>{label}</div>
      <div style={{ fontFamily: 'var(--num)', fontSize: big ? 30 : 21, fontWeight: 700, color: color || t.ink,
        letterSpacing: -0.4, marginTop: 2, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && <div style={{ fontSize: 11.5, color: t.sub, marginTop: 1 }}>{sub}</div>}
    </div>
  );
}

/* --------------------------- SECTION ------------------------------- */
function SectionHead({ title, action, onAction, t }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '2px 0 10px' }}>
      <h3 style={{ margin: 0, fontSize: 14.5, fontWeight: 700, color: t.ink, letterSpacing: -0.2 }}>{title}</h3>
      {action && <button onClick={onAction} style={{ border: 'none', background: 'none', color: t.accent,
        fontWeight: 700, fontSize: 12.5, cursor: 'pointer', fontFamily: 'inherit' }}>{action}</button>}
    </div>
  );
}

/* ---------------------------- BUTTON ------------------------------- */
function Btn({ children, t, kind = 'primary', icon, onClick, full, disabled, size = 'md', style }) {
  const base = { border: 'none', cursor: disabled ? 'not-allowed' : 'pointer', fontFamily: 'inherit',
    fontWeight: 700, borderRadius: 13, display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    gap: 7, width: full ? '100%' : 'auto', opacity: disabled ? 0.5 : 1, transition: 'transform .1s, filter .15s' };
  const sz = size === 'lg' ? { fontSize: 15, padding: '14px 20px' } :
             size === 'sm' ? { fontSize: 12.5, padding: '8px 13px', borderRadius: 10 } :
             { fontSize: 13.5, padding: '11px 17px' };
  const kinds = {
    primary: { background: t.accent, color: t.accentInk },
    soft: { background: t.accentSoft, color: t.accent },
    ghost: { background: 'transparent', color: t.ink, boxShadow: `inset 0 0 0 1px ${t.line}` },
    dark: { background: t.ink, color: t.bg },
  };
  return (
    <button onClick={disabled ? undefined : onClick} style={{ ...base, ...sz, ...kinds[kind], ...style }}
      onMouseDown={e => !disabled && (e.currentTarget.style.transform = 'scale(.97)')}
      onMouseUp={e => (e.currentTarget.style.transform = '')}
      onMouseLeave={e => (e.currentTarget.style.transform = '')}>
      {icon && <Icon name={icon} size={sz.fontSize + 3} sw={2.1} />}{children}
    </button>
  );
}

/* ----------------------- BOTTOM SHEET / MODAL ---------------------- */
function Sheet({ open, onClose, t, children, title }) {
  if (!open) return null;
  return (
    <div onClick={onClose} style={{ position: 'absolute', inset: 0, zIndex: 60, display: 'flex',
      alignItems: 'flex-end', justifyContent: 'center', background: 'rgba(20,30,24,0.34)',
      backdropFilter: 'blur(2px)', animation: 'fadeIn .18s ease' }}>
      <div onClick={e => e.stopPropagation()} style={{ width: '100%', maxWidth: 520, background: t.panel,
        borderRadius: '22px 22px 0 0', maxHeight: '88%', overflow: 'auto', boxShadow: t.shadow,
        animation: 'sheetUp .26s cubic-bezier(.2,.8,.25,1)', WebkitOverflowScrolling: 'touch' }}>
        <div style={{ position: 'sticky', top: 0, background: t.panel, padding: '12px 18px 8px',
          borderBottom: title ? `1px solid ${t.line}` : 'none', zIndex: 2 }}>
          <div style={{ width: 38, height: 4, borderRadius: 99, background: t.line, margin: '0 auto 10px' }} />
          {title && <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: t.ink }}>{title}</h3>
            <button onClick={onClose} style={{ border: 'none', background: t.sunk, width: 30, height: 30,
              borderRadius: 99, cursor: 'pointer', display: 'grid', placeItems: 'center', color: t.sub }}>
              <Icon name="x" size={16} /></button>
          </div>}
        </div>
        <div style={{ padding: '14px 18px 26px' }}>{children}</div>
      </div>
    </div>
  );
}

Object.assign(window, { Icon, Chip, Meter, Ring, Panel, CardArt, Segmented, Stat, SectionHead, Btn, Sheet });
