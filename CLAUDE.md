# Prospero's Dramatis

The suite's character creator: one character, made once with AI help, that Prospero's Companion, Adventure and Dungeon
(vantaloomin/prosperos-companion, -adventure, -dungeon) each load in their own shape. It started as Companion's
character creator.

- Layout mirrors Worldsmith: the app lives in `Program/` (Python package `dramatis/`, FastAPI on port 8815; React +
  Vite screen in `src/`, dev server 5207); `Windows/` holds only the double-click scripts.
- `dramatis/formats/` is the apps' own code, vendored (their request models, Companion's card reader and slider
  rules). Never edit it here: change it in that app, then run
  `python scripts/sync_format.py --companion <checkout> --adventure <checkout> --dungeon <checkout>`. CI's `formats`
  job fails when an app's main has moved on. `dramatis/stand_ins/` replaces the few modules those files import that
  would pull in a whole app.
- `dramatis/character.py` is the shared character and each app's shape of it, checked with that app's own models.
  A new field goes there first, with the tightest limit of the apps that read it.
- `dramatis/casts.py` is the Cast layer: a story's people as a two-layer four-corner opposition, saved in
  `casts/<id>.json` beside the library and pointing at characters by id. Resonance candidates and checks are computed
  there with no model; only structure is a hard error. Genres, group types, axes and tags are data
  (`dramatis/data/cast_*.json`), so a new template is a JSON entry. Routes are in `cast_routes.py`.
- A character's depth (`interview`, `arc`, `secret`, `psyche`) is optional and no app has a field for it: the app
  shapes fold it into fields they read, and a card drops the secret unless `?secret=1`. The interview's routes live in
  `dramatis/interview.py`, its own router; Help me write reaches nested fields by dotted keys (`arc.lie`,
  `psyche.was`), listed in `slop.DEPTH`.
- The Cast board is `src/cast/` with its calls and pure cast edits in `src/castApi.ts`. App keeps each open board
  (unsaved edits survive leaving it) and the corner a drafted character goes to. AI actions go in `src/cast/slots.tsx`.
- The Sidebar Assistant (after Adventure's, which came from Companion's sidecar; both are built on their apps' stories,
  so it is ported, not vendored) is `dramatis/assistant.py` with `prompts/assistant.md`, and `src/assistant/` on the
  screen. It gets the live form, the form as its last answer left it and the focused field (`data-field` on each
  `Field`, the same keys as Help me write), and answers `{"reply", "edits"}`; edits land in the form, marked, with Undo.
  A field it may edit is in `assistant.guides()`.
- The model never saves anything: drafts go to the form for review, and only Save writes to the library.
- Before pushing, from `Program/`: `python -m ruff check .`, `python -m pytest -q`, `npm run build`.
- `main` takes changes through pull requests.
