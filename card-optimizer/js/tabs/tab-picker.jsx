// tab-picker.jsx — Card Picker: category -> ranked recommendations from your wallet
const { useState } = React;

function PickerTab({ t }) {
  const [cat, setCat] = useState('dining');
  const C = window.CATEGORIES, cards = window.WALLET_CARDS;
  const { returnPctFor, multiplierFor, money, CANDIDATE_CARDS, Icon, Chip, Meter, CardArt, Btn } = window;

  // rank wallet cards for the selected category
  const ranked = [...cards].map(c => ({
    card: c, mult: multiplierFor(c, cat), ret: returnPctFor(c, cat),
  })).sort((a, b) => b.ret - a.ret);
  const best = ranked[0];
  const isGap = best.ret < 3.2; // no card earns a strong bonus here

  // best candidate that beats the wallet for this category (for the gap nudge)
  const candPick = [...CANDIDATE_CARDS]
    .map(c => ({ card: c, ret: returnPctFor(c, cat) }))
    .filter(x => x.ret > best.ret + 0.4)
    .sort((a, b) => b.ret - a.ret)[0];

  const spend = 100;
  return (
    <div style={{ padding: '4px 18px 20px' }}>
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: -0.5, color: t.ink }}>What are you buying?</h2>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: t.sub }}>Tap a category for the best card to swipe.</p>
      </div>

      {/* category grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 9, marginBottom: 18 }}>
        {C.map(c => {
          const on = c.id === cat;
          return (
            <button key={c.id} onClick={() => setCat(c.id)} style={{ cursor: 'pointer', fontFamily: 'inherit',
              border: `1px solid ${on ? 'transparent' : t.line}`, background: on ? t.accent : t.panel,
              color: on ? t.accentInk : t.ink, borderRadius: 14, padding: '12px 6px 9px',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
              boxShadow: on ? t.shadow : t.shadowSm, transition: 'all .15s' }}>
              <Icon name={c.icon} size={22} sw={1.9} />
              <span style={{ fontSize: 10.5, fontWeight: 600, lineHeight: 1.15, textAlign: 'center' }}>
                {c.label.split(' (')[0]}</span>
            </button>
          );
        })}
      </div>

      {/* winner */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 9 }}>
        <Chip t={t} tone="accent" icon="check">BEST FOR {window.CAT_LABEL[cat].toUpperCase().split(' (')[0]}</Chip>
      </div>

      <div style={{ background: t.panel, border: `1px solid ${t.line}`, borderRadius: 20, overflow: 'hidden', boxShadow: t.shadow }}>
        {/* hero best card */}
        <div style={{ padding: 18, display: 'flex', gap: 14, alignItems: 'center',
          background: `linear-gradient(160deg, ${t.accentSoft}, ${t.panel} 70%)` }}>
          <div style={{ position: 'relative' }}>
            <CardArt card={best.card} t={t} w={66} h={44} r={9} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 15.5, fontWeight: 700, color: t.ink, lineHeight: 1.15 }}>{best.card.name}</div>
            <div style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>{best.card.currency}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontFamily: 'var(--num)', fontSize: 26, fontWeight: 700, color: t.accent, letterSpacing: -0.5 }}>
              {best.mult % 1 === 0 ? best.mult : best.mult.toFixed(1)}×</div>
            <div style={{ fontSize: 11, color: t.sub, fontWeight: 600 }}>{best.ret.toFixed(1)}% back</div>
          </div>
        </div>
        {/* example */}
        <div style={{ display: 'flex', borderTop: `1px solid ${t.line}` }}>
          <div style={{ flex: 1, padding: '11px 16px', borderRight: `1px solid ${t.line}` }}>
            <div style={{ fontSize: 10.5, color: t.sub, fontWeight: 600 }}>On {money(spend)} spend</div>
            <div style={{ fontFamily: 'var(--num)', fontSize: 16, fontWeight: 700, color: t.ink, marginTop: 1 }}>
              {window.fmt(spend * best.mult)} pts</div>
          </div>
          <div style={{ flex: 1, padding: '11px 16px' }}>
            <div style={{ fontSize: 10.5, color: t.sub, fontWeight: 600 }}>≈ value</div>
            <div style={{ fontFamily: 'var(--num)', fontSize: 16, fontWeight: 700, color: t.good, marginTop: 1 }}>
              {money(spend * best.ret / 100, 2)}</div>
          </div>
        </div>
      </div>

      {/* runner up */}
      {ranked.length > 1 && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11.5, color: t.sub, fontWeight: 600, margin: '6px 2px' }}>Also in your wallet</div>
          {ranked.slice(1).map(r => (
            <div key={r.card.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px',
              background: t.panel, border: `1px solid ${t.line}`, borderRadius: 14, marginBottom: 8 }}>
              <CardArt card={r.card} t={t} w={40} h={27} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: t.ink }}>{r.card.name}</div>
                <div style={{ fontSize: 11, color: t.sub }}>{r.ret.toFixed(1)}% back</div>
              </div>
              <div style={{ fontFamily: 'var(--num)', fontSize: 17, fontWeight: 700, color: t.sub }}>
                {r.mult % 1 === 0 ? r.mult : r.mult.toFixed(1)}×</div>
            </div>
          ))}
        </div>
      )}

      {/* gap nudge */}
      {isGap && candPick && (
        <div style={{ marginTop: 12, background: t.warnSoft, border: `1px solid ${t.warn}33`, borderRadius: 16, padding: 15 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 6 }}>
            <Icon name="sparkle" size={17} color={t.warn} />
            <span style={{ fontSize: 12.5, fontWeight: 700, color: t.warn }}>Coverage gap</span>
          </div>
          <div style={{ fontSize: 13, color: t.ink, lineHeight: 1.4 }}>
            Your best card earns just <b>{best.ret.toFixed(1)}%</b> here. The <b>{candPick.card.name}</b> would
            earn <b>{candPick.ret.toFixed(1)}%</b> {candPick.card.pitch ? '— ' + candPick.card.pitch : ''}.
          </div>
        </div>
      )}
    </div>
  );
}
window.PickerTab = PickerTab;
