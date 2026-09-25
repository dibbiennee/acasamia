# Ricerca da fare: recensioni Google sul sito, si paga o no

Contesto: sito statico (HTML/CSS/JS vanilla, Vercel), bistrot locale a bassissimo
traffico. Blocco 4 del brief cliente vuole "valutazione media + estratti
recensioni" importati da Google. Devo capire il modo più economico e
sostenibile di farlo, prima di scegliere l'implementazione.

## Cosa verificare

1. **Google Places API (New) — endpoint Place Details.**
   - Restituisce davvero il testo delle recensioni e il rating medio?
   - Prezzo attuale per 1000 richieste (SKU "Place Details" vs "Place Details
     (Advanced)" — solo una delle due include le recensioni testuali).
   - C'è ancora un credito gratuito mensile (storicamente $200/mese) sufficiente
     a coprire un sito a bassissimo traffico se le chiamate sono poche (es. una
     al giorno via funzione server, non una per visitatore)?

2. **Limiti nei Termini di servizio Google.**
   - Quante recensioni si possono mostrare (storicamente max 5).
   - Obbligo di attribuzione/loghi Google e di badge "powered by Google".
   - Per quanto tempo si possono cachare/salvare i dati prima di dover
     ririchiamare l'API (Google vieta di conservarli indefinitamente).

3. **Alternativa a costo zero.**
   - Copiare a mano 3-5 recensioni vere + il rating medio in un file dati del
     sito (stesso pattern già usato per menù/orari), aggiornato da Edoardo ogni
     tanto. Nessuna chiave, nessun backend, nessun costo. Contro: non è "live".

4. **Widget di terze parti** (Elfsight, Trustindex, Tagembed, EmbedSocial,
   Reviews.io, Google Reviews Widget...).
   - Chi ha un piano gratuito realmente utilizzabile per un locale singolo
     (quante recensioni, che frequenza di aggiornamento)?
   - Costo del piano a pagamento se il gratuito è troppo limitato o ha
     branding non rimovibile.
   - Peso/impatto performance dello script che caricano (il sito attuale pesa
     ~110KB alla prima schermata, un widget esterno non deve vanificarlo).

5. **Via di mezzo: funzione server-side propria.**
   - Una funzione Vercel (cron una volta al giorno) che chiama l'API Google e
     scrive un JSON statico, invece di esporre la chiave lato client o di
     chiamare l'API a ogni visita. Se il costo API è già sotto il credito
     gratuito con una chiamata al giorno, è probabilmente la soluzione più
     pulita — ma introduce la prima funzione `/api/` sul progetto, quindi
     servono le due protezioni anti-abuso già previste per ogni funzione
     (regola nel CLAUDE.md globale di Edoardo).

## Cosa portare come risposta

Una tabella comparativa (opzione / costo reale mensile per questo caso d'uso /
sforzo di implementazione / quanto è "live") e una raccomandazione per un sito
di un singolo locale a basso traffico, non per un caso enterprise.
