// Funzioni condivise per le statistiche anonime di A casa mia.
// Nessun cookie, nessun indirizzo IP salvato: l'IP serve solo a calcolare,
// al momento, un codice che cambia ogni giorno e finisce in un contatore
// (HyperLogLog) da cui non si puo' risalire a nessuno.

const crypto = require('crypto');

// ---------- archivio (Upstash Redis via REST: si collega da Vercel > Storage) ----------
function archivio() {
  const url = process.env.ANALYTICS_STORE_URL || process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.ANALYTICS_STORE_TOKEN || process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN;
  return url && token ? { url: url.replace(/\/$/, ''), token } : null;
}

async function redis(comandi) {
  const a = archivio();
  if (!a) return null;
  const r = await fetch(a.url + '/pipeline', {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + a.token, 'Content-Type': 'application/json' },
    body: JSON.stringify(comandi),
  });
  if (!r.ok) throw new Error('archivio ' + r.status);
  const out = await r.json();
  return out.map((x) => (x && x.error ? null : x ? x.result : null));
}

// ---------- giorno e ora, sempre a Roma ----------
function adesso(d = new Date()) {
  const p = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Rome', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hour12: false,
  }).formatToParts(d);
  const o = {};
  p.forEach((x) => { o[x.type] = x.value; });
  return { giorno: `${o.year}-${o.month}-${o.day}`, ora: String(parseInt(o.hour, 10) % 24).padStart(2, '0') };
}

function giorniIndietro(n) {
  const out = [];
  for (let i = n - 1; i >= 0; i--) out.push(adesso(new Date(Date.now() - i * 86400000)).giorno);
  return out;
}

// ---------- indirizzo ----------
function indirizzo(req) {
  const inoltrato = String(req.headers['x-forwarded-for'] || '').split(',')[0].trim();
  return inoltrato || req.headers['x-real-ip'] || 'ignoto';
}

// ---------- blocco dei tentativi sulla password (5 errori, poi 10 minuti) ----------
const TENTATIVI_MAX = 5;
const FINESTRA = Number(process.env.AUTH_LOCK_WINDOW || 600) * 1000;
const tentativi = new Map();
const scaduto = (v) => !v || Date.now() - v.da > FINESTRA;

function bloccato(req) {
  const ip = indirizzo(req);
  const v = tentativi.get(ip);
  if (scaduto(v)) { tentativi.delete(ip); return false; }
  return v.n >= TENTATIVI_MAX;
}
function attesaResidua(req) {
  const v = tentativi.get(indirizzo(req));
  return scaduto(v) ? 0 : Math.ceil((FINESTRA - (Date.now() - v.da)) / 1000);
}
function confronta(a, b) {
  const x = crypto.createHash('sha256').update(String(a)).digest();
  const y = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
}
// Va usata da OGNI endpoint che accetta la password. Durante il blocco
// fallisce anche la password giusta, ed e' voluto.
function authed(req) {
  const tok = (req.headers.authorization || '').replace(/^Bearer\s+/i, '').trim();
  const atteso = process.env.PANNELLO_PASSWORD;
  const ip = indirizzo(req);
  if (bloccato(req)) return false;
  const ok = !!tok && !!atteso && confronta(tok, atteso);
  if (ok) { tentativi.delete(ip); return true; }
  const v = tentativi.get(ip);
  if (scaduto(v)) tentativi.set(ip, { n: 1, da: Date.now() });
  else v.n += 1;
  return false;
}

module.exports = { archivio, redis, adesso, giorniIndietro, indirizzo, bloccato, attesaResidua, authed, crypto };
