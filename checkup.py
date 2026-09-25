#!/usr/bin/env python3
"""
checkup.py — controllo completo di un sito prima della consegna.

  pip install playwright --break-system-packages
  python3 -m playwright install chromium
  python3 checkup.py https://esempio.it

Controlla: indicizzabilità, SEO, dati strutturati, contrasto del testo,
sbordamenti a cinque larghezze, bersagli di tocco, peso e file pesanti,
link rotti, errori in console, intestazioni di sicurezza, immagini.
Screenshot in ./checkup-shots/  ·  Report in ./checkup.md
"""
import sys, os, json, re, urllib.request, urllib.error
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

LARGHEZZE = [(320, 720, "iPhone SE"), (390, 844, "iPhone standard"),
             (430, 932, "iPhone Max"), (768, 1024, "tablet"), (1440, 900, "desktop")]

OUT = []
def p(s=""):
    print(s); OUT.append(s)
def titolo(t):
    p(); p(t); p("─" * len(t))

# ───────────────────────── script iniettati nella pagina ─────────────────────────

JS_SEO = r"""() => {
  const q = s => document.querySelector(s);
  const img = [...document.querySelectorAll('img')];
  const a   = [...document.querySelectorAll('a[href]')];
  return {
    title: document.title || '',
    desc: q('meta[name=description]')?.content || '',
    lang: document.documentElement.lang || '',
    viewport: q('meta[name=viewport]')?.content || '',
    robots: q('meta[name=robots]')?.content || '',
    canonical: q('link[rel=canonical]')?.href || '',
    ogTitle: q('meta[property="og:title"]')?.content || '',
    ogImage: q('meta[property="og:image"]')?.content || '',
    ogDesc: q('meta[property="og:description"]')?.content || '',
    favicon: !!q('link[rel~="icon"]'),
    themeColor: q('meta[name=theme-color]')?.content || '',
    hreflang: [...document.querySelectorAll('link[rel=alternate][hreflang]')].map(l=>l.hreflang),
    jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s=>s.textContent),
    h1: [...document.querySelectorAll('h1')].map(e=>e.innerText.trim().slice(0,60)),
    titoli: [...document.querySelectorAll('h1,h2,h3,h4')].map(e=>e.tagName+' '+e.innerText.trim().slice(0,50)),
    imgTot: img.length,
    imgNoAlt: img.filter(i=>!i.alt).map(i=>(i.currentSrc||i.src||'').split('/').pop().slice(0,40)),
    imgNoLazy: img.filter((i,n)=>n>0 && !i.loading).length,
    imgNoDim: img.filter(i=>!i.width||!i.height).length,
    link: a.map(x=>x.href).filter(h=>/^https?:/.test(h)),
    linkVuoti: a.filter(x=>!x.innerText.trim() && !x.querySelector('img,svg') && !x.getAttribute('aria-label')).length,
    linkEsterniNoRel: a.filter(x=>x.target==='_blank' && !(x.rel||'').includes('noopener')).length,
    parole: (document.body.innerText||'').trim().split(/\s+/).length,
    troncati: [...document.querySelectorAll('*')].filter(e=>!e.children.length &&
                /[,;]\s*(…|\.\.\.)$/.test((e.innerText||'').trim()))
              .map(e=>e.innerText.trim().slice(-50)).slice(0,8),
    filtriBrightness: [...document.querySelectorAll('video,img')].filter(e=>{
        const f=getComputedStyle(e).filter||''; return /bright|contrast|saturate/.test(f);}).length,
    videoConControlli: [...document.querySelectorAll('video')].filter(v=>v.controls).length,
    videoTot: document.querySelectorAll('video').length
  };
}"""

JS_LAYOUT = r"""() => {
  const bad=[];
  document.querySelectorAll('body *').forEach(el=>{
    const r=el.getBoundingClientRect();
    if(r.width>0 && (r.right>window.innerWidth+1 || r.left<-1)){
      const pa=el.parentElement;
      if(pa && ['auto','scroll'].includes(getComputedStyle(pa).overflowX)) return;
      bad.push(el.tagName.toLowerCase()+
        (typeof el.className==='string'&&el.className?'.'+el.className.trim().split(/\s+/)[0]:'')+
        ' ['+Math.round(r.left)+'→'+Math.round(r.right)+']');
    }
  });
  return {sw:document.documentElement.scrollWidth, iw:window.innerWidth,
          sborda:[...new Set(bad)].slice(0,10)};
}"""

JS_TOCCO = r"""() => {
  const out=[];
  document.querySelectorAll('a,button,input,select,[role=button]').forEach(el=>{
    const r=el.getBoundingClientRect();
    if(!r.width||!r.height) return;
    if(r.height<40||r.width<40)
      out.push((el.innerText||el.getAttribute('aria-label')||el.tagName).trim().slice(0,30)
               +' ('+Math.round(r.width)+'×'+Math.round(r.height)+')');
  });
  return [...new Set(out)].slice(0,12);
}"""

# contrasto WCAG reale, solo su testo con sfondo a tinta unita
JS_CONTRASTO = r"""() => {
  const lum = c => { const [r,g,b]=c.map(v=>{v/=255; return v<=.03928? v/12.92 : Math.pow((v+.055)/1.055,2.4);});
                     return .2126*r+.7152*g+.0722*b; };
  const rgb = s => { const m=(s||'').match(/\d+(\.\d+)?/g); return m? m.slice(0,3).map(Number):null; };
  const alpha = s => { const m=(s||'').match(/rgba?\([^)]*,\s*([\d.]+)\s*\)/); return m? parseFloat(m[1]):1; };
  const sfondo = el => {
    let n=el;
    while(n && n!==document.documentElement){
      const st=getComputedStyle(n);
      if(st.backgroundImage && st.backgroundImage!=='none') return null; // sopra immagine: non misurabile
      const c=st.backgroundColor;
      if(c && alpha(c)>.92) return rgb(c);
      n=n.parentElement;
    }
    return [255,255,255];
  };
  const out=[];
  document.querySelectorAll('p,li,span,a,h1,h2,h3,h4,button,td,label,div').forEach(el=>{
    if(el.children.length || !el.innerText || !el.innerText.trim()) return;
    const st=getComputedStyle(el);
    if(st.visibility==='hidden'||st.display==='none'||parseFloat(st.opacity)<.5) return;
    const fg=rgb(st.color), bg=sfondo(el);
    if(!fg||!bg) return;
    const L1=lum(fg), L2=lum(bg);
    const ratio=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
    const fs=parseFloat(st.fontSize), grosso = fs>=24 || (fs>=18.66 && parseInt(st.fontWeight)>=700);
    const soglia = grosso? 3 : 4.5;
    if(ratio < soglia)
      out.push(ratio.toFixed(2)+':1 (serve '+soglia+') '+Math.round(fs)+'px — "'+el.innerText.trim().slice(0,38)+'"');
  });
  return [...new Set(out)].slice(0,12);
}"""

JS_TESTO_PICCOLO = r"""() => {
  const s=new Set();
  document.querySelectorAll('p,li,span,td,a').forEach(el=>{
    if(el.children.length||!el.innerText.trim()) return;
    const fs=parseFloat(getComputedStyle(el).fontSize);
    if(fs&&fs<13) s.add(Math.round(fs)+'px — "'+el.innerText.trim().slice(0,38)+'"');
  });
  return [...s].slice(0,8);
}"""


def testa(url, percorso):
    try:
        req = urllib.request.Request(urljoin(url, percorso), headers={'User-Agent':'checkup'})
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read(4000).decode('utf-8', 'ignore'), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, '', dict(e.headers or {})
    except Exception as e:
        return None, str(e), {}


def main(url):
    os.makedirs("checkup-shots", exist_ok=True)
    errori, richieste = [], []
    _, _, head_root = testa(url, "")

    # ── indicizzabilità: robots.txt, X-Robots-Tag, sitemap ──
    titolo("INDICIZZABILITÀ")

    st, body, _ = testa(url, "/robots.txt")
    if st == 200:
        p("  robots.txt    servito — contenuto reale dal bordo:")
        for riga in [l for l in body.splitlines() if l.strip()][:14]:
            p("     | " + riga.strip())
        # blocco totale su qualunque user-agent, non solo su *
        blocchi = re.split(r'(?im)^\s*user-agent:', body)
        totale = any(re.search(r'^\s*Disallow:\s*/\s*$', b, re.M | re.I) for b in blocchi)
        mirato = [b.strip().splitlines()[0] for b in blocchi[1:]
                  if re.search(r'^\s*Disallow:', b, re.M | re.I)
                  and not b.strip().lower().startswith('*')]
        if totale:
            p("     BLOCCA TUTTO: nessun crawler può leggere il sito. Da togliere al go-live.")
        if mirato:
            p(f"     regole mirate su user-agent specifici: {', '.join(mirato)}")
        if not totale and not mirato:
            p("     nessun blocco")
    else:
        p(f"  robots.txt    assente (status {st}) — va bene, equivale a tutto permesso")

    # X-Robots-Tag: invisibile nel robots.txt e nel meta, blocca comunque l'indicizzazione.
    # Vercel lo mette a noindex sui deployment di preview.
    xr = (head_root.get('x-robots-tag') or '').lower()
    if xr:
        grave = 'noindex' in xr or 'none' in xr
        p(f"  X-Robots-Tag  {xr}" + ("   ← IL SITO NON VERRÀ INDICIZZATO" if grave else ""))
        if grave:
            p("     Su Vercel questo header compare sui deployment di preview:")
            p("     verifica che il dominio punti alla produzione, non a una preview.")
    else:
        p("  X-Robots-Tag  assente (ok)")

    st, _, _ = testa(url, "/sitemap.xml")
    p(f"  sitemap.xml   {'ok' if st==200 else 'assente'}")

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width":390,"height":844}, device_scale_factor=2)
        pg.on("console", lambda m: errori.append(f"{m.type}: {m.text[:130]}") if m.type in ("error","warning") else None)
        pg.on("pageerror", lambda e: errori.append("pageerror: " + str(e)[:130]))
        pg.on("response", lambda r: richieste.append((r.url, r.request.resource_type,
                                                      int(r.headers.get("content-length") or 0), r.status)))
        risp = pg.goto(url, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(1500)
        head = risp.headers if risp else {}
        s = pg.evaluate(JS_SEO)

        # ── sicurezza e consegna ──
        titolo("INTESTAZIONI HTTP")
        for k, atteso in [("strict-transport-security","HSTS mancante"),
                          ("x-content-type-options","x-content-type-options: nosniff mancante"),
                          ("referrer-policy","referrer-policy mancante")]:
            p(f"  {k:32s} {head.get(k) or '— ' + atteso}")

        # ── SEO ──
        titolo("SEO")
        tl, dl = len(s['title']), len(s['desc'])
        p(f"  title         {s['title'][:68]}")
        p(f"                {tl} caratteri {'(ideale 50-60)' if not 45<=tl<=62 else 'ok'}")
        p(f"  description   {s['desc'][:68]}")
        p(f"                {dl} caratteri {'(ideale 140-160)' if not 130<=dl<=165 else 'ok'}")
        p(f"  lang          {s['lang'] or 'MANCANTE'}")
        p(f"  viewport      {s['viewport'] or 'MANCANTE'}")
        xr2 = (head_root.get('x-robots-tag') or '').lower()
        blocchi_noindex = [n for n, v in [("meta robots", s['robots']), ("header X-Robots-Tag", xr2)]
                           if 'noindex' in (v or '').lower()]
        p(f"  meta robots   {s['robots'] or '(nessuno)'}")
        if blocchi_noindex:
            p(f"                NOINDEX attivo via: {' e '.join(blocchi_noindex)}")
        p(f"  canonical     {s['canonical'] or 'mancante'}")
        p(f"  og:title      {'ok' if s['ogTitle'] else 'mancante'}   og:image {'ok' if s['ogImage'] else 'MANCANTE — link brutti su WhatsApp'}")
        p(f"  favicon       {'ok' if s['favicon'] else 'mancante'}   theme-color {s['themeColor'] or 'mancante'}")
        p(f"  hreflang      {', '.join(s['hreflang']) or 'nessuno'}")
        p(f"  h1            {len(s['h1'])} {'(ne serve 1)' if len(s['h1'])!=1 else 'ok'}  {s['h1'][:2]}")
        p(f"  parole        {s['parole']}" + ("   ← poco testo per posizionarsi" if s['parole'] < 250 else ""))

        titolo("DATI STRUTTURATI")
        if not s['jsonld']:
            p("  nessun JSON-LD")
        for blocco in s['jsonld']:
            try:
                d = json.loads(blocco)
                tipi = d.get('@type') if isinstance(d, dict) else [x.get('@type') for x in d]
                p(f"  valido — @type: {tipi}")
                if isinstance(d, dict):
                    manca = [k for k in ('name','address','telephone','openingHoursSpecification','geo') if k not in d]
                    if manca: p(f"     campi assenti: {', '.join(manca)}")
            except Exception as e:
                p(f"  JSON-LD NON VALIDO: {str(e)[:70]}")

        titolo("IMMAGINI E VIDEO")
        p(f"  immagini {s['imgTot']} · senza alt {len(s['imgNoAlt'])} · senza lazy {s['imgNoLazy']} · senza dimensioni {s['imgNoDim']}")
        for x in s['imgNoAlt'][:6]: p(f"     manca alt: {x}")
        if s['videoTot']:
            p(f"  video {s['videoTot']} · con controlli visibili {s['videoConControlli']}"
              + ("   ← un video di sfondo non deve avere controlli" if s['videoConControlli'] else ""))
        if s['filtriBrightness']:
            p(f"  {s['filtriBrightness']} media con filter brightness/contrast   ← amplifica il rumore, correggere il file")

        titolo("CONTRASTO DEL TESTO (WCAG AA)")
        c = pg.evaluate(JS_CONTRASTO)
        p("  tutto a norma" if not c else "")
        for x in c: p("  " + x)
        p("  (il testo sopra foto o video non è misurabile: va verificato a occhio)")

        titolo("PESO")
        tot = sum(k for _,_,k,_ in richieste)
        p(f"  {len(richieste)} richieste · {tot/1024:.0f} KB dichiarati")
        for u,t,k,_ in sorted(richieste, key=lambda r:-r[2])[:8]:
            if k > 60_000: p(f"     {k/1024:6.0f} KB  {t:8s} {u.split('/')[-1][:48]}")

        titolo("RISPOSTE NON OK")
        ko = [(u,st) for u,_,_,st in richieste if st >= 400]
        p("  nessuna" if not ko else "")
        for u,st in ko[:10]: p(f"  {st}  {u[:90]}")

        titolo("LINK")
        interni = [l for l in set(s['link']) if urlparse(l).netloc == urlparse(url).netloc][:25]
        rotti = []
        for l in interni:
            stt,_,_ = testa(l, "")
            if stt and stt >= 400: rotti.append((l, stt))
        p(f"  {len(interni)} link interni controllati · {len(rotti)} rotti")
        for l,stt in rotti: p(f"     {stt}  {l}")
        if s['linkVuoti']: p(f"  {s['linkVuoti']} link senza testo né aria-label (illeggibili da screen reader)")
        if s['linkEsterniNoRel']: p(f"  {s['linkEsterniNoRel']} link target=_blank senza rel=noopener")

        titolo("ERRORI IN CONSOLE")
        p("  nessuno" if not errori else "")
        for e in list(dict.fromkeys(errori))[:12]: p("  " + e)

        if s['troncati']:
            titolo("TESTI TRONCATI A METÀ FRASE")
            for x in s['troncati']: p("  …" + x)

        titolo("GERARCHIA DEI TITOLI")
        for h in s['titoli'][:28]: p("  " + h)

        pg.close()

        titolo("LARGHEZZE")
        for w,h,nome in LARGHEZZE:
            p2 = b.new_page(viewport={"width":w,"height":h}, device_scale_factor=2 if w<500 else 1)
            p2.goto(url, wait_until="networkidle", timeout=60000)
            p2.wait_for_timeout(900)
            o = p2.evaluate(JS_LAYOUT)
            ok = o['sw'] <= o['iw'] + 1
            p(f"\n  {w}px ({nome}): {'ok' if ok else 'SCROLL ORIZZONTALE di ' + str(o['sw']-o['iw']) + 'px'}")
            for x in o['sborda']: p("     sborda: " + x)
            if w == 390:
                for x in p2.evaluate(JS_TOCCO): p("     bersaglio piccolo: " + x)
                for x in p2.evaluate(JS_TESTO_PICCOLO): p("     testo piccolo: " + x)
            p2.screenshot(path=f"checkup-shots/{w}.png", full_page=(w in (390,1440)))
            p2.close()
        b.close()

    open("checkup.md","w").write("```\n" + "\n".join(OUT) + "\n```\n")
    p("\nScreenshot in ./checkup-shots/ · report in ./checkup.md\n")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit("uso: python3 checkup.py https://esempio.it")
    main(sys.argv[1])
