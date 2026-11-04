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
  shapes fold it into fields they read. The secret goes everywhere the character does, so they can keep it. The interview's routes live in
  `dramatis/interview.py`, its own router; Help me write reaches nested fields by dotted keys (`arc.lie`,
  `psyche.was`), listed in `slop.DEPTH`.
- The Cast board is `src/cast/` with its calls and pure cast edits in `src/castApi.ts`. App keeps each open board
  (unsaved edits survive leaving it) and the corner a drafted character goes to.
- The Cast board's AI help is `dramatis/cast_ai.py` (routes under `/api/cast-ai`, prompts `prompts/cast-*.md`) and
  `src/cast/CastAi.tsx`, placed on the board by `src/cast/slots.tsx`; Apply and Undo edits live in `src/castApi.ts`.
  Every result is a proposal: Apply changes the board, never the cast file.
- The model never saves anything: drafts go to the form for review, and only Save writes to the library.
- Before pushing, from `Program/`: `python -m ruff check .`, `python -m pytest -q`, `npm run build`.
- `main` takes changes through pull requests.
