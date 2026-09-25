#!/usr/bin/env python3
"""
audit.py — controllo pre-consegna di un sito.

  pip install playwright --break-system-packages
  python3 -m playwright install chromium
  python3 audit.py https://esempio.it

Fa le verifiche che a occhio non si vedono: sbordamenti orizzontali,
bottoni troppo piccoli da toccare, testo minuscolo, peso della pagina,
errori in console, struttura dei titoli, SEO di base.
Gli screenshot finiscono in ./audit-shots/
"""
import sys, os, json
from playwright.sync_api import sync_playwright

LARGHEZZE = [(320, 720, "iPhone SE"), (390, 844, "iPhone standard"),
             (430, 932, "iPhone Max"), (768, 1024, "tablet"), (1440, 900, "desktop")]

SBORDA = """() => {
  const bad = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1)) {
      const p = el.parentElement;
      // ignoro i figli dentro un contenitore che scorre di suo
      if (p && ['auto','scroll'].includes(getComputedStyle(p).overflowX)) return;
      bad.push(el.tagName.toLowerCase() +
        (typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\\s+/)[0] : '') +
        ' [' + Math.round(r.left) + '→' + Math.round(r.right) + ']');
    }
  });
  return { scrollW: document.documentElement.scrollWidth,
           innerW: window.innerWidth,
           sborda: [...new Set(bad)].slice(0, 10) };
}"""

TOCCO = """() => {
  const piccoli = [];
  document.querySelectorAll('a, button, input, select, [role=button]').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    if (r.height < 40 || r.width < 40) {
      piccoli.push((el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 32)
        + ' (' + Math.round(r.width) + '×' + Math.round(r.height) + ')');
    }
  });
  return [...new Set(piccoli)].slice(0, 12);
}"""

TESTO_PICCOLO = """() => {
  const p = new Set();
  document.querySelectorAll('p, li, span, td, a, div').forEach(el => {
    if (!el.innerText || el.children.length) return;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs && fs < 14) p.add(Math.round(fs) + 'px — "' + el.innerText.trim().slice(0, 40) + '"');
  });
  return [...p].slice(0, 8);
}"""

STRUTTURA = """() => {
  const h = [...document.querySelectorAll('h1,h2,h3,h4')].map(e => e.tagName + ' ' + e.innerText.trim().slice(0,45));
  const img = [...document.querySelectorAll('img')];
  return {
    titoli: h.slice(0, 25),
    h1: document.querySelectorAll('h1').length,
    lang: document.documentElement.lang || '(mancante)',
    viewport: !!document.querySelector('meta[name=viewport]'),
    title: (document.title || '').slice(0, 70),
    titleLen: (document.title || '').length,
    description: (document.querySelector('meta[name=description]')?.content || '(mancante)').slice(0, 70),
    descLen: (document.querySelector('meta[name=description]')?.content || '').length,
    robots: document.querySelector('meta[name=robots]')?.content || '(nessuno)',
    canonical: document.querySelector('link[rel=canonical]')?.href || '(mancante)',
    og: !!document.querySelector('meta[property="og:image"]'),
    jsonld: document.querySelectorAll('script[type="application/ld+json"]').length,
    img_totali: img.length,
    img_senza_alt: img.filter(i => !i.alt).map(i => (i.currentSrc || i.src).split('/').pop()).slice(0, 8),
    img_senza_lazy: img.filter(i => !i.loading).length,
    testo_troncato: [...document.querySelectorAll('*')].filter(e =>
        !e.children.length && /[,;]\\s*(…|\\.\\.\\.)$/.test((e.innerText||'').trim()))
      .map(e => e.innerText.trim().slice(-45)).slice(0, 6)
  };
}"""


def riga(t):
    print("\n" + t + "\n" + "─" * len(t))


def main(url):
    os.makedirs("audit-shots", exist_ok=True)
    errori, richieste = [], []

    with sync_playwright() as pw:
        b = pw.chromium.launch()

        # --- passata mobile con misurazione del peso ---
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        pg.on("console", lambda m: errori.append(m.type + ": " + m.text[:120]) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: errori.append("pageerror: " + str(e)[:120]))
        pg.on("response", lambda r: richieste.append((r.url, r.request.resource_type,
                                                      int(r.headers.get("content-length") or 0))))
        pg.goto(url, wait_until="networkidle", timeout=60000)
        pg.wait_for_timeout(1200)

        s = pg.evaluate(STRUTTURA)

        riga("SEO E STRUTTURA")
        print(f"  title        {s['title']}  ({s['titleLen']} caratteri, ideale 50-60)")
        print(f"  description  {s['description']}  ({s['descLen']} caratteri, ideale 140-160)")
        print(f"  lang         {s['lang']}")
        print(f"  viewport     {'ok' if s['viewport'] else 'MANCANTE — il sito non sarà responsive'}")
        print(f"  robots       {s['robots']}")
        print(f"  canonical    {s['canonical']}")
        print(f"  og:image     {'ok' if s['og'] else 'mancante — link brutti su WhatsApp'}")
        print(f"  dati strutt. {s['jsonld']} blocchi JSON-LD")
        print(f"  h1           {s['h1']} (ne serve esattamente 1)")
        if s["testo_troncato"]:
            print("  TESTI TRONCATI A META' FRASE:")
            for x in s["testo_troncato"]:
                print("     …" + x)

        riga("IMMAGINI")
        print(f"  totali {s['img_totali']} · senza alt {len(s['img_senza_alt'])} · senza lazy-load {s['img_senza_lazy']}")
        for x in s["img_senza_alt"]:
            print("     manca alt: " + x)

        riga("PESO")
        tot = sum(k for _, _, k in richieste)
        print(f"  {len(richieste)} richieste · {tot/1024:.0f} KB dichiarati")
        for u, tipo, k in sorted(richieste, key=lambda r: -r[2])[:6]:
            if k > 80_000:
                print(f"     {k/1024:6.0f} KB  {tipo:8s} {u.split('/')[-1][:50]}")

        riga("ERRORI IN CONSOLE")
        print("  nessuno" if not errori else "")
        for e in dict.fromkeys(errori):
            print("  " + e)

        riga("GERARCHIA DEI TITOLI")
        for h in s["titoli"]:
            print("  " + h)

        pg.close()

        # --- sbordamenti e tocco su tutte le larghezze ---
        riga("LARGHEZZE")
        for w, h, nome in LARGHEZZE:
            p2 = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 500 else 1)
            p2.goto(url, wait_until="networkidle", timeout=60000)
            p2.wait_for_timeout(900)
            o = p2.evaluate(SBORDA)
            ok = o["scrollW"] <= o["innerW"] + 1
            print(f"\n  {w}px ({nome}): {'ok' if ok else 'SCROLL ORIZZONTALE ' + str(o['scrollW'] - o['innerW']) + 'px'}")
            for x in o["sborda"]:
                print("     sborda: " + x)
            if w == 390:
                for x in p2.evaluate(TOCCO):
                    print("     bersaglio piccolo: " + x)
                for x in p2.evaluate(TESTO_PICCOLO):
                    print("     testo piccolo: " + x)
            p2.screenshot(path=f"audit-shots/{w}.png", full_page=(w == 390))
            p2.close()

        b.close()
    print("\nScreenshot in ./audit-shots/\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: python3 audit.py https://esempio.it")
    main(sys.argv[1])
