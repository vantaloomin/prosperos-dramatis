<p align="center">
  <a href="https://github.com/vantaloomin/prosperos-dramatis/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/vantaloomin/prosperos-dramatis/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <img alt="Runs on Windows" src="https://img.shields.io/badge/runs%20on-Windows-555">
  <a href="LICENSE"><img alt="License: AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-555"></a>
</p>

# Prospero's Dramatis

**Make a character once. Take them into every Prospero app.**

Dramatis is where the suite's people are made. You give it as much or as little as you like (a name, an age, a city,
a hunch) and your model drafts the rest: who they are, how they talk, what they want and fear, what they're like to
be around. You read every word before anything is saved. Then the same character can be a companion in
[Prospero's Companion](https://github.com/vantaloomin/prosperos-companion), or someone in the party in
[Prospero's Adventure](https://github.com/vantaloomin/prosperos-adventure) or
[Prospero's Dungeon](https://github.com/vantaloomin/prosperos-dungeon), each app taking them in its own shape.

It runs on your computer and talks to whichever model you choose: Claude through Anthropic's API, any
OpenAI-compatible server (LM Studio, Ollama, OpenRouter), or the `claude` command line on your PC. Without a model you
can still fill in the form yourself.

It started as Companion's character creator, and checks every character with Companion's, Adventure's and Dungeon's
own code.

<p align="center">
  <img src="Program/docs/images/editor.png" alt="Dana Okafor in the Dramatis form, with Works in Companion, Adventure and Dungeon checks above her fields" width="880">
</p>

## Where it's at

**v0.1.0 is the first version**, a work in progress. Drafting, the full form, the AI-slop audit, the library and card
export are in. The Prospero apps import a Dramatis card today as an ordinary character card; reading everything
Dramatis puts in it is the next step for each of them. Windows is the only platform with scripts so far.

## What it does

**A few things to start.** Pick a name, gender, age and where and when they come from (all optional), plus which apps
they're for. Your model writes the rest: who they are, their personality, how they talk and how they sound, how others
see them and how they see themselves, background, wants and fears, skills, flaws and interests, and for Companion,
their week, routine and life themes. Under **More options** you can add an idea, a vibe, how they know you in
Companion, and emotional edges, which are off unless you turn them on. Characters are always adults.

**Bring a character you already have.** Paste notes, a bio or a scene, or open a character card (PNG or JSON, V1 to
V3). The model splits it into the fields and tells you which ones it had to fill in. You see the card's text before
anything is sent anywhere, and a card Dramatis made comes back whole without asking the model at all.

**The full form.** Every field is yours to edit. **Help me write** rewrites one field to fit the rest of the
character, and **Put back what was there** undoes it. **How they talk** (their words, rhythm and humour) and **How
they sound** (the voice itself, for text to speech) are separate fields, so neither you nor a model mixes them up.
**Outward appearance** is how others see them, reputation included, and can disagree with **How they see
themselves**. There are also the five personality sliders (roll again, or start from a four-letter type), looks
field by field, kind and lifespan, and Companion's own part: relationship, closeness, routine, weekly schedule and
texting habits.

**An audit for AI slop.** Everything the model writes is checked against Wren Halloway's list of stock names (Elara
Voss), words and patterns that mark text as model-written, plus the signs from Wikipedia's
[Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing) that fit a character. A hard hit,
such as a stock name, an em dash, the chatbot's voice or an unfilled "[Insert name]", sends the draft back to the
model once. Anything left shows on the form, with flagged words under **Worth a look**. Names and words you typed or
pasted yourself are never held against the draft, and the list stays out of the prompts, so the model never sees
those words.

**Works in.** While you edit, each app checks the character with its own rules, and the form shows **Works in
Companion**, or what that app would refuse.

**Cards.** **Export card** saves a character card (Character Card V3, PNG or JSON) in one of two kinds. The PNG
puts the card into their portrait, or a plain picture if they have none.

- **Prospero apps**: everything, for Companion, Adventure and Dungeon. Under `extensions.prospero` it carries the
  whole character and each app's own shape of them, so nothing is lost on the way in, and Dramatis opens it whole.
- **SillyTavern, Marinara, Front Porch and other chat apps**: the same card with nothing under `extensions`, so what
  only the Prospero apps use (Companion's schedule, routine, texting habits and emotional edges, the sliders) stays
  in the suite. Those apps keep any extension a card brings and pass it on when the card is shared again, so this is
  the one to hand around.

Both describe the character in the card's own fields (description, personality and scenario), so any app reads the
same person. The PNG carries the V3 card and a V2 copy, because Front Porch reads only the V2 one.

## Getting started

### Windows

1. Install [Python 3.12+](https://www.python.org/downloads/), [Node.js 22+](https://nodejs.org/) and
   [Git](https://git-scm.com/download/win), and clone this repository.
2. Open the `Windows` folder and double-click **`install.bat`**. It makes a Python environment in `Program\.venv`,
   installs the locked dependencies and builds the interface.
3. Double-click **`launch.bat`**. Dramatis opens in your browser at http://127.0.0.1:8815. Keep its window open while
   you use it.
4. Pick a model with **Change** at the top right, then make your first character.

### Mac and Linux

There are no helper scripts yet; [Development](#development) shows how to run it from the `Program` folder.

Your characters live outside the program folder, so updating keeps them: `%APPDATA%\ProsperoDramatis` on Windows and
`~/.prosperos-dramatis` elsewhere (`DRAMATIS_HOME` overrides it). Each character is a JSON file in its `characters`
folder, with their portrait beside it.

## Running beside the other Prospero apps

Each app keeps its own port and data folder, so they all run at once without clashing:

| App | App port | Dev interface |
| --- | --- | --- |
| Prospero's Study | 8765 | 5173 |
| Prospero's Companion | 8775 | 5175 |
| Prospero's Dungeon | 8785 | 5177 |
| Prospero's Worldsmith | 8795 | 5187 |
| Prospero's Adventure | 8805 | 5197 |
| Prospero's Dramatis | 8815 | 5207 |

## Which folder is for you

| Folder | Who it is for |
| --- | --- |
| [`Windows`](Windows) | Running Dramatis on a Windows PC. |
| [`Program`](Program) | The app itself: code (`Program/dramatis`), interface (`Program/src`), tests and scripts. You never need to open it to use Dramatis. |

| Script | What it does |
| --- | --- |
| `install.bat` | Makes the Python environment, installs the locked dependencies and builds the interface. Run it again after updating. |
| `launch.bat` | Starts Dramatis on http://127.0.0.1:8815 and opens it in the browser. Close its window to stop it. |
| `update.bat` | Stops Dramatis, gets the latest `main` and reruns the install. |
| `stop.bat` | Stops a running Dramatis, for when its window is lost. |
| `dev.bat` | Development mode: the backend reloads on Python changes and Vite serves http://127.0.0.1:5207. |

## Staying in step with the apps

Dramatis checks characters with each app's own code rather than a copy of their rules: Companion's, Adventure's and
Dungeon's request models, Companion's card reader, and the personality slider rules and words that Companion and
Adventure share. They're copied into `Program/dramatis/formats/`, with the commit each came from recorded in
`SOURCE.json`. To update them:

```
cd Program
python scripts/sync_format.py --companion "Z:\Coding Projects\prosperos-companion" --adventure "Z:\Coding Projects\prosperos-adventure" --dungeon "Z:\Coding Projects\prosperos-dungeon"
python -m pytest -q
```

CI checks the copies against each app's latest `main` on every pull request and once a day.

## Privacy

Dramatis only listens on your own computer (127.0.0.1). Characters and portraits stay in your data folder. The only
thing that leaves your PC is what you ask your model to write, sent to the model you picked. API keys are kept in your
system's credential store (Windows Credential Manager), never in a file.

## Development

From `Program/`: `python -m pip install -e ".[dev]"` and `npm ci`, then `python -m dramatis` starts the server.
Before pushing, run `python -m ruff check .`, `python -m pytest -q` and `npm run build`.

## License

Licensed under the [GNU Affero General Public License v3.0](LICENSE), matching the Prospero's Companion, Adventure
and Dungeon code it reuses.
