// tab-analyzer.jsx — Statement Analyzer: dynamic per-card upload, real gap computation
const { useState: useStateAn, useRef: useRefAn } = React;

const SAMPLE_MAP = {
  csp:  () => window.SAMPLE_CHASE_CSV,
  venx: () => window.SAMPLE_CAPITALONE_CSV,
};

function UploadZone({ card, data, onZoneClick, t }) {
  return (
    <div onClick={() => onZoneClick(card.id)}
      style={{ cursor: 'pointer', borderRadius: 16, overflow: 'hidden',
        border: `1px solid ${data ? t.accentDim : t.line}`, boxShadow: t.shadowSm }}>
      <div style={{ background: t[card.art], padding: '10px 12px 8px' }}>
        <div style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.65)', letterSpacing: 0.4 }}>
          {card.issuer.toUpperCase()}
        </div>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: '#fff', lineHeight: 1.2, marginTop: 1 }}>
          {card.short}
        </div>
      </div>
      <div style={{ background: data ? t.accentSoft : t.panel, padding: '12px 10px', textAlign: 'center' }}>
        {data ? (
          <>
            <window.Icon name="check" size={18} color={t.accent} />
            <div style={{ fontSize: 11, fontWeight: 700, color: t.accent, marginTop: 4 }}>
              {data.txns.length} charges
            </div>
            <div style={{ fontSize: 10, color: t.sub, marginTop: 2, overflow: 'hidden',
              textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {data.fileName}
            </div>
          </>
        ) : (
          <>
            <window.Icon name="upload" size={18} color={t.faint} />
            <div style={{ fontSize: 11, fontWeight: 600, color: t.sub, marginTop: 4 }}>Tap to upload</div>
            <div style={{ fontSize: 10, color: t.faint, marginTop: 1 }}>CSV statement</div>
          </>
        )}
      </div>
    </div>
  );
}

function AnalyzerTab({ t, balances, setBalances }) {
  const { Icon, Chip, Meter, Btn, Panel, SectionHead, money, fmt, CAT_LABEL, CATEGORIES } = window;
  const cards = window.WALLET_CARDS;

  // keyed by card.id — grows automatically as cards are added to WALLET_CARDS
  const [fileData, setFileData] = useStateAn({});
  const [phase,  setPhase]  = useStateAn('idle');
  const [step,   setStep]   = useStateAn('');
  const [result, setResult] = useStateAn(null);
  const [err,    setErr]    = useStateAn('');
  const [walletUpdate, setWalletUpdate] = useStateAn(null); // { csp: +3200, venx: +1800 }

  // single file input shared across all zones; track which card it's for via ref
  const fileInputRef  = useRefAn(null);
  const activeCardRef = useRefAn(null);

  const catMeta = Object.fromEntries(CATEGORIES.map(c => [c.id, c]));

  function loadFile(text, fileName) {
    const rows = window.parseCSV(text);
    const txns = window.extractTransactions(rows);
    return { txns, fileName };
  }

  function onZoneClick(cardId) {
    activeCardRef.current = cardId;
    fileInputRef.current && fileInputRef.current.click();
  }

  function onFileChange(e) {
    const f = e.target.files && e.target.files[0];
    const cardId = activeCardRef.current;
    if (!f || !cardId) return;
    const reader = new FileReader();
    reader.onload = () => {
      const data = loadFile(String(reader.result), f.name);
      setFileData(prev => ({ ...prev, [cardId]: data }));
    };
    reader.readAsText(f);
    e.target.value = '';
  }

  async function run(dataOverride) {
    const data = dataOverride || fileData;
    setPhase('working'); setErr(''); setResult(null); setWalletUpdate(null);
    try {
      const allTxns = cards.flatMap(card =>
        (data[card.id]?.txns || []).map(tx => ({ ...tx, usedCard: card }))
      );
      if (!allTxns.length) {
        setErr("Couldn't find any transactions. Make sure the CSV has description and amount columns.");
        setPhase('error'); return;
      }
      setStep(`Categorizing ${allTxns.length} transactions with AI…`);
      const catMap = await window.categorizeMerchants(allTxns.map(x => x.desc));
      setStep('Crunching the numbers…');
      await new Promise(r => setTimeout(r, 150));
      const analysis = window.analyze(allTxns, catMap, cards);

      // Compute points earned per card and accumulate into wallet balance
      const earned = {};
      cards.forEach(card => {
        if (!data[card.id]) return; // only cards that had a CSV uploaded
        const pts = analysis.enriched
          .filter(tx => tx.used && tx.used.id === card.id)
          .reduce((sum, tx) => sum + tx.amount * tx.usedMult, 0);
        if (pts > 0) earned[card.id] = Math.round(pts);
      });
      if (Object.keys(earned).length > 0) {
        setBalances(prev => {
          const next = { ...prev };
          Object.entries(earned).forEach(([id, pts]) => { next[id] = (next[id] || 0) + pts; });
          return next;
        });
        setWalletUpdate(earned);
      }

      setResult(analysis); setPhase('done');
    } catch (e) {
      setErr('Something went wrong. ' + (e && e.message ? e.message : ''));
      setPhase('error');
    }
  }

  function reset() { setPhase('idle'); setResult(null); setErr(''); setFileData({}); }

  const uploadedCount = Object.keys(fileData).length;
  const totalTxns = Object.values(fileData).reduce((s, d) => s + d.txns.length, 0);
  const hasSample = cards.some(c => SAMPLE_MAP[c.id]);

  /* ---- IDLE / UPLOAD ---- */
  if (phase === 'idle' || phase === 'error') {
    return (
      <div style={{ padding: '4px 18px 20px' }}>
        <div style={{ marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 22, fontWeight: 700, letterSpacing: -0.5, color: t.ink }}>Statement Analyzer</h2>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: t.sub }}>
            Upload statements for any of your cards. The app knows which card you used per charge and shows exactly where you left points on the table.
          </p>
        </div>

        {/* shared hidden file input */}
        <input ref={fileInputRef} type="file" accept=".csv,text/csv"
          onChange={onFileChange} style={{ display: 'none' }} />

        {/* one zone per card — auto-fills as cards are added to WALLET_CARDS */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
          gap: 10, marginBottom: 14 }}>
          {cards.map(card => (
            <UploadZone key={card.id} card={card} data={fileData[card.id]}
              onZoneClick={onZoneClick} t={t} />
          ))}
        </div>

        {uploadedCount > 0 && (
          <Btn t={t} kind="primary" full icon="sparkle" style={{ marginBottom: 12 }}
            onClick={() => run()}>
            Analyze {totalTxns} charge{totalTxns !== 1 ? 's' : ''}
          </Btn>
        )}

        {phase === 'error' && (
          <div style={{ marginBottom: 12, background: t.dangerSoft, border: `1px solid ${t.danger}33`,
            borderRadius: 14, padding: 13, fontSize: 12.5, color: t.danger, display: 'flex', gap: 8 }}>
            <Icon name="info" size={16} style={{ flexShrink: 0 }} /><span>{err}</span>
          </div>
        )}

        {hasSample && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '4px 2px 12px' }}>
              <div style={{ flex: 1, height: 1, background: t.line }} />
              <span style={{ fontSize: 11, color: t.faint, fontWeight: 600 }}>or try sample data</span>
              <div style={{ flex: 1, height: 1, background: t.line }} />
            </div>
            <Btn t={t} kind="ghost" full icon="sparkle" onClick={() => {
              const sampleData = {};
              cards.forEach(card => {
                const getSample = SAMPLE_MAP[card.id];
                if (getSample) sampleData[card.id] = loadFile(getSample(), `sample-${card.id}.csv`);
              });
              setFileData(sampleData);
              run(sampleData);
            }}>
              Try with sample data
            </Btn>
          </>
        )}

        <div style={{ marginTop: 16, fontSize: 11.5, color: t.faint, lineHeight: 1.5, display: 'flex', gap: 7 }}>
          <Icon name="info" size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Files are read in your browser. Merchant names are sent to AI for categorization. Nothing is stored.</span>
        </div>
      </div>
    );
  }

  /* ---- WORKING ---- */
  if (phase === 'working') {
    const loadedNames = cards.filter(c => fileData[c.id]).map(c => c.short).join(' + ');
    return (
      <div style={{ padding: '60px 28px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="spin" style={{ width: 46, height: 46, borderRadius: 99, border: `3px solid ${t.line}`,
          borderTopColor: t.accent, marginBottom: 18 }} />
        <div style={{ fontSize: 15, fontWeight: 700, color: t.ink }}>{step}</div>
        <div style={{ fontSize: 12.5, color: t.sub, marginTop: 5 }}>{loadedNames}</div>
      </div>
    );
  }

  /* ---- RESULTS ---- */
  const r = result;
  const maxCat = Math.max(...r.cats.map(c => c.amount));
  const topRec = r.recs[0];
  const hasRealGap = r.missedValue >= 0.50;
  const annualMissed = r.missedValue * r.annualFactor;

  return (
    <div style={{ padding: '4px 18px 20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20, fontWeight: 700, letterSpacing: -0.4, color: t.ink }}>Your statements</h2>
          <div style={{ fontSize: 12, color: t.sub, marginTop: 2 }}>{r.enriched.length} charges · {money(r.total)}</div>
        </div>
        <Btn t={t} kind="ghost" size="sm" icon="upload" onClick={reset}>New</Btn>
      </div>

      {/* wallet update confirmation */}
      {walletUpdate && (
        <div style={{ background: t.goodSoft, border: `1px solid ${t.accent}33`, borderRadius: 14,
          padding: '11px 14px', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Icon name="wallet" size={16} color={t.good} style={{ flexShrink: 0 }} />
          <div style={{ fontSize: 12.5, color: t.ink, lineHeight: 1.4 }}>
            <b style={{ color: t.good }}>Wallet updated</b> —{' '}
            {cards.filter(c => walletUpdate[c.id]).map((c, i, arr) => (
              <span key={c.id}>
                <b>+{fmt(walletUpdate[c.id])}</b> {c.short} pts
                {i < arr.length - 1 ? ', ' : ''}
              </span>
            ))} added to your running total.
          </div>
        </div>
      )}

      {/* actual vs optimal hero */}
      <div style={{ background: t.ink, color: t.bg, borderRadius: 20, padding: 20,
        boxShadow: t.shadow, marginBottom: 14, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', right: -20, top: -20, opacity: 0.08 }}>
          <Icon name="sparkle" size={130} sw={1} color={t.accent} />
        </div>
        <div style={{ display: 'flex', marginBottom: 14 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, opacity: 0.6, fontWeight: 600 }}>You earned</div>
            <div style={{ fontFamily: 'var(--num)', fontSize: 32, fontWeight: 700, color: '#fff', letterSpacing: -1, marginTop: 2 }}>
              {money(r.actualValue, 2)}</div>
            <div style={{ fontSize: 11.5, opacity: 0.6, marginTop: 1 }}>{fmt(Math.round(r.actualPts))} pts</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', opacity: 0.35 }}>
            <Icon name="arrow" size={18} color="#fff" />
          </div>
          <div style={{ flex: 1, textAlign: 'right' }}>
            <div style={{ fontSize: 11, opacity: 0.6, fontWeight: 600 }}>Best possible</div>
            <div style={{ fontFamily: 'var(--num)', fontSize: 32, fontWeight: 700, color: t.accent, letterSpacing: -1, marginTop: 2 }}>
              {money(r.optValue, 2)}</div>
            <div style={{ fontSize: 11.5, opacity: 0.6, marginTop: 1 }}>{fmt(Math.round(r.optPts))} pts</div>
          </div>
        </div>
        <div style={{ paddingTop: 14, borderTop: '1px solid rgba(255,255,255,0.12)',
          display: 'flex', alignItems: 'center', gap: 9 }}>
          <Icon name={hasRealGap ? 'info' : 'check'} size={16} color={t.accent} style={{ flexShrink: 0 }} />
          <div style={{ fontSize: 12, opacity: 0.85, lineHeight: 1.45 }}>
            {hasRealGap
              ? <><b style={{ color: '#fff' }}>{money(r.missedValue, 2)}</b> left on the table this month
                  {' '}(~<b style={{ color: '#fff' }}>{money(annualMissed, 0)}/yr</b>).{' '}
                  {r.suboptimalCount} charge{r.suboptimalCount !== 1 ? 's' : ''} used a suboptimal card.</>
              : <>You're near-optimal with these cards. The bigger win is the card below.</>}
          </div>
        </div>
      </div>

      {/* per-category breakdown */}
      <SectionHead t={t} title="Where your money went" />
      <Panel t={t} pad={6} style={{ marginBottom: 16 }}>
        {r.cats.map((c, i) => {
          const m = catMeta[c.cat] || { label: c.cat, icon: 'dot' };
          const isOptimal = c.missedValue < 0.01;
          return (
            <div key={c.cat} style={{ padding: '10px 10px', borderTop: i ? `1px solid ${t.line2}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
                <div style={{ width: 34, height: 34, borderRadius: 10, flexShrink: 0,
                  background: isOptimal ? t.goodSoft : t.warnSoft,
                  color: isOptimal ? t.good : t.warn,
                  display: 'grid', placeItems: 'center' }}>
                  <Icon name={m.icon} size={18} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: t.ink }}>{m.label.split(' (')[0]}</div>
                  <div style={{ fontSize: 11, color: t.sub, marginTop: 1 }}>
                    Best: <b style={{ color: t.ink }}>{c.best.short}</b> {window.multiplierFor(c.best, c.cat)}×
                    {!isOptimal && (
                      <span style={{ color: t.warn, fontWeight: 600 }}>
                        {' '}· used {c.dominantUsed.short} {window.multiplierFor(c.dominantUsed, c.cat)}×
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ fontFamily: 'var(--num)', fontSize: 14, fontWeight: 700, color: t.ink }}>
                    {money(c.amount)}
                  </div>
                  {isOptimal
                    ? <div style={{ fontSize: 10.5, color: t.good, fontWeight: 600 }}>✓ optimal</div>
                    : <div style={{ fontSize: 10.5, color: t.warn, fontWeight: 600 }}>−{money(c.missedValue, 2)} missed</div>}
                </div>
              </div>
              <div style={{ marginTop: 7, marginLeft: 45 }}>
                <Meter t={t} pct={c.amount / maxCat * 100} h={5}
                  color={isOptimal ? t.accent : t.warn} />
              </div>
            </div>
          );
        })}
      </Panel>

      {/* new-card recommendation */}
      {topRec && topRec.annualNet > 0 && (
        <>
          <SectionHead t={t} title="Based on how you spend" />
          <div style={{ background: `linear-gradient(160deg, ${t.accentSoft}, ${t.panel} 75%)`,
            border: `1px solid ${t.accentDim}`, borderRadius: 20, padding: 18, boxShadow: t.shadowSm }}>
            <div style={{ display: 'flex', gap: 13, alignItems: 'center' }}>
              <div style={{ width: 50, height: 50, borderRadius: 14, background: t.accent, color: t.accentInk,
                display: 'grid', placeItems: 'center', flexShrink: 0 }}>
                <Icon name="sparkle" size={24} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: t.accent, fontWeight: 700, letterSpacing: 0.3 }}>RECOMMENDED CARD</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: t.ink, lineHeight: 1.15, marginTop: 1 }}>
                  {topRec.card.name}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 13, color: t.ink, lineHeight: 1.45, margin: '13px 0' }}>
              You'd earn an extra <b style={{ color: t.good }}>{money(topRec.annualExtra)}/yr</b> {topRec.card.pitch}.{' '}
              {topRec.card.annualFee === 0
                ? <>No annual fee — that's <b style={{ color: t.good }}>+{money(topRec.annualNet)}</b> net.</>
                : topRec.card.creditOffset
                ? <>Its {money(topRec.card.annualFee)} fee drops to ~{money(topRec.effFee)} after credits — about <b style={{ color: t.good }}>+{money(topRec.annualNet)}</b> net.</>
                : <>Even after the {money(topRec.card.annualFee)} fee, that's <b style={{ color: t.good }}>+{money(topRec.annualNet)}</b> net.</>}
            </div>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}>
              {(topRec.card.highlight || []).map(h => (
                <Chip key={h} t={t} tone="soft">{(CAT_LABEL[h] || h).split(' (')[0]}</Chip>
              ))}
              <Chip t={t} tone="neutral">
                {topRec.card.annualFee ? money(topRec.card.annualFee) + '/yr' : 'No annual fee'}
              </Chip>
            </div>
          </div>
          {r.recs[1] && r.recs[1].annualNet > 0 && (
            <div style={{ fontSize: 12, color: t.sub, marginTop: 11, padding: '0 4px', lineHeight: 1.4 }}>
              Runner-up: <b style={{ color: t.ink }}>{r.recs[1].card.name}</b> (+{money(r.recs[1].annualNet)}/yr net).
            </div>
          )}
        </>
      )}
    </div>
  );
}
window.AnalyzerTab = AnalyzerTab;