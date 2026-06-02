// data.js — themes, card database, categories, transfer partners, helpers
// All values are factual/representative reward structures for the two real cards
// in the wallet (Chase Sapphire Preferred, Capital One Venture X) plus a small
// set of candidate cards used for spending-based recommendations.

/* ----------------------------- THEMES ----------------------------- */
const THEMES = {
  light: {
    bg: '#F4F2EB', panel: '#FFFFFF', panel2: '#FBFAF5', sunk: '#F1EFE8',
    ink: '#1B211D', sub: '#79817A', faint: '#A7AEA6', line: '#E6E8E1', line2: '#EFF0EA',
    accent: '#2F8F6B', accentInk: '#FFFFFF', accentSoft: '#E4F1EA', accentDim: '#C7E3D4',
    warn: '#B9831F', warnSoft: '#F8EED6', danger: '#C0492F', dangerSoft: '#F8E4DE',
    good: '#2F8F6B', goodSoft: '#E4F1EA',
    shadow: '0 12px 34px -20px rgba(30,55,42,0.34)', shadowSm: '0 1px 2px rgba(20,40,30,0.05)',
    csp: 'linear-gradient(150deg, #15375A 0%, #245C82 100%)',
    venx: 'linear-gradient(150deg, #23262B 0%, #41464F 100%)',
  },
  dark: {
    bg: '#13150F', panel: '#1C1F18', panel2: '#22261E', sunk: '#181B14',
    ink: '#ECEFE7', sub: '#9AA398', faint: '#69715F', line: '#2C3127', line2: '#262B22',
    accent: '#54B68C', accentInk: '#0C140F', accentSoft: '#1C3328', accentDim: '#2A4A38',
    warn: '#D7A24A', warnSoft: '#33291463', danger: '#E27A60', dangerSoft: '#3A211B66',
    good: '#54B68C', goodSoft: '#1C3328',
    shadow: '0 16px 40px -22px rgba(0,0,0,0.7)', shadowSm: '0 1px 2px rgba(0,0,0,0.3)',
    csp: 'linear-gradient(150deg, #14365A 0%, #1E4E70 100%)',
    venx: 'linear-gradient(150deg, #1B1E22 0%, #353A42 100%)',
  },
};

/* --------------------------- CATEGORIES --------------------------- */
// Canonical spend categories the analyzer maps transactions into.
const CATEGORIES = [
  { id: 'dining',      label: 'Dining & Restaurants', icon: 'dining' },
  { id: 'groceries',   label: 'Groceries',            icon: 'cart' },
  { id: 'travel',      label: 'Travel (airfare/hotel)', icon: 'plane' },
  { id: 'portal_hotel',label: 'Hotel via card portal', icon: 'bed' },
  { id: 'portal_flight',label:'Flight via card portal', icon: 'plane' },
  { id: 'transit',     label: 'Transit & Rideshare',  icon: 'car' },
  { id: 'gas',         label: 'Gas',                  icon: 'gas' },
  { id: 'streaming',   label: 'Streaming',            icon: 'play' },
  { id: 'online',      label: 'Online Shopping',      icon: 'bag' },
  { id: 'drugstore',   label: 'Drugstores',           icon: 'pill' },
  { id: 'utilities',   label: 'Bills & Utilities',    icon: 'bolt' },
  { id: 'other',       label: 'Everything else',      icon: 'dot' },
];
const CAT_LABEL = Object.fromEntries(CATEGORIES.map(c => [c.id, c.label]));

/* ----------------------------- CARDS ------------------------------ */
// cpp = cents-per-point we value the currency at (realistic transfer-weighted).
// earn = multiplier per category id; `base` applies to anything unlisted.
const WALLET_CARDS = [
  {
    id: 'csp',
    name: 'Chase Sapphire Preferred',
    issuer: 'Chase', currency: 'Ultimate Rewards', short: 'CSP',
    art: 'csp', annualFee: 95, cpp: 1.7,
    base: 1,
    earn: { portal_flight: 5, portal_hotel: 5, travel: 2, dining: 3, streaming: 3, online_grocery: 3 },
    earnNote: { dining: '3x dining', portal_flight: '5x via Chase Travel', portal_hotel: '5x via Chase Travel', travel: '2x all travel', streaming: '3x streaming' },
    perksValue: [
      { label: '$50 annual hotel credit (Chase Travel)', value: 50 },
      { label: '10% anniversary points bonus', value: 60 },
    ],
    expiry: { state: 'safe', text: 'No expiry while account is open' },
  },
  {
    id: 'venx',
    name: 'Capital One Venture X',
    issuer: 'Capital One', currency: 'Capital One Miles', short: 'Venture X',
    art: 'venx', annualFee: 395, cpp: 1.85,
    base: 2,
    earn: { portal_hotel: 10, portal_flight: 5 },
    earnNote: { portal_hotel: '10x hotels via portal', portal_flight: '5x flights via portal', other: '2x everything' },
    perksValue: [
      { label: '$300 annual travel credit', value: 300 },
      { label: '10,000 anniversary miles', value: 185 },
      { label: 'Priority Pass + Capital One Lounges', value: 0 },
    ],
    expiry: { state: 'safe', text: 'No expiry while account is open' },
  },
];

// Candidate cards for spending-pattern recommendations (real cards).
const CANDIDATE_CARDS = [
  { id: 'amexgold', name: 'American Express Gold', annualFee: 325, creditOffset: 240, cpp: 1.9,
    base: 1, earn: { dining: 4, groceries: 4 },
    pitch: 'on dining & grocery spend', highlight: ['dining', 'groceries'] },
  { id: 'bcp', name: 'Blue Cash Preferred', annualFee: 95, creditOffset: 84, cpp: 1,
    base: 1, earn: { groceries: 6, streaming: 6, transit: 3, gas: 3 }, isCashback: true,
    pitch: 'on groceries, streaming & gas', highlight: ['groceries', 'streaming', 'gas'] },
  { id: 'savor', name: 'Capital One Savor', annualFee: 0, creditOffset: 0, cpp: 1,
    base: 1, earn: { dining: 3, groceries: 3, streaming: 3, online: 3 }, isCashback: true,
    pitch: 'on no-fee dining + grocery cashback', highlight: ['dining', 'groceries'] },
  { id: 'doublecash', name: 'Citi Double Cash', annualFee: 0, creditOffset: 0, cpp: 1,
    base: 2, earn: {}, isCashback: true,
    pitch: 'as a flat 2% on everything, no fee', highlight: ['other'] },
  { id: 'cfu', name: 'Chase Freedom Unlimited', annualFee: 0, creditOffset: 0, cpp: 1.7,
    base: 1.5, earn: { dining: 3, drugstore: 3, portal_flight: 5, portal_hotel: 5 },
    pitch: 'pairing with your CSP to boost everyday spend', highlight: ['dining', 'other'] },
  { id: 'custom', name: 'Citi Custom Cash', annualFee: 0, creditOffset: 0, cpp: 1,
    base: 1, earn: { dining: 5, groceries: 5, gas: 5, transit: 5 }, isCashback: true, customTop: true,
    pitch: 'auto-earning 5% on your top category each cycle', highlight: ['gas', 'transit'] },
];

/* ----------------------- TRANSFER PARTNERS ------------------------ */
// cpp = typical redemption value (cents per point). ratio is points : partner.
const TRANSFER_PARTNERS = {
  csp: [
    { name: 'World of Hyatt', type: 'hotel', ratio: '1:1', cpp: 2.3, sweet: 'Top value — luxury hotels for few points' },
    { name: 'Air Canada Aeroplan', type: 'air', ratio: '1:1', cpp: 1.5, sweet: 'Great Star Alliance routing' },
    { name: 'United MileagePlus', type: 'air', ratio: '1:1', cpp: 1.4, sweet: 'Wide domestic + Excursionist perk' },
    { name: 'Virgin Atlantic', type: 'air', ratio: '1:1', cpp: 1.45, sweet: 'ANA first class sweet spot' },
    { name: 'British Airways Avios', type: 'air', ratio: '1:1', cpp: 1.4, sweet: 'Cheap short-haul flights' },
    { name: 'Air France/KLM Flying Blue', type: 'air', ratio: '1:1', cpp: 1.3, sweet: 'Monthly Promo Rewards' },
    { name: 'Southwest Rapid Rewards', type: 'air', ratio: '1:1', cpp: 1.4, sweet: 'No change fees, free bags' },
    { name: 'Marriott Bonvoy', type: 'hotel', ratio: '1:1', cpp: 0.8, sweet: 'Lowest value — avoid' },
  ],
  venx: [
    { name: 'Turkish Miles&Smiles', type: 'air', ratio: '1:1', cpp: 1.8, sweet: 'United domestic for 10k miles' },
    { name: 'Air Canada Aeroplan', type: 'air', ratio: '1:1', cpp: 1.5, sweet: 'Great Star Alliance routing' },
    { name: 'Avianca LifeMiles', type: 'air', ratio: '1:1', cpp: 1.5, sweet: 'No fuel surcharges' },
    { name: 'Virgin Red', type: 'air', ratio: '1:1', cpp: 1.45, sweet: 'ANA / Delta sweet spots' },
    { name: 'British Airways Avios', type: 'air', ratio: '1:1', cpp: 1.4, sweet: 'Cheap short-haul flights' },
    { name: 'Air France/KLM Flying Blue', type: 'air', ratio: '1:1', cpp: 1.3, sweet: 'Monthly Promo Rewards' },
    { name: 'Emirates Skywards', type: 'air', ratio: '1:1', cpp: 1.2, sweet: 'Premium cabins to Dubai' },
    { name: 'Wyndham Rewards', type: 'hotel', ratio: '1:1', cpp: 1.1, sweet: 'Flat 7.5k–30k/night' },
  ],
};

/* --------------------------- HELPERS ------------------------------ */
function fmt(n) { return Math.round(n).toLocaleString('en-US'); }
function money(n, dp = 0) {
  return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: dp, maximumFractionDigits: dp });
}
// multiplier a card earns for a given category
function multiplierFor(card, catId) {
  if (card.earn && card.earn[catId] != null) return card.earn[catId];
  return card.base != null ? card.base : 1;
}
// effective return % for a category on a card = multiplier * cpp
function returnPctFor(card, catId) {
  return multiplierFor(card, catId) * card.cpp;
}

Object.assign(window, {
  THEMES, CATEGORIES, CAT_LABEL, WALLET_CARDS, CANDIDATE_CARDS,
  TRANSFER_PARTNERS, fmt, money, multiplierFor, returnPctFor,
});

// Override hardcoded defaults with live data fetched from Claude (stored in localStorage).
// UI-only fields (art, expiry) are always kept from the hardcoded defaults.
(function applyLiveCardData() {
  try {
    const raw = localStorage.getItem('co_live_cards');
    if (!raw) return;
    const live = JSON.parse(raw);
    if (live.cards && Array.isArray(live.cards)) {
      window.WALLET_CARDS = live.cards.map(liveCard => {
        const def = WALLET_CARDS.find(c => c.id === liveCard.id) || {};
        return { ...def, ...liveCard, art: def.art, expiry: def.expiry };
      });
    }
    if (live.transferPartners && typeof live.transferPartners === 'object') {
      window.TRANSFER_PARTNERS = { ...TRANSFER_PARTNERS, ...live.transferPartners };
    }
  } catch (e) {
    console.warn('Could not apply live card data:', e);
  }
})();
