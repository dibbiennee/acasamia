// Test dell'analytics proprietario e del pannello. Nessuna rete, nessun segreto reale:
// l'archivio e' finto (fetch sostituito) e la password e' di prova.
// Esecuzione: node tests/privacy/api.test.js
const assert = require('assert');
process.env.PANNELLO_PASSWORD = 'password-solo-per-test';
process.env.ANALYTICS_STORE_URL = 'http://archivio-finto.invalid';
process.env.ANALYTICS_STORE_TOKEN = 'token-finto';

let comandi = [];
global.fetch = async (url, opt) => {
  const cmd = JSON.parse(opt.body);
  comandi.push(...cmd);
  return { ok: true, json: async () => cmd.map(() => ({ result: [] })) };
};

const t = require('../../api/t.js');
const stats = require('../../api/stats.js');

function res() {
  const r = { code: 0, headers: {}, body: null };
  r.setHeader = (k, v) => { r.headers[k.toLowerCase()] = v; };
  r.status = (c) => { r.code = c; return r; };
  r.json = (b) => { r.body = b; return r; };
  r.end = () => r;
  return r;
}
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Version/17.5 Mobile/15E148 Safari/604.1';
const H = { origin: 'https://acasamiacivitavecchia.it', 'user-agent': UA, 'x-forwarded-for': '203.0.113.77' };
async function invia(body, headers = {}) {
  comandi = [];
  const r = res();
  await t({ method: 'POST', headers: { ...H, ...headers }, body: typeof body === 'string' ? body : JSON.stringify(body) }, r);
  assert.strictEqual(r.code, 204, 'risponde sempre 204');
  return comandi.filter((c) => c[0] === 'HINCRBY').map((c) => c[2]);
}
const prove = [];
const prova = (nome, fn) => prove.push([nome, fn]);

prova('visita normale: conta pv, lingua, apparecchio, ora, stato aperto', async () => {
  const c = await invia({ l: 'it', w: 390, e: [{ t: 'pv', r: 'www.google.com', u: 'instagram', o: 1 }] });
  assert(c.includes('pv') && c.includes('lang:it') && c.includes('dev:mobile') && c.includes('ref:ricerca') && c.includes('utm:instagram') && c.includes('po:aperto'));
});
prova('DNT attivo: non conta nulla', async () => assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { dnt: '1' }), []));
prova('GPC attivo: non conta nulla', async () => assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { 'sec-gpc': '1' }), []));
prova('DNT e GPC insieme: non conta nulla', async () => assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { dnt: '1', 'sec-gpc': '1' }), []));
prova('payload malformato: scartato', async () => {
  assert.deepStrictEqual(await invia('{non e json'), []);
  assert.deepStrictEqual(await invia('x'.repeat(5000)), []);
  assert.deepStrictEqual(await invia({ l: 'it', e: 'non-un-array' }), []);
  assert.deepStrictEqual(await invia({ l: 'it', e: Array(13).fill({ t: 'pv' }) }), []);
});
prova('chiavi non ammesse: ignorate o ricondotte a "altro"', async () => {
  const c = await invia({ l: 'it', w: 1200, e: [{ t: 'c', n: 'spia', p: 'hero' }, { t: 's', n: 'admin' }, { t: 'w', n: 'altro' }, { t: 'c', n: 'telefono', p: 'posizione-inventata' }, { t: 'x', n: 'y' }] });
  assert(!c.some((k) => /spia|admin|posizione-inventata|altro$/.test(k) && !k.endsWith(':altro')), 'nessuna chiave inventata');
  assert(c.includes('ev:telefono') && c.includes('evp:telefono:altro'));
});
prova('clic dentro l\'evento Halloween: posizione "halloween" ammessa', async () => {
  const c = await invia({ l: 'it', w: 390, e: [{ t: 'c', n: 'whatsapp', p: 'halloween', o: 0 }] });
  assert(c.includes('ev:whatsapp') && c.includes('evp:whatsapp:halloween'), c.join(','));
});
prova('dati personali nel payload: non finiscono nell\'archivio', async () => {
  const c = await invia({ l: 'it', w: 390, nome: 'Mario Rossi', email: 'mario@example.com', tel: '3331234567', ip: '198.51.100.9', e: [{ t: 'pv', r: 'https://sito.it/?email=mario@example.com', nome: 'Mario', testo: 'ciao' }, { t: 'c', n: 'telefono', numero: '3331234567', p: 'hero' }] });
  const tutto = JSON.stringify(comandi);
  for (const s of ['Mario', 'example.com', '3331234567', '198.51.100.9', 'ciao']) assert(!tutto.includes(s), 'non deve comparire: ' + s);
  assert(c.length > 0);
});
prova('IP e user agent del visitatore non vengono mai scritti', async () => {
  await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] });
  const tutto = JSON.stringify(comandi);
  assert(!tutto.includes('203.0.113.77') && !tutto.includes('iPhone') && !tutto.includes('Mozilla'));
});
prova('origine non ammessa, bot e senza user agent: non contano', async () => {
  assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { origin: 'https://altro-sito.it' }), []);
  assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { 'user-agent': 'Googlebot/2.1 (+http://www.google.com/bot.html)' }), []);
  assert.deepStrictEqual(await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] }, { 'user-agent': 'curl/8' }), []);
});
prova('metodo diverso da POST: non conta', async () => {
  comandi = []; const r = res(); await t({ method: 'GET', headers: H }, r); assert.strictEqual(r.code, 204); assert.deepStrictEqual(comandi, []);
});
prova('scadenza dei contatori: 400 giorni', async () => {
  await invia({ l: 'it', w: 390, e: [{ t: 'pv' }] });
  const e = comandi.find((c) => c[0] === 'EXPIRE'); assert(e && e[2] === 60 * 60 * 24 * 400);
});

const rs = (auth, ip = '198.51.100.1') => ({ method: 'GET', headers: { ...(auth ? { authorization: 'Bearer ' + auth } : {}), 'x-forwarded-for': ip } });
prova('pannello: senza password 401 e senza leggere l\'archivio', async () => {
  comandi = []; const r = res(); await stats(rs(null, '198.51.100.2'), r); assert.strictEqual(r.code, 401); assert.deepStrictEqual(comandi, []);
});
prova('pannello: password giusta 200, senza visitatori unici e senza segreti', async () => {
  comandi = []; const r = res(); await stats(rs('password-solo-per-test', '198.51.100.3'), r);
  assert.strictEqual(r.code, 200); assert.strictEqual(r.headers['x-robots-tag'], 'noindex'); assert.strictEqual(r.headers['cache-control'], 'no-store');
  const txt = JSON.stringify(r.body); assert(!/visitatori/i.test(txt) && !txt.includes('password-solo-per-test') && !txt.includes('token-finto'));
});
prova('pannello: 5 errori bloccano, anche la password giusta (429)', async () => {
  const ip = '198.51.100.4';
  for (let i = 0; i < 5; i++) { const r = res(); await stats(rs('sbagliata', ip), r); assert.strictEqual(r.code, i < 5 ? 401 : 429); }
  const r = res(); await stats(rs('password-solo-per-test', ip), r); assert.strictEqual(r.code, 429);
});

(async () => {
  let ko = 0;
  for (const [nome, fn] of prove) {
    try { await fn(); console.log('OK   ' + nome); } catch (e) { ko++; console.log('FAIL ' + nome + '\n     ' + e.message); }
  }
  console.log(`\n${prove.length - ko}/${prove.length} test superati`);
  process.exit(ko ? 1 : 0);
})();
