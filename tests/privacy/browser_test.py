"""Test del browser: cookie, storage, richieste esterne, payload delle statistiche, DNT e GPC.
Non tocca la produzione: serve il sito da una cartella locale, fa risolvere il nome di produzione
su 127.0.0.1 (cosi' le regole "solo sul dominio vero" valgono) e blocca ogni richiesta esterna.
Esecuzione:  python3 tests/privacy/browser_test.py [--ahrefs on|off]   (off di default: e' come e' costruito il sito)
"""
import sys, json, threading, http.server, socketserver, functools, os
from playwright.sync_api import sync_playwright

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AHREFS = 'on' if '--ahrefs' in sys.argv and sys.argv[sys.argv.index('--ahrefs') + 1] == 'on' else 'off'
HOST = 'acasamiacivitavecchia.it'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1'

class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=ROOT)); PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

PAGINE = ['/', '/en/', '/privacy/', '/en/privacy/']
VIEWPORT = {'desktop': {'width': 1280, 'height': 900}, 'mobile': {'width': 390, 'height': 844}}
ok = ko = 0
def check(nome, cond, extra=''):
    global ok, ko
    if cond: ok += 1; print('OK   ' + nome)
    else: ko += 1; print('FAIL ' + nome + ' ' + extra)

def apri(b, vp, init=None):
    ctx = b.new_context(viewport=VIEWPORT[vp], user_agent=UA, is_mobile=(vp == 'mobile'))
    if init: ctx.add_init_script(init)
    pg = ctx.new_page()
    log = {'esterni': [], 'beacon': [], 'ahrefs': [], 'errori': []}
    def instrada(route):
        u = route.request.url
        host = u.split('/')[2].split(':')[0]
        if host == HOST:
            if '/api/t' in u:
                try: log['beacon'].append(json.loads(route.request.post_data or 'null'))
                except Exception: log['beacon'].append('non-json')
                return route.fulfill(status=204)
            return route.continue_()
        log['esterni'].append(host)
        if host == 'analytics.ahrefs.com': log['ahrefs'].append(u)
        return route.fulfill(status=200, content_type='application/javascript', body='')
    pg.route('**/*', instrada)
    pg.on('console', lambda m: log['errori'].append(m.text) if m.type == 'error' else None)
    pg.on('pageerror', lambda e: log['errori'].append(str(e)))
    return ctx, pg, log

def stato(pg, ctx):
    return {'cookie': [c['name'] for c in ctx.cookies()], 'doc': pg.evaluate('document.cookie'),
            'ls': pg.evaluate('Object.keys(localStorage)'), 'ss': pg.evaluate('Object.keys(sessionStorage)'),
            'sw': pg.evaluate("'serviceWorker' in navigator ? navigator.serviceWorker.getRegistrations().then(r=>r.length) : 0")}

with sync_playwright() as p:
    b = p.chromium.launch(args=[f'--host-resolver-rules=MAP {HOST} 127.0.0.1:{PORT}, MAP www.{HOST} 127.0.0.1:{PORT}'])
    for vp in VIEWPORT:
        for path in PAGINE:
            ctx, pg, log = apri(b, vp)
            pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle')
            prima = stato(pg, ctx); prima_ext = list(log['esterni'])
            for y in (500, 1500, 2600, 3600): pg.evaluate(f'scrollTo(0,{y})'); pg.wait_for_timeout(250)
            pg.evaluate('scrollTo(0,0)')
            if path in ('/', '/en/'):  # interazione: clic su una CTA (la navigazione esterna e' bloccata) e sul rail
                pg.evaluate("document.querySelector('#giornata .rail').scrollLeft=300"); pg.wait_for_timeout(200)
                pg.evaluate("document.querySelector('a[data-evento=\"whatsapp\"]').addEventListener('click',e=>e.preventDefault(),true)")
                pg.evaluate("document.querySelector('a[data-evento=\"whatsapp\"]').click()"); pg.wait_for_timeout(300)
            pg.wait_for_timeout(800)
            dopo = stato(pg, ctx)
            tag = f'[{vp} {path}] '
            check(tag + 'nessun cookie', not prima['cookie'] and not dopo['cookie'] and dopo['doc'] == '')
            check(tag + 'localStorage, sessionStorage e service worker vuoti', not dopo['ls'] and not dopo['ss'] and dopo['sw'] == 0, str(dopo))
            attesi = {'analytics.ahrefs.com'} if AHREFS == 'on' else set()
            check(tag + f'domini esterni contattati da soli: {sorted(set(log["esterni"])) or "nessuno"}', set(log['esterni']) <= attesi, str(set(log['esterni'])))
            check(tag + 'nessun errore in console', not log['errori'], str(log['errori'][:2]))
            check(tag + 'nessuno scroll orizzontale', pg.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            if path in ('/', '/en/'):
                ammessi = {'l', 'w', 'e'}
                bad = [x for x in log['beacon'] if not isinstance(x, dict) or not set(x) <= ammessi]
                chiavi_ev = {k for x in log['beacon'] if isinstance(x, dict) for ev in x.get('e', []) for k in ev}
                check(tag + 'payload statistiche: solo chiavi previste (' + ','.join(sorted(chiavi_ev)) + ')', not bad and chiavi_ev <= {'t', 'r', 'u', 'o', 'n', 'p'}, str(bad))
                blob = json.dumps(log['beacon'])
                check(tag + 'payload senza indirizzo, percorso, query, user agent', 'http' not in blob and 'iPhone' not in blob and '?' not in blob)
                check(tag + 'invia visita, clic e sezioni', any(ev.get('t') == 'pv' for x in log['beacon'] for ev in x['e']) and any(ev.get('t') == 'c' for x in log['beacon'] for ev in x['e']))
                pv = [ev for x in log['beacon'] for ev in x['e'] if ev.get('t') == 'pv']
                check(tag + 'la visita invia lo stato aperto/chiuso (o=0|1)', bool(pv) and all(ev.get('o') in (0, 1) for ev in pv), str(pv))
                if AHREFS == 'on': check(tag + 'script Ahrefs richiesto', len(log['ahrefs']) == 1)
                else: check(tag + 'script Ahrefs assente', not log['ahrefs'] and 'ahrefs' not in pg.content().lower())
            ctx.close()
    # DNT e GPC: nessuna richiesta di statistiche, nessuno script di terzi
    for nome, init in (('DNT', "Object.defineProperty(navigator,'doNotTrack',{get:()=>'1'})"),
                       ('GPC', "Object.defineProperty(navigator,'globalPrivacyControl',{get:()=>true})"),
                       ('DNT+GPC', "Object.defineProperty(navigator,'doNotTrack',{get:()=>'1'});Object.defineProperty(navigator,'globalPrivacyControl',{get:()=>true})")):
        for path in ('/', '/en/'):
            ctx, pg, log = apri(b, 'mobile', init)
            pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle'); pg.evaluate('scrollTo(0,2000)'); pg.wait_for_timeout(800)
            pg.evaluate("document.querySelector('a[data-evento=\"telefono\"]').addEventListener('click',e=>e.preventDefault(),true);document.querySelector('a[data-evento=\"telefono\"]').click()"); pg.wait_for_timeout(500)
            check(f'[{nome} {path}] nessuna statistica e nessun terzo', not log['beacon'] and not log['ahrefs'], str(log['beacon'])[:80])
            ctx.close()
    if AHREFS == 'on':  # riattivazione futura: ad Ahrefs deve andare il solo percorso, mai query o frammento
        for path in ('/', '/en/'):
            ctx, pg, log = apri(b, 'mobile')
            pg.goto(f'http://{HOST}:{PORT}{path}?utm_source=instagram&nome=PROVA#giornata', wait_until='networkidle'); pg.wait_for_timeout(500)
            attr = pg.evaluate("(document.querySelector('script[data-key]')||{getAttribute:()=>null}).getAttribute('data-page-location')")
            check(f'[{path}] Ahrefs (se acceso): data-page-location e\' solo il percorso', attr == path, str(attr))
            ctx.close()
    # evento Halloween (temporaneo): pannello di prenotazione, messaggio WhatsApp, stato la sera del 31, sparizione dopo il 31
    for path, en in (('/', False), ('/en/', True)):
        ctx, pg, log = apri(b, 'mobile')
        pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle'); pg.wait_for_timeout(300)
        tag = f'[Halloween {path}] '
        check(tag + 'striscia, sezione e pannello presenti', pg.locator('#hw-strip').count() == 1 and pg.locator('#halloween').count() == 1 and pg.locator('#hw-pan').count() == 1)
        check(tag + 'la hero non e\' toccata (foto e frase di apertura al loro posto)', pg.locator('.hero-photo').count() == 1 and pg.locator('.tag').count() == 1)
        pg.locator('#hw-strip [data-hw-open]').click(); pg.wait_for_timeout(500)
        check(tag + 'il pannello si apre', pg.evaluate("document.documentElement.classList.contains('hw-open')") and pg.locator('#hw-pan').is_visible())
        pg.locator('.hw-chip', has_text='4').first.click(); pg.locator('.hw-chip', has_text=('8 pm' if en else '20:00')).click()
        href = pg.evaluate("document.getElementById('hw-wa').href")
        import urllib.parse
        testo = urllib.parse.unquote(href.split('text=')[1]) if 'text=' in href else ''
        attesa = ["Hi! I'd like to book for Halloween, Saturday 31 October: we're 4, around 8 pm."] if en else ['Ciao! Vorrei prenotare per Halloween, sabato 31 ottobre: siamo in 4, verso le 20:00.']
        check(tag + 'link WhatsApp giusto e messaggio nella lingua della pagina', href.startswith('https://wa.me/393481897496?text=') and testo == attesa[0], testo)
        check(tag + 'nessuna richiesta esterna prima del clic su WhatsApp', not log['esterni'], str(log['esterni']))
        pg.keyboard.press('Escape'); pg.wait_for_timeout(400)
        check(tag + 'Esc chiude il pannello', not pg.evaluate("document.documentElement.classList.contains('hw-open')"))
        ctx.close()
    for nome, quando, atteso in (('prima delle 18', '2026-10-31T16:00:00+01:00', ('Riapriamo stasera alle 18:00', 'Reopening tonight at 6 pm')),
                                 ('dopo le 18', '2026-10-31T19:30:00+01:00', ('Stasera siamo aperti per Halloween', 'Open tonight for Halloween'))):
        for path, i in (('/', 0), ('/en/', 1)):
            ctx, pg, log = apri(b, 'mobile')
            pg.clock.install(time=quando)
            pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle'); pg.wait_for_timeout(300)
            check(f'[31/10 {nome} {path}] stato nella pillola: "{atteso[i]}"', atteso[i] in pg.inner_text('#status-text').replace('\xa0', ' '), pg.inner_text('#status-text'))
            ctx.close()
    for path in ('/', '/en/'):
        ctx, pg, log = apri(b, 'mobile')
        pg.clock.install(time='2026-11-01T09:00:00+01:00')
        pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle'); pg.wait_for_timeout(300)
        check(f'[dopo il 31 ottobre {path}] l\'evento sparisce da solo dalla pagina', pg.locator('.hw').count() == 0 and pg.locator('#halloween').count() == 0)
        ctx.close()
    for path in ('/privacy/', '/en/privacy/'):
        ctx, pg, log = apri(b, 'mobile')
        pg.goto(f'http://{HOST}:{PORT}{path}', wait_until='networkidle')
        check(f'[{path}] la pagina privacy non porta l\'evento', pg.locator('.hw').count() == 0)
        ctx.close()
    # localhost: l'analytics non parte
    ctx, pg, log = apri(b, 'mobile')
    pg.goto(f'http://localhost:{PORT}/', wait_until='networkidle'); pg.wait_for_timeout(600)
    check('[localhost] nessuna statistica e nessun terzo', not log['beacon'] and not log['ahrefs'])
    ctx.close()
    # pannello: all'apertura non scrive nulla
    ctx, pg, log = apri(b, 'mobile')
    pg.goto(f'http://{HOST}:{PORT}/pannello/', wait_until='networkidle'); pg.wait_for_timeout(500)
    s = stato(pg, ctx)
    check('[pannello] all\'apertura niente cookie/storage, niente statistiche pubbliche, niente terzi', not s['cookie'] and not s['ls'] and not s['ss'] and not log['beacon'] and not log['esterni'], str(s))
    ctx.close(); b.close()
print(f'\n{ok} superati, {ko} falliti (Ahrefs: {AHREFS})')
sys.exit(1 if ko else 0)
