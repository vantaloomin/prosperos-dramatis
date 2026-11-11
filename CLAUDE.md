# Prospero's Dramatis

The suite's character creator: one character, made once with AI help, that Prospero's Companion, Adventure and Dungeon
(vantaloomin/prosperos-companion, -adventure, -dungeon) each load in their own shape. It started as Companion's
character creator.

- Layout mirrors Worldsmith: the app lives in `Program/` (Python package `dramatis/`, FastAPI on port 8815; React +
  Vite screen in `src/`, dev server 5207); `Windows/` and `Mac/` hold only the double-click scripts (the Mac ones run
  `Program/scripts/macos/*.sh`, after Companion's; CI's `mac.yml` installs, launches and stops on a Mac). Both install
  from `Program/requirements.lock.txt`; a dependency change in `pyproject.toml` means writing it again (README,
  Development).
- `dramatis/formats/` is the apps' own code, vendored (their request models, Companion's card reader and slider
  rules). Never edit it here: change it in that app, then run
  `python scripts/sync_format.py --companion <checkout> --adventure <checkout> --dungeon <checkout>`. CI's `formats`
  job fails when a copy differs from the app at the commit `SOURCE.json` records; an app's newer main arrives as the
  daily `sync-formats` workflow's own PR on `sync/formats` (or an issue, when the sync cannot run).
  `dramatis/stand_ins/` replaces the few modules those files import that would pull in a whole app.
- `dramatis/character.py` is the shared character and each app's shape of it, checked with that app's own models.
  A new field goes there first, with the tightest limit of the apps that read it, then one `Spec` in
  `dramatis/fields.py` (its label, section, Help me write words; the limit is read from the model), then
  `python scripts/screen_types.py`, which writes `src/generated/` (the character's TypeScript types and the registry).
  The form takes a field by `field="about"`; a test fails when `src/generated/` is out of date.
  An app with no field for part of the character gets it folded into a text it reads (`folded`): Companion's
  background, Adventure's and Companion's How they see themselves, and Dungeon's About you (`dungeon_about`).
- A character whose Companion relationship is `persona` is the user themself: Companion's shape of them is its
  `PersonaInput` (`{'persona': …}`), and drafting, the form and the assistant leave Companion's everyday life out.
- `dramatis/casts.py` is the Cast layer: a story's people as a two-layer four-corner opposition, saved in
  `casts/<id>.json` beside the library and pointing at characters by id. Resonance candidates and checks are computed
  there with no model; only structure is a hard error. Genres, group types, axes and tags are data
  (`dramatis/data/cast_*.json`), so a new template is a JSON entry. Routes are in `cast_routes.py`. A card exported
  from a cast carries that character's place in it (`casts.context_for`: `extensions.prospero.cast` and the
  description's "Their place in" paragraph, by name, never by id); the single-character card has none.
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
- `dramatis/library_tools.py` (routes under `/api/library`) duplicates, backs up and restores (a zip of the record
  files; restore only adds what is missing, through `records.migrated`), opens a cast file as a new cast (ids it
  carries that this library lacks come in as new characters, `relinked`), and names the casts that use a character.
  Search is `library.listing(search)`, over the character's text values. `src/LibraryTools.tsx` is the screen's part.
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
  A field it may edit is in `assistant.guides()`. It sees the secret only when the focus or message is about how they
  are inside, and then each edit to a field anyone reads is written again by Help me write without it (`covered`);
  the fields Help me write doesn't write, and the split, get `dramatis/echo.py`'s check. A message asking for a minor
  is refused before the model (`adults.adult_request`), every text it writes goes through `adults.says_young`, and
  `drafting.for_model` leaves out lines on the form that talk to the model (`unspoken`).
- Every model output for the character form (Help me write, the assistant, the interview, the split) is a proposal in
  `src/proposals.ts`: it stands in its field at once, marked, with Keep / Put back under it, and Save keeps what is
  still open. A model action is a `ModelButton` (bolt icon, Stop while it runs, `src/modelCall.ts`); a field's Help me
  write is the bolt `Field` draws from its `write` prop. Fields have labels only, no hint lines.
- Characters and casts are kept by `dramatis/records.py`: whole files through a temp file of their own, a `schema`
  number with ordered `MIGRATIONS` run on load (a removed or renamed field is one more step there, never a hand strip),
  and a `revision` per save; a save sent with an older revision gets 409 `stale` and the screen asks before saving
  over (`savedOver` in `src/api.ts`).
- A character form with unsaved changes is a draft in `src/drafts.ts` (by id, or `new-…` before its first save), kept
  in localStorage, one entry per draft (another tab's arrive by the `storage` event), so switching characters or
  reloading loses nothing; the library marks them and Discard drops one. Cast boards with changes not saved are kept
  the same way (`castStore`).
- Each view has an address in the URL's hash (`src/address.ts`: `#/character/<id>`, `#/draft/<key>`, `#/cast/<id>`,
  `#/new-cast`, `#/models`), so a reload stays and Back and Forward move between views; a first save replaces the
  unsaved address. A new view in `App` needs a case there.
- Stop stops the model: `dramatis/calls.py` middleware sets the request's `gone` event when the browser drops it, and
  `ai.run` cancels the provider's coroutine (hosted streams close, CLI processes end). A screen call names its run
  (`X-Dramatis-Run`, from `src/modelCall.ts`); `calls.step` records what a draft is doing for GET /api/progress/{run}.
- Every model call goes through `dramatis/ai.py` `complete`, run with Companion's own providers (vendored in
  `formats/companion/providers`). Profiles and which one does each job (`writing`, `assistant`, `cast`) are
  `dramatis/profiles.py` (in settings.json, keys in the keyring), routes in `model_routes.py`; a caller names its job
  with `ai.doing(job)`. The Models screen is Companion's, ported to `src/models/`.
- `Character.written` keeps the fields a model wrote (form keys), saved with them: the audit of a brought character
  reads only those, and Help me write and the assistant hold only the other fields as the user's own words
  (`drafting.own_words`).
- The AI-slop audit on the form is `src/Audit.tsx`: Fix selected / Fix all go to `dramatis/fixes.py` (`/api/draft/fix`,
  `prompts/fix.md`), where the model answers only replacements for the marked spans and the server puts them in, so
  the rest of a field never changes; Ignore saves the words in `Character.ignored_flags`, which `slop.audit` leaves out.
- Browser autofill and password managers are off on every field: `src/noAutofill.ts` (started in `main.tsx`) marks each
  `input`, `textarea` and `select` as it appears, so a new field needs nothing.
- The server answers only this computer (`dramatis/local_only.py`): a Host or Origin that isn't localhost, 127.0.0.1
  or ::1 gets a 403 before any route, against DNS rebinding. Tests' `testserver` is let in by `conftest.py`.
- The model never saves anything: drafts go to the form for review, and only Save writes to the library.
- Every model call that wants JSON back goes through `dramatis/asking.py` (`ask`: the prompt file filled, the reply
  parsed with its dashes made commas, a 5'10" height mended and missing closing brackets added, one retry, `Unusable` when it still isn't). The adults-only policy (ages, youthful wording, "not theirs")
  is `dramatis/adults.py`, used by every route that takes the user's words. `drafting.py` is the drafts themselves.
- The character form is `src/Editor.tsx` with its sections in `src/editor/sections.tsx` and the export and Works in
  rows in `src/editor/status.tsx`.
- `python -m dramatis --stub` (`dramatis/stub.py`) swaps `ai.complete` for fixed answers chosen by a mark each prompt
  carries (`ANSWERS`; `tests/test_stub.py` checks every prompt still gets its own), in a throwaway library with the
  profile in memory. CI's `walk` job runs `tests/walk/walk.mjs` (Playwright) against it; a new screen flow gets a step
  there. The screen's pure logic has Vitest tests in `tests/screen/` (`npm test`).
- Before pushing, from `Program/`: `python -m ruff check .`, `python -m pytest -q`, `npm test`, `npm run build`.
- `main` takes changes through pull requests.
- A release: the version agrees in `package.json`, `pyproject.toml` and `dramatis/__init__.py`, its notes are
  `Program/docs/releases/v<version>.md` (and a CHANGELOG.md section), and the Release workflow tags it after CI and
  the Mac job pass. Never run it without Vanta's yes.
