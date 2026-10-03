// Lettura delle statistiche per il pannello. Protetta da password e dal blocco dei tentativi.

const { redis, adesso, giorniIndietro, bloccato, attesaResidua, authed, archivio } = require('./_lib.js');

const EVENTI = ['telefono', 'whatsapp', 'indicazioni', 'indicazioni-apple', 'recensione', 'glovo', 'instagram', 'facebook'];

function somma(a, b) { for (const k of Object.keys(b)) a[k] = (a[k] || 0) + Number(b[k] || 0); return a; }

function hashAObj(arr) {
  const o = {};
  if (Array.isArray(arr)) for (let i = 0; i < arr.length; i += 2) o[arr[i]] = Number(arr[i + 1]);
  return o;
}

module.exports = async function handler(req, res) {
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('X-Robots-Tag', 'noindex');
  if (bloccato(req)) {
    const attesa = attesaResidua(req);
    res.setHeader('Retry-After', String(attesa));
    return res.status(429).json({ error: 'too many attempts', attesa });
  }
  if (!authed(req)) return res.status(401).json({ error: 'unauthorized' });
  if (!archivio()) return res.status(503).json({ error: 'archivio non collegato' });

  try {
    const giorni = Math.min(90, Math.max(1, parseInt(req.query && req.query.days, 10) || 30));
    const elenco = giorniIndietro(giorni * 2); // il doppio: serve anche il periodo precedente per il confronto
    const cmd = [];
    elenco.forEach((g) => { cmd.push(['HGETALL', 's:' + g]); cmd.push(['PFCOUNT', 'u:' + g]); });
    cmd.push(['PFCOUNT', ...elenco.slice(giorni).map((g) => 'u:' + g)]);
    cmd.push(['PFCOUNT', ...elenco.slice(0, giorni).map((g) => 'u:' + g)]);
    const r = await redis(cmd);

    const giornalieri = elenco.map((g, i) => ({ giorno: g, h: hashAObj(r[i * 2]), visitatori: Number(r[i * 2 + 1] || 0) }));
    const corrente = giornalieri.slice(giorni);
    const precedente = giornalieri.slice(0, giorni);
    const visCorr = Number(r[elenco.length * 2] || 0);
    const visPrec = Number(r[elenco.length * 2 + 1] || 0);

    const totale = (periodo) => periodo.reduce((acc, d) => somma(acc, d.h), {});
    const T = totale(corrente);
    const P = totale(precedente);
    const clic = (t) => EVENTI.reduce((n, e) => n + (t['ev:' + e] || 0), 0);

    const per = (t, prefisso) => {
      const o = {};
      Object.keys(t).forEach((k) => { if (k.startsWith(prefisso)) o[k.slice(prefisso.length)] = t[k]; });
      return o;
    };

    const eventi = {};
    EVENTI.forEach((e) => {
      eventi[e] = {
        totale: T['ev:' + e] || 0,
        precedente: P['ev:' + e] || 0,
        posizione: per(T, 'evp:' + e + ':'),
        aperto: T['evo:' + e + ':aperto'] || 0,
        chiuso: T['evo:' + e + ':chiuso'] || 0,
        lingua: { it: T['evl:' + e + ':it'] || 0, en: T['evl:' + e + ':en'] || 0 },
      };
    });

    const ore = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'));
    res.status(200).json({
      ok: true,
      aggiornato: adesso().giorno,
      periodo: { giorni, da: corrente[0].giorno, a: corrente[corrente.length - 1].giorno },
      totali: {
        visite: T.pv || 0, visite_precedenti: P.pv || 0,
        visitatori: visCorr, visitatori_precedenti: visPrec,
        clic: clic(T), clic_precedenti: clic(P),
        tasso_clic: T.pv ? Math.round((clic(T) / T.pv) * 1000) / 10 : 0,
      },
      giornaliero: corrente.map((d) => ({ giorno: d.giorno, visite: d.h.pv || 0, visitatori: d.visitatori, clic: clic(d.h) })),
      eventi,
      sezioni: per(T, 'sez:'),
      scorrimenti: per(T, 'sw:'),
      dispositivi: per(T, 'dev:'),
      lingue: per(T, 'lang:'),
      provenienza: per(T, 'ref:'),
      campagne: per(T, 'utm:'),
      ore_visite: ore.map((h) => T['h:' + h] || 0),
      ore_clic: ore.map((h) => T['evh:' + h] || 0),
    });
  } catch (e) {
    res.status(500).json({ error: 'errore di lettura' });
  }
};
