// app.jsx — shell: nav, shared state, theming, tweaks
const { useState: useStateApp, useEffect: useEffectApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "dark": false,
  "accent": "#2F8F6B"
}/*EDITMODE-END*/;

const ACCENTS = ['#2F8F6B', '#1F8AA6', '#4C63D6', '#C8643B'];

function deriveTheme(base, accent, dark) {
  const panel = base.panel;
  return {
    ...base,
    accent,
    accentSoft: `color-mix(in oklab, ${accent} ${dark ? 20 : 15}%, ${panel})`,
    accentDim: `color-mix(in oklab, ${accent} ${dark ? 44 : 34}%, ${panel})`,
    good: accent,
    goodSoft: `color-mix(in oklab, ${accent} ${dark ? 20 : 15}%, ${panel})`,
  };
}

function usePersist(key, initial) {
  const [v, setV] = useStateApp(() => {
    try { const s = localStorage.getItem(key); return s ? JSON.parse(s) : initial; } catch { return initial; }
  });
  useEffectApp(() => { try { localStorage.setItem(key, JSON.stringify(v)); } catch {} }, [v]);
  return [v, setV];
}

const NAV = [
  { id: 'picker', label: 'Picker', icon: 'grid' },
  { id: 'analyze', label: 'Analyze', icon: 'scan' },
  { id: 'wallet', label: 'Wallet', icon: 'wallet' },
  { id: 'insights', label: 'Insights', icon: 'chart' },
];

function App() {
  const { useTweaks, TweaksPanel, TweakSection, TweakToggle, TweakColor, TweakButton, Icon } = window;
  const [tw, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const t = deriveTheme(window.THEMES[tw.dark ? 'dark' : 'light'], tw.accent, tw.dark);

  const [tab, setTab] = usePersist('co_tab', 'picker');
  const [balances, setBalances] = usePersist('co_balances', {});
  const [goal, setGoal] = usePersist('co_goal', null);
  const [subs, setSubs] = usePersist('co_subs', [
    { cardId: 'venx', spent: 2100, required: 4000, daysLeft: 41, reward: 75000 },
    { cardId: 'csp', done: true, reward: 60000 },
  ]);

  // Responsive layout
  const [isDesktop, setIsDesktop] = useStateApp(() => window.innerWidth >= 768);
  useEffectApp(() => {
    const handler = () => setIsDesktop(window.innerWidth >= 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);

  // Card data refresh state
  const [refreshing, setRefreshing] = useStateApp(false);
  const [refreshStatus, setRefreshStatus] = useStateApp('');
  const [lastUpdated, setLastUpdated] = useStateApp(() => {
    try { const s = localStorage.getItem('co_live_cards'); return s ? JSON.parse(s).fetchedAt : null; } catch { return null; }
  });

  useEffectApp(() => { document.body.style.background = tw.dark ? '#0c0d09' : '#e9e6dd'; }, [tw.dark]);

  function resetData() {
    setBalances({});
    setGoal(null);
    setSubs([{ cardId: 'venx', spent: 2100, required: 4000, daysLeft: 41, reward: 75000 }, { cardId: 'csp', done: true, reward: 60000 }]);
  }

  async function refreshCardData() {
    setRefreshing(true); setRefreshStatus('');
    try {
      const resp = await fetch('/api/refresh-card-data', { method: 'POST' });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      localStorage.setItem('co_live_cards', JSON.stringify(data));
      setLastUpdated(data.fetchedAt);
      setRefreshStatus('done');
      setTimeout(() => window.location.reload(), 900);
    } catch (e) {
      setRefreshStatus('error:' + (e.message || 'Failed'));
    } finally {
      setRefreshing(false);
    }
  }

  function formatUpdated(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  const titles = { picker: 'Card Picker', analyze: 'Analyzer', wallet: 'My Wallet', insights: 'Insights' };

  const openSettings = () => window.postMessage({ type: '__activate_edit_mode' }, '*');

  const settingsBtn = (
    <button onClick={openSettings}
      style={{ width: 36, height: 36, borderRadius: 999, background: t.panel, border: `1px solid ${t.line}`,
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3,
        cursor: 'pointer', flexShrink: 0 }}>
      <Icon name="dot" size={5} color={t.accent} />
      <Icon name="dot" size={5} color={t.sub} />
      <Icon name="dot" size={5} color={t.sub} />
    </button>
  );

  const tabContent = (
    <main className="content" style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
      <div style={{ maxWidth: isDesktop ? 780 : 'none', margin: isDesktop ? '0 auto' : undefined }}>
        {tab === 'picker'   && <window.PickerTab t={t} />}
        {tab === 'analyze'  && <window.AnalyzerTab t={t} balances={balances} setBalances={setBalances} />}
        {tab === 'wallet'   && <window.WalletTab t={t} balances={balances} setBalances={setBalances} goal={goal} setGoal={setGoal} />}
        {tab === 'insights' && <window.InsightsTab t={t} balances={balances} subs={subs} setSubs={setSubs} />}
      </div>
    </main>
  );

  return (
    <div className="stage" style={{ background: tw.dark ? '#0c0d09' : '#e9e6dd' }}>
      <div className="app" style={{ background: t.bg, color: t.ink, flexDirection: isDesktop ? 'row' : 'column' }}>

        {/* ── Desktop: left sidebar ── */}
        {isDesktop && (
          <aside style={{ width: 220, flexShrink: 0, background: t.panel, borderRight: `1px solid ${t.line}`,
            display: 'flex', flexDirection: 'column', padding: '20px 12px' }}>
            {/* logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 10px 24px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 9, background: t.accent, color: t.accentInk,
                display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 17, fontFamily: 'var(--num)', flexShrink: 0 }}>◆</div>
              <div style={{ fontSize: 14, fontWeight: 800, letterSpacing: -0.3, lineHeight: 1.2, color: t.ink }}>Card Optimizer</div>
            </div>
            {/* nav items */}
            {NAV.map(n => {
              const on = n.id === tab;
              return (
                <button key={n.id} onClick={() => setTab(n.id)} style={{ border: 'none', fontFamily: 'inherit',
                  background: on ? t.accentSoft : 'transparent', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 10, marginBottom: 2,
                  color: on ? t.accent : t.sub, transition: 'all .15s', textAlign: 'left', width: '100%' }}>
                  <Icon name={n.icon} size={18} sw={on ? 2.2 : 1.8} />
                  <span style={{ fontSize: 13.5, fontWeight: on ? 700 : 500 }}>{n.label}</span>
                </button>
              );
            })}
            {/* settings at bottom */}
            <div style={{ flex: 1 }} />
            <button onClick={openSettings} style={{ border: `1px solid ${t.line}`, background: 'transparent',
              borderRadius: 10, padding: '10px 12px', cursor: 'pointer', fontFamily: 'inherit',
              display: 'flex', alignItems: 'center', gap: 10, color: t.sub, width: '100%' }}>
              <Icon name="dot" size={5} color={t.sub} />
              <Icon name="dot" size={5} color={t.sub} />
              <Icon name="dot" size={5} color={t.sub} />
              <span style={{ fontSize: 13, fontWeight: 500, marginLeft: 2 }}>Settings</span>
            </button>
          </aside>
        )}

        {/* ── Main column (header + content + mobile nav) ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
          <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: isDesktop ? '16px 28px 14px' : '14px 18px 10px',
            borderBottom: `1px solid ${t.line}`, background: t.bg, flexShrink: 0 }}>
            {isDesktop ? (
              <div style={{ fontSize: 17, fontWeight: 700, letterSpacing: -0.3, color: t.ink }}>{titles[tab]}</div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: 9, background: t.accent, color: t.accentInk,
                  display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 17, fontFamily: 'var(--num)' }}>◆</div>
                <div>
                  <div style={{ fontSize: 14.5, fontWeight: 800, letterSpacing: -0.3, lineHeight: 1 }}>Card Optimizer</div>
                  <div style={{ fontSize: 10.5, color: t.sub, marginTop: 2 }}>{titles[tab]}</div>
                </div>
              </div>
            )}
            {settingsBtn}
          </header>

          {tabContent}

          {/* bottom nav — mobile only */}
          {!isDesktop && (
            <nav style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center', padding: '8px 6px',
              paddingBottom: 'max(8px, env(safe-area-inset-bottom))', background: t.panel, borderTop: `1px solid ${t.line}`, flexShrink: 0 }}>
              {NAV.map(n => {
                const on = n.id === tab;
                return (
                  <button key={n.id} onClick={() => setTab(n.id)} style={{ border: 'none', background: 'none',
                    cursor: 'pointer', fontFamily: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center',
                    gap: 3, padding: '4px 14px', color: on ? t.accent : t.faint, transition: 'color .15s' }}>
                    <Icon name={n.icon} size={22} sw={on ? 2.2 : 1.8} />
                    <span style={{ fontSize: 10, fontWeight: on ? 700 : 500 }}>{n.label}</span>
                  </button>
                );
              })}
            </nav>
          )}
        </div>
      </div>

      <TweaksPanel>
        <TweakSection label="Appearance" />
        <TweakToggle label="Dark mode" value={tw.dark} onChange={v => setTweak('dark', v)} />
        <TweakColor label="Accent" value={tw.accent} options={ACCENTS} onChange={v => setTweak('accent', v)} />
        <TweakSection label="Card Data" />
        <div style={{ fontSize: 11, color: 'rgba(41,38,27,0.5)', lineHeight: 1.45, marginBottom: 6 }}>
          {lastUpdated ? <>Live data · updated {formatUpdated(lastUpdated)}</> : <>Using built-in defaults</>}
        </div>
        {refreshStatus.startsWith('error:') && (
          <div style={{ fontSize: 11, color: '#c04b30', marginBottom: 6, lineHeight: 1.4 }}>{refreshStatus.slice(6)}</div>
        )}
        <TweakButton
          label={refreshing ? 'Fetching from Claude…' : refreshStatus === 'done' ? 'Done — reloading…' : 'Refresh from Claude'}
          onClick={refreshCardData}
        />
        <TweakSection label="Sample Data" />
        <TweakButton label="Reset to sample data" onClick={resetData} />
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
