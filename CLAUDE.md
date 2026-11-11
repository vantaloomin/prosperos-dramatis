# Prospero's Dramatis

The suite's character creator: one character, made once with AI help, that Prospero's Companion, Adventure and Dungeon
(vantaloomin/prosperos-companion, -adventure, -dungeon) each load in their own shape. It started as Companion's
character creator.

- Layout mirrors Worldsmith: the app lives in `Program/` (Python package `dramatis/`, FastAPI on port 8815; React +
  Vite screen in `src/`, dev server 5207); `Windows/` holds only the double-click scripts.
- `dramatis/formats/` is the apps' own code, vendored (their request models, Companion's card reader and slider
  rules). Never edit it here: change it in that app, then run
  `python scripts/sync_format.py --companion <checkout> --adventure <checkout> --dungeon <checkout>`. CI's `formats`
  job fails when a copy differs from the app at the commit `SOURCE.json` records; an app's newer main arrives as the
  daily `sync-formats` workflow's own PR on `sync/formats` (or an issue, when the sync cannot run).
  `dramatis/stand_ins/` replaces the few modules those files import that would pull in a whole app.
- `dramatis/character.py` is the shared character and each app's shape of it, checked with that app's own models.
  A new field goes there first, with the tightest limit of the apps that read it.
- A character whose Companion relationship is `persona` is the user themself: Companion's shape of them is its
  `PersonaInput` (`{'persona': …}`), and drafting, the form and the assistant leave Companion's everyday life out.
- `dramatis/casts.py` is the Cast layer: a story's people as a two-layer four-corner opposition, saved in
  `casts/<id>.json` beside the library and pointing at characters by id. Resonance candidates and checks are computed
  there with no model; only structure is a hard error. Genres, group types, axes and tags are data
  (`dramatis/data/cast_*.json`), so a new template is a JSON entry. Routes are in `cast_routes.py`.
- The Details of how they look are settled before the model writes their Appearance (`dramatis/looks.py`): what the
  user's words speak of the model reads into the fields, the rest are rolled first with Companion's own looks banks
  (vendored `formats/companion/looks.py` and `dating.py`), and `Character.looks_from` marks each as From their words or
  Rolled, as the sliders are marked, until the user edits it.
- Names are Companion's (`dramatis/names.py`): its name banks and birth-year lists (vendored `formats/companion/
  naming.py`, `data/names.json`, `data/given_names.json`) and its own `generators.name`, vendored as a part (sync_format's
  `parts`: only the named definitions of a file too tied to Companion to vendor whole). `Place` reads a Companion city
  from the setting. A draft with Name empty chooses among drawn names; nothing the slop audit lists is offered; a stock
  or made-up name kept after the retry is swapped (`Roll.swaps`); a name the user typed is never touched.
- A character's depth (`interview`, `arc`, `secret`, `psyche`) is optional and no app has a field for it: the app
  shapes fold it into fields they read. The secret goes everywhere the character does, so they can keep it. The interview's routes live in
  `dramatis/interview.py`, its own router; Help me write reaches nested fields by dotted keys (`arc.lie`,
  `psyche.was`), listed in `slop.DEPTH`. A quick-start draft writes every section, depth and an ordinary secret
  included (`Shape(whole=True)`): a field still empty after the one retry comes back in `missing`, and the form names it.
- Another app's character file is `dramatis/imports.py`: Companion's own importer (vendored `formats/companion/imports/`)
  reads it, then it opens in the form with no model (headed lines to their fields) or goes to the paste box for the
  split, both behind the Paste path's checks. What the card has that Dramatis doesn't make is `Character.card`
  (`CardParts`), put back in every export and kept out of prompts by `drafting.for_model`.
- The Cast board is `src/cast/` with its calls and pure cast edits in `src/castApi.ts`. App keeps each open board
  (unsaved edits survive leaving it) and the corner a drafted character goes to.
- The Cast board's AI help is `dramatis/cast_ai.py` (routes under `/api/cast-ai`, prompts `prompts/cast-*.md`) and
  `src/cast/CastAi.tsx`, placed on the board by `src/cast/slots.tsx`; the edits they make live in `src/castApi.ts`.
  Every result goes onto the board in place as a proposal (`src/cast/boardProposals.tsx`) with Keep / Put back; it
  changes the board, never the cast file.
- The Sidebar Assistant (after Adventure's, which came from Companion's sidecar; both are built on their apps' stories,
  so it is ported, not vendored) is `dramatis/assistant.py` with `prompts/assistant.md`, and `src/assistant/` on the
  screen. It gets the live form, the form as its last answer left it and the focused field (`data-field` on each
  `Field`, the same keys as Help me write), and answers `{"reply", "edits"}`; each edit is a proposal on the form.
  A field it may edit is in `assistant.guides()`.
- Every model output for the character form (Help me write, the assistant, the interview, the split) is a proposal in
  `src/proposals.ts`: it stands in its field at once, marked, with Keep / Put back under it, and Save keeps what is
  still open. A model action is a `ModelButton` (bolt icon, Stop while it runs, `src/modelCall.ts`); a field's Help me
  write is the bolt `Field` draws from its `write` prop. Fields have labels only, no hint lines.
- A character form with unsaved changes is a draft in `src/drafts.ts` (by id, or `new-…` before its first save), kept
  in localStorage, so switching characters or reloading loses nothing; the library marks them and Discard drops one.
- Every model call goes through `dramatis/ai.py` `complete`, run with Companion's own providers (vendored in
  `formats/companion/providers`). Profiles and which one does each job (`writing`, `assistant`, `cast`) are
  `dramatis/profiles.py` (in settings.json, keys in the keyring), routes in `model_routes.py`; a caller names its job
  with `ai.doing(job)`. The Models screen is Companion's, ported to `src/models/`.
- The AI-slop audit on the form is `src/Audit.tsx`: Fix selected / Fix all go to `dramatis/fixes.py` (`/api/draft/fix`,
  `prompts/fix.md`), where the model answers only replacements for the marked spans and the server puts them in, so
  the rest of a field never changes; Ignore saves the words in `Character.ignored_flags`, which `slop.audit` leaves out.
- Browser autofill and password managers are off on every field: `src/noAutofill.ts` (started in `main.tsx`) marks each
  `input`, `textarea` and `select` as it appears, so a new field needs nothing.
- The server answers only this computer (`dramatis/local_only.py`): a Host or Origin that isn't localhost, 127.0.0.1
  or ::1 gets a 403 before any route, against DNS rebinding. Tests' `testserver` is let in by `conftest.py`.
- The model never saves anything: drafts go to the form for review, and only Save writes to the library.
- Before pushing, from `Program/`: `python -m ruff check .`, `python -m pytest -q`, `npm run build`.
- `main` takes changes through pull requests.
