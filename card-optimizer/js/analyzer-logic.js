// analyzer-logic.js — CSV parsing, AI categorization, and points math for the Statement Analyzer

/* --------------------------- CSV PARSING --------------------------- */
function parseCSV(text) {
  const rows = [];
  let i = 0, field = '', row = [], inQ = false;
  while (i < text.length) {
    const ch = text[i];
    if (inQ) {
      if (ch === '"') { if (text[i+1] === '"') { field += '"'; i++; } else inQ = false; }
      else field += ch;
    } else {
      if (ch === '"') inQ = true;
      else if (ch === ',') { row.push(field); field = ''; }
      else if (ch === '\n' || ch === '\r') {
        if (ch === '\r' && text[i+1] === '\n') i++;
        row.push(field); rows.push(row); row = []; field = '';
      } else field += ch;
    }
    i++;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows.filter(r => r.some(c => c && c.trim() !== ''));
}

// Identify date / description / amount columns and return clean transactions.
function extractTransactions(rows) {
  if (!rows.length) return [];
  const looksHeader = rows[0].some(c => /date|desc|merchant|amount|debit|credit|name|category|transaction/i.test(c));
  const header = looksHeader ? rows[0].map(c => c.toLowerCase().trim()) : null;
  const body = looksHeader ? rows.slice(1) : rows;

  const findCol = (re) => header ? header.findIndex(h => re.test(h)) : -1;
  // Anchor desc regex to start so "transaction date" doesn't match before "description"
  let descCol = findCol(/^desc|^merchant|^name|^payee/);
  let amtCol  = findCol(/amount|debit|charge|spent/);
  let dateCol = findCol(/date|posted/);

  const sample = body.slice(0, 25);
  const isNum = (v) => v != null && v !== '' && !isNaN(parseFloat(String(v).replace(/[$,()]/g, '')));
  if (amtCol < 0) {
    const cols = body[0] ? body[0].length : 0;
    for (let c = cols - 1; c >= 0; c--) {
      if (sample.filter(r => isNum(r[c])).length > sample.length * 0.6) { amtCol = c; break; }
    }
  }
  if (descCol < 0) {
    let bestLen = -1, cols = body[0] ? body[0].length : 0;
    for (let c = 0; c < cols; c++) {
      if (c === amtCol) continue;
      const numFrac = sample.filter(r => isNum(r[c])).length / Math.max(1, sample.length);
      if (numFrac > 0.5) continue;
      const len = sample.reduce((s, r) => s + (r[c] ? r[c].length : 0), 0);
      if (len > bestLen) { bestLen = len; descCol = c; }
    }
  }
  if (dateCol < 0) dateCol = 0;

  const num = (v) => parseFloat(String(v || '').replace(/[$,()]/g, '')) || 0;
  const skip = /payment|thank you|autopay|auto pay|balance|interest charge|cash back redemption|statement credit/i;
  const out = [];
  for (const r of body) {
    const descRaw = (r[descCol] || '').trim();
    if (!descRaw || skip.test(descRaw)) continue;
    let amt = Math.abs(num(r[amtCol]));
    if (!amt) continue;
    out.push({ date: (r[dateCol] || '').trim(), desc: descRaw, amount: amt });
  }
  return out;
}

// Clean a merchant string for display + grouping
function cleanMerchant(s) {
  return s.replace(/\s+#?\d{2,}.*$/, '').replace(/\s{2,}/g, ' ')
    .replace(/\b(inc|llc|co|corp)\b\.?/gi, '').replace(/[*#].*$/, '').trim() || s.trim();
}

/* ----------------------- AI CATEGORIZATION ------------------------ */
const CAT_IDS = ['dining','groceries','travel','transit','gas','streaming','online','drugstore','utilities','other'];

async function categorizeMerchants(merchants) {
  const uniq = [...new Set(merchants.map(cleanMerchant))];
  const result = {};
  const chunk = 45;
  for (let i = 0; i < uniq.length; i += chunk) {
    const batch = uniq.slice(i, i + chunk);
    const prompt =
`Categorize each credit-card merchant into exactly one category id from this list:
dining (restaurants, cafes, fast food, bars, food delivery),
groceries (supermarkets, grocery stores),
travel (airlines, hotels, car rental, cruises, booking sites),
transit (rideshare, taxi, transit, parking, tolls),
gas (gas stations, fuel),
streaming (streaming/music/video subscriptions),
online (general online retail, electronics, marketplaces),
drugstore (pharmacies, drugstores),
utilities (phone, internet, electric, insurance, recurring bills),
other (anything else).

Return ONLY a JSON array, no prose, like [{"m":"<merchant>","c":"<id>"}].
Merchants:
${batch.map(m => '- ' + m).join('\n')}`;
    let txt = '';
    try {
      const resp = await fetch('/api/claude', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: [{ role: 'user', content: prompt }] }),
      });
      if (resp.ok) txt = await resp.text();
    } catch (e) { txt = ''; }
    const parsed = safeJsonArray(txt);
    for (const o of parsed) {
      if (o && o.m && CAT_IDS.includes(o.c)) result[o.m.trim().toLowerCase()] = o.c;
    }
    for (const m of batch) {
      const k = m.trim().toLowerCase();
      if (!result[k]) result[k] = heuristicCat(m);
    }
  }
  return result;
}

function safeJsonArray(txt) {
  if (!txt) return [];
  let s = txt.trim().replace(/^```(json)?/i, '').replace(/```$/, '').trim();
  const a = s.indexOf('['), b = s.lastIndexOf(']');
  if (a >= 0 && b > a) s = s.slice(a, b + 1);
  try { const v = JSON.parse(s); return Array.isArray(v) ? v : []; } catch { return []; }
}

// keyword fallback so the app still works without an API key
function heuristicCat(m) {
  const s = m.toLowerCase();
  const test = (re) => re.test(s);
  if (test(/coffee|cafe|restaurant|grill|pizza|burger|taco|sushi|chipotle|starbucks|mcdonald|doordash|grubhub|uber eats|dunkin|panera|sweetgreen|cheesecake|bar |kitchen|bistro|diner|wings|bbq|shake shack|nobu|joe's/)) return 'dining';
  if (test(/whole foods|trader joe|safeway|kroger|aldi|wegmans|publix|grocery|market|costco|sam's|sprouts|food lion|h-e-b|heb|ralphs|albertsons/)) return 'groceries';
  if (test(/air|airline|delta|united|american air|jetblue|southwest|hotel|marriott|hilton|hyatt|airbnb|expedia|booking|hertz|avis|enterprise|rental|cruise|resort|inn|lodge|capital one travel|chase travel/)) return 'travel';
  if (test(/uber|lyft|transit|metro|parking|toll|taxi|cab|bart|mta|caltrain/)) return 'transit';
  if (test(/shell|exxon|chevron|bp |mobil|gas|fuel|arco|valero|76 |speedway|texaco|sunoco/)) return 'gas';
  if (test(/netflix|spotify|hulu|disney|hbo|max|youtube|prime video|apple music|paramount|peacock|audible/)) return 'streaming';
  if (test(/amazon|ebay|etsy|best buy|apple\.com|walmart\.com|target\.com|newegg|wayfair|home depot|target/)) return 'online';
  if (test(/cvs|walgreens|rite aid|pharmacy|drug/)) return 'drugstore';
  if (test(/comcast|xfinity|at&t|verizon|t-mobile|pg&e|electric|water|insurance|geico|state farm|internet|utility|wireless/)) return 'utilities';
  return 'other';
}

/* --------------------------- POINTS MATH --------------------------- */
// txns must have { date, desc, amount, usedCard } where usedCard is a WALLET_CARDS entry.
function analyze(txns, catMap, cards) {
  const { multiplierFor, returnPctFor } = window;

  const enriched = txns.map(tx => {
    const cat = catMap[cleanMerchant(tx.desc).trim().toLowerCase()] || heuristicCat(tx.desc);
    // best possible card for this category
    let best = cards[0], bestRet = -1;
    cards.forEach(c => { const r = returnPctFor(c, cat); if (r > bestRet) { bestRet = r; best = c; } });
    // card actually used (tagged from the source file)
    const used = tx.usedCard || best;
    const usedMult = multiplierFor(used, cat);
    const usedRet = returnPctFor(used, cat);
    const missedPer = Math.max(0, tx.amount * (bestRet - usedRet) / 100);
    return { ...tx, cat, best, bestMult: multiplierFor(best, cat), bestRet, used, usedMult, usedRet, missedPer };
  });

  const total = enriched.reduce((s, t) => s + t.amount, 0);
  const everyday = [...cards].sort((a, b) => (b.base * b.cpp) - (a.base * a.cpp))[0];

  let optValue = 0, optPts = 0, actualValue = 0, actualPts = 0;
  enriched.forEach(t => {
    optValue   += t.amount * t.bestRet / 100;
    optPts     += t.amount * t.bestMult;
    actualValue += t.amount * t.usedRet / 100;
    actualPts   += t.amount * t.usedMult;
  });
  const missedValue = Math.max(0, optValue - actualValue);
  const suboptimalCount = enriched.filter(t => t.missedPer > 0.01).length;

  // per-category breakdown with actual vs optimal
  const byCat = {};
  enriched.forEach(t => {
    if (!byCat[t.cat]) byCat[t.cat] = {
      cat: t.cat, amount: 0, count: 0, best: t.best,
      optValue: 0, actualValue: 0, missedValue: 0,
    };
    byCat[t.cat].amount      += t.amount;
    byCat[t.cat].count++;
    byCat[t.cat].optValue    += t.amount * t.bestRet / 100;
    byCat[t.cat].actualValue += t.amount * t.usedRet / 100;
    byCat[t.cat].missedValue += t.missedPer;
    // keep track of whichever card appeared most in this category
    byCat[t.cat][`_amt_${t.used.id}`] = (byCat[t.cat][`_amt_${t.used.id}`] || 0) + t.amount;
  });
  // resolve dominant "used" card per category for display
  const cats = Object.values(byCat).sort((a, b) => b.amount - a.amount).map(c => {
    let dominantId = null, maxAmt = -1;
    window.WALLET_CARDS.forEach(card => {
      const a = c[`_amt_${card.id}`] || 0;
      if (a > maxAmt) { maxAmt = a; dominantId = card.id; }
    });
    c.dominantUsed = window.WALLET_CARDS.find(card => card.id === dominantId) || c.best;
    return c;
  });

  // spending-pattern recommendation
  const annualFactor = 12;
  const recs = window.CANDIDATE_CARDS.map(cand => {
    let extra = 0;
    enriched.forEach(t => {
      const candRet = returnPctFor(cand, t.cat);
      if (candRet > t.bestRet) extra += t.amount * (candRet - t.bestRet) / 100;
    });
    const annualExtra = extra * annualFactor;
    const effFee = Math.max(0, cand.annualFee - (cand.creditOffset || 0));
    return { card: cand, annualNet: annualExtra - effFee, annualExtra, effFee };
  }).sort((a, b) => b.annualNet - a.annualNet);

  return { enriched, total, optValue, optPts, actualValue, actualPts, missedValue, suboptimalCount, cats, recs, annualFactor, everyday };
}

Object.assign(window, { parseCSV, extractTransactions, cleanMerchant, categorizeMerchants, analyze, heuristicCat });