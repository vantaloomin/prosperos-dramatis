# Prospero's Dramatis

**Make a character once, with your model's help, and take them into any Prospero app.**

Dramatis is the character creator from [Prospero's Companion](https://github.com/vantaloomin/prosperos-companion),
standing on its own and made for the whole suite. A character you make here can be a companion in
[Companion](https://github.com/vantaloomin/prosperos-companion), or someone in a story in
[Adventure](https://github.com/vantaloomin/prosperos-adventure) or [Dungeon](https://github.com/vantaloomin/prosperos-dungeon).
Each character is saved once and exports as a character card that every one of those apps can read, and so can
SillyTavern, Chub, RisuAI and most other chat apps.

Work in progress: v0.1.0 is the first version.

## What it does

- **A few things to start.** Pick a name, gender, age and where and when they come from (all optional), plus which
  apps they're for. Your model writes the rest: who they are, their personality, voice, background, what they want and
  fear, skills, flaws and interests, and for Companion, their week, routine and life themes. You see the whole
  character before anything is saved. Under **More options** you can add an idea, a vibe, how they know you in
  Companion, and emotional edges, which are off unless you turn them on.
- **Bring a character you already have.** Paste notes, a bio or a scene, or open a character card (PNG or JSON, V1
  to V3). The model splits it into the fields and tells you which ones it had to fill in. You see the card's text
  before anything is sent anywhere. A card Dramatis made comes back whole, without asking the model at all.
- **The full form.** You can edit every field. **Help me write** rewrites any field to fit the rest of the character,
  and **Put back what was there** undoes it. **How they talk** (their words, rhythm and humour) and **How they sound** (the voice itself, for text to speech) are separate fields, so neither you nor a model mixes them up. There are also the five personality sliders (Roll again, or start from a
  four-letter type), Looks field by field, how others see them and how they see themselves, kind and lifespan, and
  Companion's own part: relationship, closeness, routine, weekly schedule, texting habits.
- **The AI-slop audit.** Everything the model writes is checked against a list of stock names (Elara Voss), words
  and patterns that mark text as model-written (Wren Halloway's list, in `Program/dramatis/data/ai-slop.json`). A
  hard hit, such as a stock name, an em dash or the assistant's voice, sends the draft back to the model once. Anything
  left shows on the form, with flagged words under "Worth a look". Names and words you typed or pasted yourself are
  never held against the draft. The list stays out of the drafting prompts, so the model doesn't see those words.
- **Works in.** While you edit, each app checks the character with its own rules, and the form shows "Works in
  Companion", or what that app would refuse.
- **Cards.** **Card (PNG)** puts the card into their portrait (or a plain picture if they have none). **Card (JSON)**
  saves the card on its own. The card's usual fields describe the character in words any app can read. Inside, under
  `extensions.prospero`, it carries the whole character and each app's own shape of it, so nothing is lost when a
  Prospero app takes them in.

Characters are always adults.

## Models

Drafting uses the model you pick at the top of the screen: Claude through Anthropic's API, any OpenAI-compatible
server (LM Studio, Ollama, OpenRouter), or the `claude` command line on your PC. API keys go in the system keyring
(Windows Credential Manager), not in a file. Without a model you can still fill in the form yourself.

## Running it on Windows

1. Install [Python 3.12+](https://www.python.org/downloads/) and [Node.js 22+](https://nodejs.org/), and clone this
   repository.
2. Double-click **`Windows\install.bat`**. It makes a Python environment in `Program\.venv` and builds the screen.
3. Double-click **`Windows\launch.bat`**. Dramatis opens in your browser at http://127.0.0.1:8815. Keep its window
   open while you use it.

`update.bat` gets the latest version, `stop.bat` stops a Dramatis whose window is lost, and `dev.bat` runs the
server with Vite's live reload on 5207, for working on it.

Your characters and settings live in `%APPDATA%\ProsperoDramatis` (`~/.prosperos-dramatis` elsewhere;
`DRAMATIS_HOME` overrides it). Each character is a JSON file in its `characters` folder, with their portrait beside it.

## Running beside the other Prospero apps

| App | App port | Dev interface |
| --- | --- | --- |
| Prospero's Study | 8765 | 5173 |
| Prospero's Companion | 8775 | 5175 |
| Prospero's Dungeon | 8785 | 5177 |
| Prospero's Worldsmith | 8795 | 5187 |
| Prospero's Adventure | 8805 | 5197 |
| Prospero's Dramatis | 8815 | 5207 |

## How it stays in step with the apps

Dramatis checks characters with each app's own code rather than a copy of their rules: Companion's, Adventure's
and Dungeon's request models, Companion's card reader, and the personality slider rules and words that Companion and
Adventure share. `Program/scripts/sync_format.py` copies those files into `Program/dramatis/formats`, and
`formats/SOURCE.json` records the commit each came from. CI checks every day that they still match each app's
`main`.

## Development

From `Program/`: `python -m pip install -e ".[dev]"`, then `python -m ruff check .`, `python -m pytest -q` and
`npm ci && npm run build`. `python -m dramatis` starts the server.

## License

[AGPL-3.0](LICENSE), like the rest of the suite.
