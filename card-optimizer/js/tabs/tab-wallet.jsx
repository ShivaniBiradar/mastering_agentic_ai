// tab-wallet.jsx — My Wallet: balances, expiry, transfer optimizer, goal tracker
const { useState: useStateW } = React;

function WalletTab({ t, balances, setBalances, goal, setGoal }) {
  const { Icon, Chip, Meter, Btn, Panel, SectionHead, CardArt, Sheet, Segmented, money, fmt } = window;
  const cards = window.WALLET_CARDS;
  const [editCard, setEditCard] = useStateW(null);
  const [editGoal, setEditGoal] = useStateW(false);
  const [prog, setProg] = useStateW('csp');
  const [draft, setDraft] = useStateW('');

  const valueOf = (c) => (balances[c.id] || 0) * c.cpp / 100;
  const totalVal = cards.reduce((s, c) => s + valueOf(c), 0);
  const totalPts = cards.reduce((s, c) => s + (balances[c.id] || 0), 0);

  const goalProgram = goal.program;
  const goalPts = goalProgram === 'any' ? totalPts : (balances[goalProgram] || 0);
  const goalPct = Math.min(100, goalPts / goal.target * 100);

  const partners = window.TRANSFER_PARTNERS[prog] || [];
  const progBal = balances[prog] || 0;
  const maxCpp = Math.max(...partners.map(p => p.cpp));

  function openEdit(c) { setEditCard(c); setDraft(String(balances[c.id] || 0)); }
  function saveEdit() {
    const v = Math.max(0, parseInt(String(draft).replace(/[^\d]/g, '')) || 0);
    setBalances({ ...balances, [editCard.id]: v }); setEditCard(null);
  }

  return (
    <div style={{ padding: '4px 18px 20px' }}>
      {/* total hero */}
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 12, color: t.sub, fontWeight: 600 }}>Total point value</div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, marginTop: 2 }}>
          <span style={{ fontFamily: 'var(--num)', fontSize: 38, fontWeight: 700, color: t.ink, letterSpacing: -1 }}>
            {money(totalVal)}</span>
          <Chip t={t} tone="good" icon="up">{fmt(totalPts)} pts</Chip>
        </div>
      </div>

      {/* cards */}
      <SectionHead t={t} title="Your cards" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 18 }}>
        {cards.map(c => {
          const safe = c.expiry.state === 'safe';
          return (
            <div key={c.id} style={{ background: t.panel, border: `1px solid ${t.line}`, borderRadius: 18,
              padding: 15, boxShadow: t.shadowSm }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 13 }}>
                <CardArt card={c} t={t} w={56} h={37} r={8} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14.5, fontWeight: 700, color: t.ink, lineHeight: 1.1 }}>{c.name}</div>
                  <div style={{ fontSize: 11.5, color: t.sub, marginTop: 2 }}>{c.currency}</div>
                </div>
                <button onClick={() => openEdit(c)} style={{ border: `1px solid ${t.line}`, background: t.panel2,
                  borderRadius: 10, padding: '6px 10px', cursor: 'pointer', color: t.sub, fontFamily: 'inherit',
                  fontSize: 11.5, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Icon name="dot" size={5} color={t.accent} /> Edit</button>
              </div>
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginTop: 13 }}>
                <div>
                  {balances[c.id]
                    ? <>
                        <div style={{ fontFamily: 'var(--num)', fontSize: 23, fontWeight: 700, color: t.ink, letterSpacing: -0.5 }}>
                          {fmt(balances[c.id])}</div>
                        <div style={{ fontSize: 11, color: t.sub }}>≈ {money(valueOf(c))} · {c.cpp}¢/pt</div>
                      </>
                    : <div style={{ fontSize: 12, color: t.faint, lineHeight: 1.4 }}>
                        Tap <b style={{ color: t.sub }}>Edit</b> to enter your starting balance from the bank app — it'll grow automatically as you upload statements.
                      </div>}
                </div>
                <Chip t={t} tone={safe ? 'good' : 'warn'} icon={safe ? 'check' : 'clock'}>
                  {safe ? 'No expiry' : 'Expiring soon'}</Chip>
              </div>
            </div>
          );
        })}
      </div>

      {/* redemption goal */}
      <SectionHead t={t} title="Redemption goal" action="Edit" onAction={() => setEditGoal(true)} />
      <div style={{ background: `linear-gradient(160deg, ${t.accentSoft}, ${t.panel} 80%)`, border: `1px solid ${t.accentDim}`,
        borderRadius: 20, padding: 18, marginBottom: 18, display: 'flex', gap: 16, alignItems: 'center' }}>
        <window.Ring pct={goalPct} size={74} sw={8} t={t}>
          <span style={{ fontFamily: 'var(--num)', fontSize: 16, fontWeight: 700, color: t.accent }}>{Math.round(goalPct)}%</span>
        </window.Ring>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6 }}>
            <Icon name="target" size={15} color={t.accent} style={{ flexShrink: 0, marginTop: 2 }} />
            <span style={{ fontSize: 14.5, fontWeight: 700, color: t.ink, lineHeight: 1.25 }}>{goal.label}</span>
          </div>
          <div style={{ fontSize: 12.5, color: t.sub, marginTop: 4, lineHeight: 1.4 }}>
            <b style={{ color: t.ink }}>{fmt(goalPts)}</b> of {fmt(goal.target)} pts
            {goalPct < 100
              ? <> · {fmt(goal.target - goalPts)} to go</>
              : <> · <b style={{ color: t.good }}>Goal reached! ✦</b></>}
          </div>
          <div style={{ marginTop: 9 }}><Meter t={t} pct={goalPct} h={7} /></div>
        </div>
      </div>

      {/* transfer optimizer */}
      <SectionHead t={t} title="Transfer partner optimizer" />
      <p style={{ margin: '-4px 2px 11px', fontSize: 12, color: t.sub, lineHeight: 1.4 }}>
        Best redemption value per program. Transferring to airline & hotel partners usually beats cashing out.</p>
      <div style={{ marginBottom: 12 }}>
        <Segmented t={t} value={prog} onChange={setProg}
          options={cards.map(c => ({ value: c.id, label: c.short }))} />
      </div>
      <Panel t={t} pad={6}>
        {partners.map((p, i) => {
          const worth = progBal * p.cpp / 100;
          const isBest = i === 0;
          return (
            <div key={p.name} style={{ padding: '11px 10px', borderTop: i ? `1px solid ${t.line2}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 30, height: 30, borderRadius: 9, background: isBest ? t.accent : t.sunk,
                  color: isBest ? t.accentInk : t.sub, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                  <Icon name={p.type === 'hotel' ? 'bed' : 'plane'} size={15} /></div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: t.ink, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{p.name}</span>
                    {isBest && <Chip t={t} tone="accent">BEST</Chip>}
                  </div>
                  <div style={{ fontSize: 10.5, color: t.sub, marginTop: 1 }}>{p.ratio} · {p.sweet}</div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontFamily: 'var(--num)', fontSize: 14, fontWeight: 700, color: isBest ? t.good : t.ink }}>{p.cpp}¢</div>
                  <div style={{ fontSize: 10.5, color: t.sub }}>{money(worth)}</div>
                </div>
              </div>
              <div style={{ marginTop: 7, marginLeft: 40 }}><Meter t={t} pct={p.cpp / maxCpp * 100} h={4}
                color={isBest ? t.accent : t.accentDim} /></div>
            </div>
          );
        })}
      </Panel>

      {/* edit balance sheet */}
      <Sheet open={!!editCard} onClose={() => setEditCard(null)} t={t} title={editCard ? editCard.name : ''}>
        {editCard && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 14 }}>
              <CardArt card={editCard} t={t} w={90} h={58} r={11} />
            </div>
            <label style={{ fontSize: 12, color: t.sub, fontWeight: 600 }}>Point balance</label>
            <input autoFocus type="text" inputMode="numeric" value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && saveEdit()}
              style={{ width: '100%', marginTop: 6, padding: '13px 14px', borderRadius: 13, fontFamily: 'var(--num)',
                fontSize: 22, fontWeight: 700, color: t.ink, background: t.panel2, border: `1px solid ${t.line}`,
                outline: 'none', boxSizing: 'border-box' }} />
            <div style={{ fontSize: 12, color: t.sub, marginTop: 8 }}>
              ≈ {money((parseInt(String(draft).replace(/[^\d]/g,''))||0) * editCard.cpp / 100)} in value</div>
            <div style={{ marginTop: 18 }}><Btn t={t} full size="lg" onClick={saveEdit}>Save balance</Btn></div>
          </div>
        )}
      </Sheet>

      {/* edit goal sheet */}
      <GoalSheet open={editGoal} onClose={() => setEditGoal(false)} t={t} goal={goal} setGoal={setGoal} cards={cards} />
    </div>
  );
}

function GoalSheet({ open, onClose, t, goal, setGoal, cards }) {
  const { Sheet, Btn, Segmented } = window;
  const [d, setD] = useStateW(goal);
  React.useEffect(() => { if (open) setD(goal); }, [open]);
  const inputStyle = { width: '100%', marginTop: 6, padding: '12px 14px', borderRadius: 13, fontSize: 15,
    fontWeight: 600, color: t.ink, background: t.panel2, border: `1px solid ${t.line}`, outline: 'none',
    boxSizing: 'border-box', fontFamily: 'inherit' };
  return (
    <Sheet open={open} onClose={onClose} t={t} title="Redemption goal">
      <label style={{ fontSize: 12, color: t.sub, fontWeight: 600 }}>What are you saving for?</label>
      <input value={d.label} onChange={e => setD({ ...d, label: e.target.value })} style={inputStyle} />
      <div style={{ height: 14 }} />
      <label style={{ fontSize: 12, color: t.sub, fontWeight: 600 }}>Target points</label>
      <input type="text" inputMode="numeric" value={d.target}
        onChange={e => setD({ ...d, target: Math.max(0, parseInt(String(e.target.value).replace(/[^\d]/g,''))||0) })}
        style={{ ...inputStyle, fontFamily: 'var(--num)' }} />
      <div style={{ height: 14 }} />
      <label style={{ fontSize: 12, color: t.sub, fontWeight: 600, display: 'block', marginBottom: 6 }}>Count points from</label>
      <Segmented t={t} value={d.program} onChange={v => setD({ ...d, program: v })}
        options={[{ value: 'any', label: 'All cards' }, ...cards.map(c => ({ value: c.id, label: c.short }))]} />
      <div style={{ marginTop: 20 }}><Btn t={t} full size="lg" onClick={() => { setGoal(d); onClose(); }}>Save goal</Btn></div>
    </Sheet>
  );
}
window.WalletTab = WalletTab;
