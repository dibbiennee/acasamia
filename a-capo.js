/**
 * a-capo.js — tipografia nel browser, per siti statici o come rete di sicurezza.
 *
 * Uso:
 *   Includi il file con un tag script (src="/a-capo.js", defer), poi:
 *   addEventListener('DOMContentLoaded', () => ACapo.avvia());
 *   Se lo incolli dentro un tag script nella pagina, controlla che non contenga
 *   la sequenza di chiusura del tag script, o il browser taglia il codice.
 *
 * Opzioni di ACapo.avvia({...}):
 *   radice      elemento da trattare (default: document.body)
 *   adatta      selettore dei titoli da rimpicciolire finché la parola più lunga ci sta
 *               (default: '.display, .card h2, .card h3, [data-adatta]')
 *   minimo      quanto può scendere un titolo, in rapporto alla misura del CSS (default 0.45)
 *   osserva     rilegge i testi che cambiano dopo il caricamento (default true)
 *
 * Funzioni singole: ACapo.lega(radice), ACapo.adattaTitoli(radice), ACapo.sciogliSeSfora(radice).
 * Con i router a pagina singola chiama ACapo.aggiorna(paginaVisibile) a ogni cambio pagina.
 */
(function () {
  const NB = '\u00A0';
  const BREVI = ['il','lo','la','i','gli','le','un','uno','una','di','a','da','in','con','su','per','tra','fra',
    'del','dello','della','dei','degli','delle','al','allo','alla','ai','agli','alle','dal','dallo','dalla','dai','dagli','dalle',
    'nel','nello','nella','nei','negli','nelle','sul','sullo','sulla','sui','sugli','sulle','col',
    'e','ed','o','od','ma','né','che','se','perché','quando','come','dove','mentre','anche',
    'mi','ti','ci','vi','si','ne','li','non','ogni','più','meno','senza','sotto','sopra','dopo','prima','tu','io',
    // inglese
    'an','the','of','to','on','at','by','for','with','from','and','or','but','if','as','is','it','my','your','our','no','not'];
  const reBrevi = new RegExp('(?<=^|[\\s(«"“\'’\\[])(' + BREVI.join('|') + ')[ \\t\\n]+(?=\\S)', 'giu');
  const reUnita = /(\d)[ \t]+(?=(€|%|euro|ore|minuti|secondi|sere|giorni|notti|anni|mesi|km|kg|persone|posti|gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)(?![\p{L}]))/giu;
  const rePrima = /(?<=^|\s)(Room|Pack|Sala|Giorno|ore|alle|dalle|n\.|art\.)[ \t]+(?=\d)/giu;
  const SALTA = 'script, style, textarea, input, select, option, svg, code, pre, [data-noglue]';

  const legaTesto = (s) => s.replace(reBrevi, '$1' + NB).replace(reUnita, '$1' + NB).replace(rePrima, '$1' + NB);
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const tutti = (sel, r) => (r.matches && r.matches(sel) ? [r] : []).concat(Array.from(r.querySelectorAll(sel)));

  /** Lega parole brevi, numeri e unità; spezza i titoli dopo la virgola; evita la parola sola in fondo. */
  function lega(radice) {
    radice = radice || document.body;
    const w = document.createTreeWalker(radice, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement && !n.parentElement.closest(SALTA) && /\S/.test(n.nodeValue)) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT
    });
    const nodi = []; while (w.nextNode()) nodi.push(w.currentNode);
    nodi.forEach((n) => { const g = legaTesto(n.nodeValue); if (g !== n.nodeValue) n.nodeValue = g; });

    // Titoli h1 e h2 con virgole e senza a capo decisi a mano: una frase per riga
    tutti('h1, h2', radice).forEach((h) => {
      if (h.children.length || h.closest(SALTA)) return;
      if (parseFloat(getComputedStyle(h).fontSize) < 28) return; // solo i titoli grandi: quelli piccoli vanno a capo da soli
      const parti = h.textContent.split(/(?<=[,;:])\s+/);
      if (parti.length < 2) return;
      h.innerHTML = parti.map((p) => '<span class="cl" style="display:block">' + esc(p) + '</span>').join(' ');
    });

    // Paragrafi: ultime due parole insieme se l'ultima è corta
    tutti('p, li, figcaption, blockquote', radice).forEach((p) => {
      if (p.closest(SALTA) || p.textContent.length < 25) return;
      const tw = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let ultimo = null;
      while (tw.nextNode()) if (/\S/.test(tw.currentNode.nodeValue)) ultimo = tw.currentNode;
      if (!ultimo) return;
      const v = ultimo.nodeValue.replace(/[ \t\n]+(\S{1,12})\s*$/u, NB + '$1');
      if (v !== ultimo.nodeValue) ultimo.nodeValue = v;
    });
  }

  let SEL_ADATTA = '.display, .card h2, .card h3, [data-adatta]';
  let MINIMO = 0.45;

  /** Rimpicciolisce ogni titolo finché la parola (o il gruppo .ph) più lunga ci sta nel contenitore. */
  function adattaTitoli(radice) {
    tutti(SEL_ADATTA, radice || document).forEach((el) => {
      if (!el.getClientRects().length) return;
      el.style.fontSize = '';
      let px = parseFloat(getComputedStyle(el).fontSize);
      const min = px * MINIMO; let giri = 0;
      while (el.scrollWidth > el.clientWidth + 1 && px > min && giri++ < 150) { px -= 0.5; el.style.fontSize = px + 'px'; }
    });
  }

  /** In colonne molto strette le parole legate possono non entrare: lì si torna agli spazi normali. */
  function sciogliSeSfora(radice) {
    tutti('p, li, span, strong, b, em, a, label, small, dd, h3, h4, h5', radice || document).forEach((el) => {
      if (!el.getClientRects().length || el.closest(SALTA) || el.matches(SEL_ADATTA)) return;
      if (getComputedStyle(el).whiteSpace === 'nowrap' || el.scrollWidth <= el.clientWidth + 1) return;
      el.setAttribute('data-noglue', '');
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) w.currentNode.nodeValue = w.currentNode.nodeValue.replace(/\u00A0/g, ' ');
    });
  }

  function aggiorna(radice) { adattaTitoli(radice); sciogliSeSfora(radice); }

  function avvia(opz) {
    opz = opz || {};
    const radice = opz.radice || document.body;
    if (opz.adatta) SEL_ADATTA = opz.adatta;
    if (opz.minimo) MINIMO = opz.minimo;
    lega(radice);
    aggiorna(radice);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(() => aggiorna(radice));
      document.fonts.addEventListener('loadingdone', () => aggiorna(radice)); // font arrivati dopo il primo controllo
    }
    let t; addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => aggiorna(radice), 120); });
    if (opz.osserva !== false) {
      new MutationObserver((mm) => {
        const r = new Set();
        mm.forEach((m) => { const el = m.type === 'characterData' ? m.target.parentElement : m.target; if (el && el.nodeType === 1) r.add(el); });
        r.forEach((el) => lega(el));
      }).observe(radice, { subtree: true, childList: true, characterData: true });
    }
  }

  window.ACapo = { avvia, lega, adattaTitoli, sciogliSeSfora, aggiorna, legaTesto };
})();
