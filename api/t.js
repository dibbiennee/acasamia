// Raccolta anonima: riceve da /index e /en/ le visite, i clic sui contatti e le sezioni raggiunte.
// Risponde sempre 204 (anche se non salva) per non rallentare ne' rompere la pagina.

const { redis, adesso, indirizzo, crypto } = require('./_lib.js');

const EVENTI = new Set(['telefono', 'whatsapp', 'indicazioni', 'indicazioni-apple', 'recensione', 'glovo', 'instagram', 'facebook', 'lingua', 'cue', 'orari']);
const SEZIONI = new Set(['giornata', 'servizi', 'recensioni', 'negozio', 'galleria', 'dove']);
const POSIZIONI = new Set(['barra', 'header', 'footer', 'hero', 'altro', ...SEZIONI]);
const SCORRI = new Set(['giornata', 'recensioni']);
const BOT = /bot|crawl|spider|slurp|headless|lighthouse|pagespeed|preview|facebookexternalhit|whatsapp|curl|wget|python|node-fetch|axios|go-http|java\//i;
const TTL = 60 * 60 * 24 * 400;

function ospitiAmmessi() {
  return (process.env.ANALYTICS_HOSTS || 'acasamia.satoshiweb.it,acasamiacivitavecchia.it,www.acasamiacivitavecchia.it')
    .split(',').map((s) => s.trim().toLowerCase()).filter(Boolean);
}

function ospite(req) {
  const o = req.headers.origin || req.headers.referer || '';
  try { return new URL(o).hostname.toLowerCase(); } catch (e) { return ''; }
}

function categoria(host) {
  if (!host) return 'diretto';
  const h = host.replace(/^www\./, '');
  if (ospitiAmmessi().includes(host) || ospitiAmmessi().includes(h)) return 'interno';
  if (/(^|\.)(google|bing|duckduckgo|ecosia|yahoo|yandex|brave|qwant)\./.test(h)) return h.startsWith('maps.') ? 'mappe' : 'ricerca';
  if (/(^|\.)(instagram|facebook|fb|tiktok|t\.co|linkedin|pinterest|reddit)\b/.test(h) || h === 'l.instagram.com' || h === 'lm.facebook.com') return 'social';
  if (/maps|waze|apple\.com/.test(h)) return 'mappe';
  if (/whatsapp|wa\.me/.test(h)) return 'whatsapp';
  if (/glovo/.test(h)) return 'glovo';
  if (/tripadvisor|thefork|yelp/.test(h)) return 'recensioni';
  return 'altro';
}

function corpo(req) {
  let b = req.body;
  if (Buffer.isBuffer(b)) b = b.toString('utf8');
  if (typeof b === 'string') { if (b.length > 4000) return null; try { b = JSON.parse(b); } catch (e) { return null; } }
  return b && typeof b === 'object' ? b : null;
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  const fine = () => res.status(204).end();
  try {
    if (req.method !== 'POST') return fine();
    if (BOT.test(req.headers['user-agent'] || '')) return fine();
    if (!ospitiAmmessi().includes(ospite(req))) return fine();
    const b = corpo(req);
    if (!b || !Array.isArray(b.e) || b.e.length === 0 || b.e.length > 12) return fine();

    const lingua = b.l === 'en' ? 'en' : 'it';
    const w = Number(b.w) || 0;
    const disp = w && w < 768 ? 'mobile' : w && w < 1100 ? 'tablet' : 'desktop';
    const { giorno, ora } = adesso();
    const s = 's:' + giorno;
    const cmd = [];
    const inc = (campo) => cmd.push(['HINCRBY', s, campo, 1]);

    for (const x of b.e) {
      if (!x || typeof x !== 'object') continue;
      if (x.t === 'pv') {
        const ref = categoria(String(x.r || '').toLowerCase().slice(0, 60));
        inc('pv'); inc('lang:' + lingua); inc('dev:' + disp); inc('h:' + ora);
        if (ref !== 'interno') inc('ref:' + ref);
        const utm = String(x.u || '').replace(/[^a-z0-9_-]/g, '').slice(0, 20);
        if (utm) inc('utm:' + utm);
        // visitatori unici del giorno: codice che cambia ogni giorno, mai salvato
        const sale = (process.env.ANALYTICS_SALT || 'acasamia') + ':' + giorno;
        const codice = crypto.createHash('sha256').update(sale + '|' + indirizzo(req) + '|' + (req.headers['user-agent'] || '')).digest('hex');
        cmd.push(['PFADD', 'u:' + giorno, codice]);
        cmd.push(['EXPIRE', 'u:' + giorno, TTL]);
      } else if (x.t === 'c' && EVENTI.has(x.n)) {
        const pos = POSIZIONI.has(x.p) ? x.p : 'altro';
        inc('ev:' + x.n); inc('evp:' + x.n + ':' + pos); inc('evo:' + x.n + ':' + (x.o ? 'aperto' : 'chiuso')); inc('evl:' + x.n + ':' + lingua); inc('evh:' + ora);
      } else if (x.t === 's' && SEZIONI.has(x.n)) {
        inc('sez:' + x.n);
      } else if (x.t === 'w' && SCORRI.has(x.n)) {
        inc('sw:' + x.n);
      }
    }
    if (cmd.length) {
      cmd.push(['EXPIRE', s, TTL]);
      await redis(cmd);
    }
  } catch (e) {
    // mai far fallire la pagina per colpa delle statistiche
  }
  return fine();
};
