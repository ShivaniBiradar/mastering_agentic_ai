// tab-insights.jsx — Insights: annual fee ROI, sign-up bonus tracker, rotating categories
const { useState: useStateI } = React;

function InsightsTab({ t, balances, subs, setSubs }) {
  const { Icon, Chip, Meter, Btn, Panel, SectionHead, CardArt, Sheet, Ring, money, fmt } = window;
  const cards = window.WALLET_CARDS;
  const [editSub, setEditSub] = useStateI(null);
  const [draft, setDraft] = useStateI('');

  function openSub(s) { setEditSub(s); setDraft(String(s.spent)); }
  function saveSub() {
    const v = Math.max(0, parseInt(String(draft).replace(/[^\d]/g, '')) || 0);
    setSubs(subs.map(s => s.cardId === editSub.cardId ? { ...s, spent: v } : s));
    setEditSub(null);
  }

  return (
    <div style={{ padding: '4px 18px 20px' }}>
      <div style={{ marginBottom: 14 }}>
        <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: -0.5, color: t.ink }}>Insights</h2>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: t.sub }}>Are your cards earning their keep?</p>
      </div>

      {/* ---------- ANNUAL FEE ROI ---------- */}
      <SectionHead t={t} title="Annual fee ROI" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 11, marginBottom: 20 }}>
        {cards.map(c => {
          const credits = (c.perksValue || []).reduce((s, p) => s + p.value, 0);
          const cover = c.annualFee ? Math.min(160, credits / c.annualFee * 100) : 100;
          const net = credits - c.annualFee;
          const paysOff = net >= 0;
          return (
            <div key={c.id} style={{ background: t.panel, border: `1px solid ${t.line}`, borderRadius: 18, padding: 16, boxShadow: t.shadowSm }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 13 }}>
                <CardArt card={c} t={t} w={46} h={30} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: t.ink, lineHeight: 1.1 }}>{c.name}</div>
                  <div style={{ fontSize: 11.5, color: t.sub, marginTop: 2 }}>{money(c.annualFee)} annual fee</div>
                </div>
                <Chip t={t} tone={paysOff ? 'good' : 'warn'} size="md" icon={paysOff ? 'check' : 'info'}>
                  {paysOff ? 'Pays for itself' : 'Use your credits'}</Chip>
              </div>
              {/* fee coverage bar */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, fontSize: 11, color: t.sub, marginBottom: 5 }}>
                <span style={{ flex: 1, minWidth: 0 }}>Credits &amp; perks offset</span>
                <span style={{ fontWeight: 700, color: paysOff ? t.good : t.ink, whiteSpace: 'nowrap', flexShrink: 0 }}>
                  {money(credits)} of {money(c.annualFee)}</span>
              </div>
              <Meter t={t} pct={cover} h={8} color={paysOff ? t.good : t.warn} />
              <div style={{ marginTop: 11, display: 'flex', flexDirection: 'column', gap: 5 }}>
                {(c.perksValue || []).map(p => (
                  <div key={p.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, fontSize: 12 }}>
                    <span style={{ color: t.sub, display: 'flex', alignItems: 'flex-start', gap: 6, flex: 1, minWidth: 0, lineHeight: 1.35 }}>
                      <Icon name="check" size={13} color={t.accent} style={{ flexShrink: 0, marginTop: 1 }} />{p.label}</span>
                    <span style={{ color: t.ink, fontWeight: 600, fontFamily: 'var(--num)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                      {p.value ? money(p.value) : '—'}</span>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: `1px solid ${t.line2}`, display: 'flex',
                justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 12.5, color: t.sub, fontWeight: 600 }}>Net before rewards</span>
                <span style={{ fontFamily: 'var(--num)', fontSize: 18, fontWeight: 700, color: paysOff ? t.good : t.danger }}>
                  {net >= 0 ? '+' : '−'}{money(Math.abs(net))}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ---------- SIGN-UP BONUS TRACKER ---------- */}
      <SectionHead t={t} title="Sign-up bonus tracker" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 11, marginBottom: 20 }}>
        {subs.map(s => {
          const c = cards.find(x => x.id === s.cardId);
          if (s.done) {
            return (
              <div key={s.cardId} style={{ background: t.goodSoft, border: `1px solid ${t.accent}33`, borderRadius: 18,
                padding: 15, display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: 12, background: t.accent, color: t.accentInk,
                  display: 'grid', placeItems: 'center', flexShrink: 0 }}><Icon name="trophy" size={20} /></div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 700, color: t.ink }}>{c.name}</div>
                  <div style={{ fontSize: 12, color: t.good, fontWeight: 600, marginTop: 1 }}>Bonus earned — {fmt(s.reward)} pts ✦</div>
                </div>
              </div>
            );
          }
          const pct = Math.min(100, s.spent / s.required * 100);
          const remaining = Math.max(0, s.required - s.spent);
          const perDay = s.daysLeft > 0 ? remaining / s.daysLeft : remaining;
          const onTrack = perDay <= (s.required / 90) * 1.15;
          return (
            <div key={s.cardId} style={{ background: t.panel, border: `1px solid ${t.line}`, borderRadius: 18, padding: 16, boxShadow: t.shadowSm }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 13 }}>
                <CardArt card={c} t={t} w={46} h={30} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: t.ink, lineHeight: 1.1 }}>{c.name}</div>
                  <div style={{ fontSize: 11.5, color: t.sub, marginTop: 2 }}>Earn {fmt(s.reward)} pts bonus</div>
                </div>
                <button onClick={() => openSub(s)} style={{ border: `1px solid ${t.line}`, background: t.panel2,
                  borderRadius: 10, padding: '6px 11px', cursor: 'pointer', color: t.sub, fontFamily: 'inherit',
                  fontSize: 11.5, fontWeight: 600 }}>Log spend</button>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 10, marginBottom: 6 }}>
                <span style={{ fontFamily: 'var(--num)', fontSize: 18, fontWeight: 700, color: t.ink, whiteSpace: 'nowrap' }}>
                  {money(s.spent)} <span style={{ fontSize: 13, color: t.sub, fontWeight: 600 }}>/ {money(s.required)}</span></span>
                <Chip t={t} tone={onTrack ? 'good' : 'warn'} icon={onTrack ? 'check' : 'clock'}>
                  {onTrack ? 'On track' : 'Pick up pace'}</Chip>
              </div>
              <Meter t={t} pct={pct} h={9} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 9, gap: 10, fontSize: 12, color: t.sub }}>
                <span style={{ whiteSpace: 'nowrap' }}>{money(remaining)} to go</span>
                <span style={{ textAlign: 'right' }}><b style={{ color: t.ink }}>{s.daysLeft}</b> days left · ~{money(perDay)}/day</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* ---------- ROTATING CATEGORIES ---------- */}
      <SectionHead t={t} title="Rotating 5% categories" />
      <div style={{ background: t.panel, border: `1px dashed ${t.line}`, borderRadius: 18, padding: 18 }}>
        <div style={{ display: 'flex', gap: 11, alignItems: 'flex-start' }}>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: t.sunk, color: t.faint,
            display: 'grid', placeItems: 'center', flexShrink: 0 }}><Icon name="cal" size={20} /></div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13.5, fontWeight: 700, color: t.ink }}>No rotating-category cards in your wallet</div>
            <div style={{ fontSize: 12.5, color: t.sub, marginTop: 3, lineHeight: 1.45 }}>
              Neither the Sapphire Preferred nor Venture X has quarterly 5% categories. Cards like the Chase Freedom Flex
              or Discover it rotate categories you'd activate each quarter.</div>
          </div>
        </div>
        <div style={{ marginTop: 14, background: t.sunk, borderRadius: 12, padding: 12 }}>
          <div style={{ fontSize: 11, color: t.faint, fontWeight: 700, letterSpacing: 0.4, marginBottom: 8 }}>
            THIS QUARTER · APR–JUN 2026 (if you had one)</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['Grocery stores', 'Gas stations', 'Streaming'].map(x => (
              <span key={x} style={{ fontSize: 12, fontWeight: 600, color: t.sub, background: t.panel,
                border: `1px solid ${t.line}`, borderRadius: 999, padding: '5px 11px', opacity: 0.8 }}>{x}</span>
            ))}
          </div>
        </div>
      </div>

      {/* edit SUB sheet */}
      <Sheet open={!!editSub} onClose={() => setEditSub(null)} t={t}
        title={editSub ? cards.find(c => c.id === editSub.cardId).name : ''}>
        {editSub && (
          <div>
            <label style={{ fontSize: 12, color: t.sub, fontWeight: 600 }}>Spend so far toward bonus</label>
            <input autoFocus type="text" inputMode="numeric" value={draft}
              onChange={e => setDraft(e.target.value)} onKeyDown={e => e.key === 'Enter' && saveSub()}
              style={{ width: '100%', marginTop: 6, padding: '13px 14px', borderRadius: 13, fontFamily: 'var(--num)',
                fontSize: 22, fontWeight: 700, color: t.ink, background: t.panel2, border: `1px solid ${t.line}`,
                outline: 'none', boxSizing: 'border-box' }} />
            <div style={{ fontSize: 12, color: t.sub, marginTop: 8 }}>
              Goal: {money(editSub.required)} in the first 3 months</div>
            <div style={{ marginTop: 18 }}><Btn t={t} full size="lg" onClick={saveSub}>Save progress</Btn></div>
          </div>
        )}
      </Sheet>
    </div>
  );
}
window.InsightsTab = InsightsTab;
