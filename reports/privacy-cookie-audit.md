# Audit privacy e cookie: A casa mia

Data: 13 ottobre 2026. Branch: `audit/privacy-cookie-hardening` (nessun merge su `main`, nessun deploy, nessuna modifica a Vercel o Redis in produzione).

Questo documento distingue le **verifiche tecniche** (fatte qui, con prove) dalle **decisioni giuridiche** (da validare con un consulente). Non attesta la conformità del sito al GDPR.

Stati usati: VERIFICATO TECNICAMENTE · CORRETTO · DA CONFERMARE CON IL TITOLARE · DA VALIDARE CON IL CONSULENTE · NON VERIFICABILE · BLOCCANTE PER IL RILASCIO.

## A. Sintesi

**Stato iniziale (produzione al 12 ottobre).** Sito senza cookie né storage; statistiche proprie anonime; lo script Ahrefs Web Analytics caricato in automatico (se non ci sono DNT/GPC); informativa IT/EN che dichiarava, per Ahrefs, "senza cookie", "paese ricavato dall'IP", "per conto nostro" e "nessun identificativo per visitatore" (quest'ultima riferita alle sole statistiche proprie).

**Problemi individuati**

| # | Problema | Stato |
|---|---|---|
| 1 | Ahrefs: la documentazione ufficiale descrive un **codice visitatore pseudonimo giornaliero** (hash di IP + user agent + valore che cambia ogni 24 ore), posizione a livello di **città**, URL **con parametri**, lingua, schermo, user agent. L'informativa non lo diceva e parlava di "paese" | CORRETTO nel testo; trattamento in sé **DA VALIDARE CON IL CONSULENTE** |
| 2 | Ahrefs: durata di conservazione, luogo di trattamento, ruolo (responsabile o titolare), accordo sul trattamento dati e supporto a DNT non documentati dal fornitore | NON VERIFICABILE |
| 3 | Ahrefs: lo script invia l'URL completo, quindi anche parametri come `?nome=...` | CORRETTO (all'estero va solo il percorso) |
| 4 | **Bug dell'analytics proprio:** la visita non inviava lo stato aperto/chiuso, quindi tutte le visite erano contate "chiuso" (dal rilascio del 6 ottobre, commit `11a6f29`) | CORRETTO (e coperto da test) |
| 5 | Commento in `api/_lib.js` ancora riferito a codici giornalieri e HyperLogLog, già rimossi | CORRETTO |
| 6 | Informativa: ruoli (art. 28), garanzie di trasferimento e rete di distribuzione dichiarati in modo più sicuro del verificato | CORRETTO (testo attenuato; verifiche in sezione H) |

**Decisione su Ahrefs.** Nel branch Ahrefs è **spento di default** (interruttore in `build.py`, `AHREFS_ANALYTICS=1` per riaccenderlo), perché il quadro documentale è incompleto e il trattamento comprende un identificativo pseudonimo giornaliero che l'informativa precedente non descriveva. Le due versioni del testo (Ahrefs acceso/spento) convivono nei file sorgente: riaccenderlo non richiede di riscrivere nulla. Se la società vuole tenerlo acceso in produzione, serve prima la validazione della sezione J.

**Stato rilascio.** Con Ahrefs spento non risultano problemi tecnici bloccanti. In produzione oggi Ahrefs è ancora acceso: finché questo branch non viene pubblicato, il sito dichiara e fa quanto descritto nella versione del 12 ottobre. **BLOCCANTE PER IL RILASCIO** solo se si decide di tenere Ahrefs acceso senza chiudere i punti 2 e 3 della sezione J.

## B. Inventario dei trattamenti

| Componente | Dati trattati | Finalità | Destinatario | Conservazione | Evidenza | Non verificabile |
|---|---|---|---|---|---|---|
| Statistiche proprie (`/api/t`) | pagina vista, lingua, larghezza schermo (→ telefono/tablet/computer), ora di Roma, categoria di provenienza (dal solo nome di dominio del referrer), `utm_source` (max 20 caratteri `a-z0-9_-`), stato aperto/chiuso, clic su pulsanti con sezione, sezioni raggiunte, scorrimento schede | Capire l'uso del sito | Upstash (archivio) | Contatori per giorno, scadenza 400 giorni (`EXPIRE`) | `api/t.js`, test API 14/14, test browser sul payload | Regione effettiva di Upstash |
| Log tecnici dell'hosting | IP, data/ora, percorso, user agent (dichiarato nell'informativa) | Funzionamento e sicurezza | Vercel | Periodo stabilito da Vercel | DPA Vercel (sezione H) | Durata effettiva dei log sul piano in uso |
| Regola anti-abuso sul bordo | IP, conteggio richieste a `/api/` (60/min) | Proteggere le funzioni | Vercel | Finestra di 1 minuto | Configurazione verificata il 6/10 | Retention interna Vercel |
| Blocco tentativi pannello | IP, in memoria della funzione, 10 minuti | Proteggere la password | Nessuno (memoria) | Fino a riavvio o 10 minuti | `api/_lib.js` | Si azzera a ogni deploy (debito noto) |
| Pannello `/pannello/` | Password digitata (in `sessionStorage` dopo il login) | Accesso del titolare | Nessuno | Fino a chiusura scheda | `source/pannello.html` | Solo titolare e agenzia |
| Contatti (telefono, WhatsApp, e-mail) | Dati forniti da chi scrive | Rispondere | Meta (WhatsApp), provider e-mail | Non definita | Informativa | Tempi di conservazione |
| Ahrefs Web Analytics (spento nel branch) | Vedi sezione D | Statistiche di terzi | Ahrefs | Non dichiarata dal fornitore | Codice dello script, documentazione ufficiale, payload catturato | Retention, luogo, ruolo, DPA |

## C. Cookie e storage

Verifica su pagine servite in locale con il dominio di produzione mappato su 127.0.0.1 (le regole "solo sul dominio vero" valgono), richieste esterne bloccate, Chromium su desktop (1280×900) e mobile (390×844), contesto pulito. Pagine: `/`, `/en/`, `/privacy/`, `/en/privacy/`, `/pannello/`. Dopo caricamento, scroll, rail laterale, clic su CTA.

| Origine | Nome/chiave | Finalità | Durata | Quando | Soggetto | Tecnico? | Conseguenza |
|---|---|---|---|---|---|---|---|
| Cookie del sito | nessuno | n.a. | n.a. | mai | n.a. | n.a. | Nessun banner necessario per il sito stesso |
| Cookie del provider (Vercel) | nessuno osservato (nessun `Set-Cookie`) | n.a. | n.a. | mai | n.a. | n.a. | Controllare di nuovo se cambia piano o si attivano funzioni Vercel |
| `localStorage` / IndexedDB / service worker | nessuno | n.a. | n.a. | mai | n.a. | n.a. | Nessuna indicazione necessaria oltre a quella già in informativa |
| `sessionStorage` pubblico | nessuno | n.a. | n.a. | mai | n.a. | n.a. | Idem |
| `sessionStorage` nel pannello | `pw` | Mantenere l'accesso del titolare durante la sessione | Fino a chiusura della scheda | Dopo un login riuscito | Codice del sito, solo `/pannello/` | Sì (funzione richiesta dal titolare) | Non riguarda i visitatori; il test conferma che all'apertura non scrive nulla |
| Ahrefs (se acceso) | nessuno | n.a. | n.a. | mai | n.a. | n.a. | Il codice dello script non usa cookie né storage; verificato anche con prova |

**Risultato:** VERIFICATO TECNICAMENTE. 64 controlli del browser superati su 64 (Ahrefs spento) e 64 su 64 (Ahrefs acceso) al momento dell'audit; dopo i test mirati della release candidate sono 68 e 70, comprese le pagine privacy.

## D. Ahrefs

**Come è caricato (produzione al 12 ottobre).** Script inline che inietta `https://analytics.ahrefs.com/analytics.js` con `data-key`, solo su `acasamiacivitavecchia.it` e `www.`, e solo se non sono attivi DNT o GPC. L'iniezione dinamica è accettata dal controllo di installazione di Ahrefs ("Script installed").

**Cosa fa lo script (codice letto, 6.947 caratteri).** Nessuna scrittura di cookie o storage. Legge `screen.width/height`, `navigator.language(s)` e `navigator.webdriver` (se `true` non invia). Invia con `POST` a `analytics.ahrefs.com/api/event` un evento `pageview` e, se configurato, altri eventi. Non controlla DNT né GPC: il rispetto è affidato al nostro caricamento condizionale.

**Payload catturato** (copia locale dello script, richiesta intercettata, nessun contatto con Ahrefs):
`{"n":"pageview","u":"<URL>","l":["it-IT"],"k":"<chiave del sito>","r":<referrer>,"sw":390,"sh":844,"sr":1,"t":"<titolo pagina>"}`.
Con la configurazione di produzione `u` conteneva anche la query (`?utm_source=instagram&nome=PROVA`). Nel branch (script riacceso a prova) `data-page-location` è impostato sul solo percorso: `u` diventa `/`.

**Documentazione ufficiale** ([guida Ahrefs Web Analytics](https://help.ahrefs.com/en/articles/10247870-about-ahrefs-web-analytics), consultata il 13/10/2026):
- nessun cookie né identificatori persistenti;
- l'IP serve a stimare la posizione a livello di città; "gli IP grezzi vengono scartati e mai conservati";
- per contare i visitatori unici si genera un **ID pseudonimo giornaliero** `hash(valore_giornaliero + IP + user agent)`, con valore rigenerato ogni 24 ore e vecchi valori cancellati; non permette di seguire il visitatore tra giorni;
- raccolti: URL con parametri, referrer, `Accept-Language`, dimensioni schermo, user agent, eventi (pageview, clic, invio moduli);
- il sito resta responsabile degli obblighi di legge.

**Non indicato dal fornitore:** tempi di conservazione di URL, referrer, eventi e dati aggregati; luogo di trattamento; supporto a DNT; consenso; accordo sul trattamento dati per questo servizio. La [privacy policy generale](https://ahrefs.com/privacy-policy) (consultata il 13/10/2026) indica sede a Singapore (Ahrefs Pte. Ltd.), dati "trasferiti e conservati negli Stati Uniti", garanzie UE-USA (Data Privacy Framework) e clausole contrattuali standard, uso possibile delle informazioni per "addestrare modelli di machine learning", e non dice se si applica ai dati raccolti sui siti dei clienti.

**Discrepanze con l'informativa del 12 ottobre:** (1) "paese" invece di città; (2) nessuna menzione dell'ID pseudonimo giornaliero; (3) "elabora per conto nostro" senza conferma del ruolo; (4) sede indicata come Singapore senza dire che i dati risultano conservati negli Stati Uniti; (5) URL con parametri inviati ad Ahrefs.

**Decisione.** Spegnere Ahrefs in attesa di validazione (non sostituito con altri servizi). Configurazione minima disponibile e applicata se si riaccende: percorso senza query via `data-page-location`. Non esiste un'opzione dello script per disattivare l'ID giornaliero o l'uso dell'IP. Cosa non è verificabile da browser o repository: la conservazione reale, i sub-responsabili, la sede dei server, l'uso dei dati per l'addestramento, il comportamento in presenza di DNT lato Ahrefs.

**Testo dell'informativa se acceso:** sezione "Statistiche di Ahrefs" separata da quella proprietaria, con ID pseudonimo, città, parametri esclusi, assenza di tempi dichiarati. Nessuna affermazione di anonimato.

## E. Analytics proprietario

**Flusso:** pagina → `navigator.sendBeacon('/api/t')` (testo JSON, chiavi `l`, `w`, `e`) → funzione serverless (`fra1`) → Upstash Redis via REST (`HINCRBY` su `s:AAAA-MM-GG`, `EXPIRE` 400 giorni) → `/api/stats` (password) → `/pannello/`.

**Controlli sul codice e sui test (API 14/14, browser 64/64):**
- **DNT, GPC, entrambi:** il browser non invia nulla e il server, anche chiamato direttamente con `DNT: 1` o `Sec-GPC: 1`, non scrive. VERIFICATO TECNICAMENTE.
- **Payload malformato o troppo grande (>4.000 caratteri), più di 12 eventi, non array:** scartato.
- **Chiavi non ammesse:** eventi, sezioni e posizioni fuori elenco sono ignorati o ricondotti a `altro`.
- **Dati personali nel corpo** (nome, e-mail, telefono, IP, testo libero, URL con query nel referrer): non finiscono in nessun comando verso l'archivio.
- **IP e user agent:** mai scritti. Il referrer viene ridotto a una categoria.
- **Origine non ammessa, bot, senza user agent, metodo diverso da POST:** non contano.
- **`/api/stats`:** 401 senza password e senza leggere l'archivio; con password giusta la risposta non contiene "visitatori" né segreti; dopo 5 errori 429 anche con la password giusta.
- **Visite al pannello:** il pannello non contiene il codice di tracciamento pubblico: nessuna statistica all'apertura.
- **Retention:** scadenza 400 giorni verificata nel test.
- **Non reintrodotti:** hash di IP, sale, HyperLogLog, visitatori unici.

**Corretto:** il campo `o` (locale aperto/chiuso) mancava dalla visita (le visite risultavano tutte "chiuso"); ora la visita lo invia, come già facevano i clic. Il formato delle metriche non cambia.

**Note, non modificate:**
- `utm_source` è testo libero di massimo 20 caratteri `a-z0-9_-`: chi manipola l'indirizzo può scriverci qualcosa. Rischio basso, ma non è una allowlist (DA VALIDARE CON IL CONSULENTE se serve restringerlo).
- Il controllo dell'origine usa `Origin`/`Referer`, che chi chiama le API direttamente può falsificare: può gonfiare i contatori, non estrarre dati. La regola sul bordo limita a 60 richieste al minuto per IP.
- I log di errore della funzione non stampano il payload (il blocco `catch` è vuoto per scelta).

## F. Informative

Modifiche a `source/privacy_it.html` e `source/privacy_en.html` (la data passa al 13 ottobre perché il contenuto è stato aggiornato e verificato oggi):
1. Struttura a blocchi con e senza Ahrefs: l'informativa pubblicata segue lo stato reale del sito.
2. Con Ahrefs: sezione dedicata con l'ID pseudonimo giornaliero, la città, i parametri esclusi, "Ahrefs non indica tempi di conservazione precisi" e "secondo Ahrefs" davanti alle sue dichiarazioni.
3. "Chi tratta i dati per nostro conto" diventa "Fornitori coinvolti" e il ruolo (responsabile o titolare autonomo per i dati di servizio) è rimandato agli accordi, perché per Vercel la documentazione lo distingue.
4. Trasferimenti: tolto il riferimento generico a "decisione di adeguatezza" e agli "accordi pubblicati dai fornitori"; indicate le clausole standard di Vercel (verificate) e rimandate agli accordi le garanzie degli altri.
5. Hosting: aggiunta la rete di distribuzione in più paesi e la frase "le nostre statistiche non leggono né salvano questo indirizzo".
6. Contatti: aggiunto che WhatsApp è gestito da Meta, che tratta i dati secondo la propria informativa.
7. Versione inglese allineata riga per riga all'italiana.
Non inventati: DPO, REA, capitale sociale, durate di conservazione.

## G. Banner e consenso

**Conclusione tecnica (Ahrefs spento):** il sito non usa cookie, non scrive nel browser e non carica servizi di terzi in automatico. Un banner di consenso non è motivato dalle evidenze, e non è stato aggiunto. Una sezione sui cookie è già nell'informativa ("non usa cookie e non scrive nulla nel tuo browser"). **DA VALIDARE CON IL CONSULENTE.**

**Se Ahrefs è acceso:** c'è uno strumento di terzi con IP, user agent, schermo e lingua, un ID pseudonimo giornaliero e conservazione non dichiarata. Le Linee guida cookie del Garante (provv. n. 231/2021) esonerano le statistiche di terzi dal consenso solo con condizioni stringenti (dati aggregati, nessun incrocio, riduzione del potere identificativo come il mascheramento dell'IP, garanzie contrattuali); non posso dimostrare queste condizioni per Ahrefs. **DA VALIDARE CON IL CONSULENTE** prima di accenderlo: se serve il consenso, il sito dovrebbe bloccare lo script finché l'utente non accetta (pari facilità di rifiuto, revoca, nessuna casella preselezionata); non è stato implementato perché Ahrefs è spento.

## H. Fornitori e contratti

| Fornitore | Verificato | Da confermare |
|---|---|---|
| Vercel | [DPA](https://vercel.com/legal/dpa): responsabile per i dati del cliente, titolare per i dati di servizio generati dalla piattaforma; clausole contrattuali standard 2021/914 (moduli 1-3); elaborazione primaria negli Stati Uniti; elenco dei sub-responsabili su security.vercel.com. Funzioni su Francoforte (`fra1` in `vercel.json`, visibile nell'intestazione `x-vercel-id`) | Durata dei log sul piano in uso; elenco sub-responsabili; che il DPA sia accettato per l'account (NON VERIFICABILE dal repository) |
| Upstash | Regione dichiarata Francoforte nella schermata di creazione mostrata dal titolare | NON VERIFICABILE: il DPA è un PDF che non ho potuto leggere; regione, sub-responsabili, garanzie di trasferimento, tetto di spesa |
| Ahrefs | Policy generale: Singapore, dati conservati negli USA, garanzie UE-USA e clausole standard | Ruolo, accordo sul trattamento dati, conservazione, addestramento di modelli |
| Aruba | Solo dominio e posta; nessun dato dei visitatori | Accordo sul trattamento per la posta |
| Satoshi Web | n.a. | Atto di nomina art. 28 prima della fattura |

Un DPA firmato non basta da solo a dimostrare la conformità complessiva.

## I. Test eseguiti

| Test | Comando | Esito |
|---|---|---|
| Analytics proprio e pannello (14 casi: visita, DNT, GPC, DNT+GPC, payload malformato, chiavi non ammesse, dati personali, IP/UA, origine, bot, GET, scadenza, 401, pannello pulito, 429) | `node tests/privacy/api.test.js` | 14/14 |
| Cookie, storage, richieste esterne, payload, DNT/GPC, localhost, pannello, console, overflow (4 pagine × desktop/mobile) | `python3 tests/privacy/browser_test.py` | 68/68 con Ahrefs spento (64 all'audit, +4 mirati) |
| Come sopra con Ahrefs acceso (build con `AHREFS_ANALYTICS=1`) | `python3 tests/privacy/browser_test.py --ahrefs on` | 70/70 |
| Payload di Ahrefs (copia locale dello script, richiesta intercettata) | script una tantum, in questa sezione | Catturato; query esclusa dopo la modifica |
| Tipografia dei testi (4 larghezze) | `controlla-testi.py` su `/`, `/en/`, `/privacy/`, `/en/privacy/` | Nessun problema |
| Audit di design (390 e 1280 px) | `audit-design.py` | 0 errori (avvisi già noti) |
| Build | `python3 build.py` (e con `AHREFS_ANALYTICS=1`) | Riuscita |

**Non eseguiti o non verificabili:** Safari e Firefox reali (solo Chromium); login reale al pannello (nessuna credenziale reale usata); lettura delle impostazioni Vercel e Upstash in produzione (nessun accesso richiesto in questo incarico); durata dei log Vercel; DPA Upstash e DPA Ahrefs. Procedura manuale suggerita: in un browser con DNT attivo aprire il sito, controllare in "Rete" dello strumento sviluppatori che non partano `/api/t` né richieste a terzi; poi disattivare DNT e ripetere.

**Nota onesta sui test di ieri e oggi:** prima di questo incarico ho aperto alcune volte il sito di produzione con un browser automatico (user agent di un telefono) per controllare cookie e script. Quelle visite possono aver aggiunto qualche conteggio alle statistiche del 12-13 ottobre. Questo audit, invece, non ha toccato la produzione.

## J. Questioni aperte

**Per il titolare**
1. Si vuole tenere Ahrefs sul sito pubblico? Se sì, chi firma l'accordo con Ahrefs?
2. Numero REA e capitale sociale per il footer.
3. Durate di conservazione desiderate per i messaggi ricevuti (e-mail, WhatsApp).
4. Piano Vercel in uso (durata dei log) e tetto di spesa Upstash.

**Per il consulente privacy**
1. Le statistiche proprie (contatori aggregati senza identificativi) rientrano nei dati anonimi o serve il legittimo interesse come scritto?
2. Senza cookie né terzi in automatico, conferma che non servono banner né cookie policy separata?
3. Ahrefs: l'ID pseudonimo giornaliero (hash di IP, user agent e valore giornaliero) più la città e lo user agent rientrano nell'esonero delle Linee guida cookie? Serve il consenso?
4. Ruoli e garanzie: Ahrefs (Singapore/USA), Vercel (clausole standard), Upstash (da leggere).
5. Durate di conservazione da indicare per log, contatti e statistiche di terzi.
6. `utm_source` libero: va ristretto a un elenco?
7. Estratti di recensioni Google mostrati nel sito: termini d'uso e autori.
8. DPO non dovuto?

## K. Riferimenti (consultati il 13/10/2026)

- Ahrefs, [About Ahrefs Web Analytics](https://help.ahrefs.com/en/articles/10247870-about-ahrefs-web-analytics)
- Ahrefs, [Privacy Policy](https://ahrefs.com/privacy-policy)
- Vercel, [Data Processing Addendum](https://vercel.com/legal/dpa)
- Upstash, [DPA](https://upstash.com/trust/dpa.pdf) (non leggibile automaticamente)
- Garante per la protezione dei dati personali, Linee guida cookie e altri strumenti di tracciamento, provv. n. 231 del 10 giugno 2021 (sintesi: [Osborne Clarke](https://www.osborneclarke.com/wp-content/uploads/2021/07/OC_Insight_TMT_Linee-guida-cookie-luglio-2021_-1.pdf)); il testo ufficiale va riletto sul sito del Garante.

## File modificati nel branch

`api/_lib.js` (commento), `build.py` (interruttore Ahrefs), `source/vestito.html` (stato aperto/chiuso sulla visita, blocco Ahrefs condizionato), `source/privacy_it.html` e `source/privacy_en.html`, pagine generate (`index.html`, `en/index.html`, `privacy/index.html`, `en/privacy/index.html`, `sitemap.xml`), nuovi: `tests/privacy/api.test.js`, `tests/privacy/browser_test.py`, `tests/privacy/release_check.py`, `reports/privacy-cookie-audit.md`.
