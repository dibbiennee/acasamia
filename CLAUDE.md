@.claude/design.md

# A casa mia — progetto

Sito del bistrot "A casa mia", Civitavecchia. HTML/CSS/JS vanilla, niente
framework, niente build step npm. Deploy statico su Vercel (team `edo14`).

Pipeline: `source/demo.html` (unico file che si modifica a mano) → `build.py`
(estrae le immagini, genera `index.html` e `public/img/`) → deploy. Vedi
`aggiornamento-per-claude-code.md` nella cronologia per le regole già concordate
su cosa build.py deve e non deve toccare.
