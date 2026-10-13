"""Controlli statici sulla release: file generati, informative IT/EN, sitemap/robots, esclusioni dalla pubblicazione, api.
Esecuzione: python3 tests/privacy/release_check.py   (dalla radice del progetto; non usa rete ne' browser)
"""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')); os.chdir(ROOT)
ok = ko = 0
def check(nome, cond, extra=''):
    global ok, ko
    if cond: ok += 1; print('OK   ' + nome)
    else: ko += 1; print('FAIL ' + nome + ' ' + str(extra))
def leggi(p): return open(p, encoding='utf-8').read()
def main_of(h): return re.search(r'<main id="top" class="legal">.*?</main>', h, re.S).group(0)

pagine = {'it': leggi('index.html'), 'en': leggi('en/index.html'), 'pit': leggi('privacy/index.html'), 'pen': leggi('en/privacy/index.html'), 'pan': leggi('pannello/index.html')}
acceso = any('analytics.ahrefs.com' in pagine[k] for k in ('it', 'en', 'pit', 'pen'))
print(f'Stato della build: Ahrefs {"ACCESO" if acceso else "SPENTO"}')
check('Ahrefs coerente su tutte e 4 le pagine pubbliche (tutte accese o tutte spente)', all(('analytics.ahrefs.com' in pagine[k]) == acceso for k in ('it', 'en', 'pit', 'pen')))
check('pannello senza Ahrefs e senza tracciamento pubblico', 'ahrefs' not in pagine['pan'].lower() and '/api/t' not in pagine['pan'])
check('nessun segnaposto dei blocchi Ahrefs rimasto nelle pagine generate', not any('AHREFS:' in v for v in pagine.values()))
if not acceso:
    check('build predefinita: nessun riferimento ad Ahrefs nelle 4 pagine (script e informative)', not any('ahrefs' in pagine[k].lower() for k in ('it', 'en', 'pit', 'pen')))
check('interruttore Ahrefs: spento se la variabile non e\' impostata (build.py)', 'AHREFS_ATTIVO = os.environ.get("AHREFS_ANALYTICS") == "1"' in leggi('build.py'))
check('sorgente: riattivazione manda ad Ahrefs il solo percorso (data-page-location)', "setAttribute('data-page-location',location.pathname)" in leggi('source/vestito.html'))
check('la visita invia lo stato aperto/chiuso (IT e EN)', all("o:st0&&st0.getAttribute('data-open')==='true'?1:0" in pagine[k] for k in ('it', 'en')))

# informative: struttura IT/EN
mi, me = main_of(pagine['pit']), main_of(pagine['pen'])
conta = lambda h, t: len(re.findall(r'<%s[ >]' % t, h))
for t in ('h1', 'h2', 'h3', 'p', 'li', 'b', 'i', 'a', 'br'):
    check(f'informative: stesso numero di <{t}> in IT ({conta(mi,t)}) e EN ({conta(me,t)})', conta(mi, t) == conta(me, t))
check('informative: stessi link (mailto) in IT e EN', sorted(re.findall(r'href="([^"]+)"', mi)) == sorted(re.findall(r'href="([^"]+)"', me)))
check('informative: stessa menzione di Ahrefs in IT e EN', ('Ahrefs' in mi) == ('Ahrefs' in me) == acceso)
check('informative: stessa data di aggiornamento (13 ottobre / 13 October 2026)', '13 ottobre 2026' in mi and '13 October 2026' in me)
for chiave in ('Vercel', 'Upstash', 'Aruba', 'Meta', '400', 'Garante', 'Le 3 lettere S.R.L.', '18241231002', 'le3lettere@pec.it', 'info@acasamiacivitavecchia.it', 'Do Not Track', 'Global Privacy Control', 'localStorage', 'sessionStorage'):
    check(f'informative: "{chiave}" presente in IT e EN', chiave in mi and chiave in me)
check('informative: nessun segnaposto tra parentesi quadre ne\' trattino lungo', not re.search(r'\[[A-Za-z ]+\]|—', mi + me))
check('informative: nessuna dichiarazione di "conforme" o "certificato"', not re.search(r'conform|certificat|compliant|certified', (mi + me).lower().replace('certified email', '')))
check('informative: nessun DPO inventato', 'DPO' not in mi and 'Responsabile della protezione' not in mi and 'Data Protection Officer' not in me)
check('informative: dichiarano assenza di cookie e di storage', 'non usa cookie' in mi and 'does not use cookies' in me)
check('link informativa nel footer di / e /en/', 'href="/privacy/"' in pagine['it'] and 'href="/en/privacy/"' in pagine['en'])
check('pagine privacy: canonical e hreflang reciproci', all(x in pagine['pit'] for x in ('rel="canonical" href="https://acasamiacivitavecchia.it/privacy/"', 'hreflang="en" href="https://acasamiacivitavecchia.it/en/privacy/"')) and 'rel="canonical" href="https://acasamiacivitavecchia.it/en/privacy/"' in pagine['pen'])

# sitemap e robots
sm, rb = leggi('sitemap.xml'), leggi('robots.txt')
locs = re.findall(r'<loc>([^<]+)</loc>', sm)
check('sitemap: 4 pagine (IT/EN e informative)', sorted(locs) == sorted(['https://acasamiacivitavecchia.it/', 'https://acasamiacivitavecchia.it/en/', 'https://acasamiacivitavecchia.it/privacy/', 'https://acasamiacivitavecchia.it/en/privacy/']), locs)
check('sitemap: nessun pannello ne\' api', 'pannello' not in sm and '/api' not in sm)
check('robots: Allow e Sitemap sul dominio definitivo', 'Sitemap: https://acasamiacivitavecchia.it/sitemap.xml' in rb and 'Allow: /' in rb)

# esclusioni dalla pubblicazione
vi = [l.strip() for l in leggi('.vercelignore').splitlines()]
for d in ('reports', 'tests', 'videos', 'source', 'materiale-fotografico'):
    check(f'.vercelignore esclude {d}/', d in vi)
vj = leggi('vercel.json')
check('vercel.json: regione fra1 e noindex su /api/ e /pannello', '"regions":["fra1"]' in vj.replace(' ', '').replace('\n', '') and 'noindex' in vj)

# api: rispetto a main, solo commenti (le metriche storiche e il formato dei dati non cambiano)
base = subprocess.run(['git', 'merge-base', 'HEAD', 'main'], capture_output=True, text=True).stdout.strip()
d = subprocess.run(['git', 'diff', '-U0', base, '--', 'api'], capture_output=True, text=True).stdout.splitlines()
righe = [l for l in d if l[:1] in '+-' and not l.startswith(('+++', '---'))]
check(f'api/: rispetto a main cambiano solo commenti ({len(righe)} righe)', all(re.match(r'^[+-]\s*(//|$)', l) for l in righe), [l for l in righe if not re.match(r'^[+-]\s*(//|$)', l)][:3])
t = leggi('api/t.js')
check('api/t.js: nessuna scrittura distruttiva (solo HINCRBY ed EXPIRE)', set(re.findall(r"\['([A-Z]+)'", t)) == {'HINCRBY', 'EXPIRE'}, set(re.findall(r"\['([A-Z]+)'", t)))
check('api/stats.js: solo lettura', not re.search(r"'(HINCRBY|HSET|DEL|EXPIRE|SET|FLUSH\w*)'", leggi('api/stats.js')))
check('chiavi storiche invariate: po:aperto / po:chiuso e ev*:aperto|chiuso', "inc('po:' + (x.o ? 'aperto' : 'chiuso'))" in t and "'evo:'" in t)
print(f'\n{ok} superati, {ko} falliti')
sys.exit(1 if ko else 0)
