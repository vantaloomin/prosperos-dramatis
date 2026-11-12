# Changelog

What changed in each release of Prospero's Dramatis. Each release's notes are also in `Program/docs/releases/`.

## 0.2.1: Secrets kept, adults only

### Safer

- More ways of giving a pasted character or an idea an age under 18 are refused ("Mara, 15, lives…", "just turned
  14", "in ninth grade", "she lives with her mom, and she is 15"), and so are more ways of asking the assistant or Help
  me write for one ("age her down to 17", "tenth grade"), while "sixteen years sober" is left alone.
- Help me write on a field other characters read keeps to what people believe of them.
- A value the split lifted whole from a line telling the model what a field says is taken back out and the line named.
- A pasted character's field that still gives their secret away after the model's second try is left empty, and the
  form names it, rather than other characters reading the secret there. So is one that says outright that what people
  believe isn't so ("the truth is", "people think… but").
- Asked for while the secret is in view, the assistant's rewrite of a field others read no longer hears the user's talk
  of the secret, and a rewrite that still says the cover story is false is dropped.
- When a character has a secret, a split and the assistant's edits now get a model call that reads the fields other
  characters see for the secret, however it is worded, and the model writes a flagged field once more. Still flagged,
  a split leaves the field empty and names it; the assistant leaves that edit out and says so. What people believe,
  told in any words, and the card's own words are never flagged, and a field that talks to the check counts as one.
- A draft or a split is refused when the model reads the user's words as giving an age under 18 now, behind the word
  checks that catch most of them first.
- The split no longer empties a field for words the pasted card itself uses outside its secret (a night clerk whose
  secret is about the hotel safe keeps "runs the night desk at a small hotel"), and a relative's age in About ("a
  16-year-old daughter") is no longer read as theirs, for drafts and portraits alike.
- More ways of giving the secret away are caught ("exposed as a fraud", "the truth about", "the thing she'd never tell
  anyone"), and the assistant checks every field others read for them whenever there is a secret, shown or not.
- A birth year under 18 years ago, a British school year ("Year ten") and GCSEs still ahead are refused, and the model
  is asked to say when the user's words make someone a minor without an age; a reply that leaves that out goes back
  once.
- "Make her a high school teacher" is no longer refused, and "a teenager again", "a minor living with her parents" and
  "a teen runaway" are.

## 0.2.0: Depth, casts and portraits

Dramatis 0.2 gives a character depth, a cast to stand in, and a picture, and makes the library something you can
search, back up and carry between apps.

### New

- **Depth.** An in-voice interview, an inner arc (the lie they believe, the truth they need, what could force it), who
  they could become (who they were, are expected to be, want to be, fear becoming) and a secret. The secret goes with
  them into every app, so they know what they are keeping.
- **Casts.** A story's people as a two-layer opposition on the Cast board, with suggestions for corners, a check of a
  square and the turn, each put on the board for you to keep or put back. A card exported from a cast says where they
  stand in it.
- **Portraits.** Made with Companion's own image makers, kept at full size, or your own PNG, JPEG or WebP.
- **Sidebar Assistant.** A chat beside the form that sees it as you type and proposes edits you keep or put back.
- **Bring characters in** from other apps' cards and files, with what Dramatis doesn't make kept for their cards.
- **The library.** Search by any of their words, duplicate a character, back the whole library up as one file and
  bring a backup back, open a cast file from another Dramatis, and a warning naming the casts before a delete.
- **User persona.** A character who is you, to play as rather than talk to.
- **Models.** Companion's full model setup, with a profile for each job (writing, the assistant, casts).
- **Card exports** for SillyTavern, Marinara and Front Porch, without the Prospero-only part.
- **Mac.** Double-click scripts in the `Mac` folder, as on Windows.

### Better

- A quick-start draft fills every section and says what the model left empty; its looks are settled first (from your
  words, or rolled) and its name comes from Companion's name banks.
- The AI-slop audit's Worth a look: tick hits, then Fix selected, Fix all or Ignore.
- Every model result stands in its field with Keep / Put back, and Stop stops the model.
- Unsaved edits and unsaved cast boards survive switching and reloading, every view has its own address so Back and
  Forward work, and the library sits in a drawer on a phone.
- Skills, flaws and interests are short phrases; text boxes grow to fit.
- Companion, Adventure and Dungeon (each on its latest main) read the Prospero part of a card, so a character arrives
  as written.
- The install uses locked package versions.
- Fewer drafts are sent back: a model's dashes become commas, and a height like 5'10" or a
  reply cut off before its last brackets no longer breaks it.

### Safer

- Dramatis answers only this computer: a page from another site can't reach your library.
- Lines in a pasted character that talk to the model (a note to the AI, an OOC aside, "set the voice to…") are
  left out of what it reads, and the form names them.
- The secret stays out of Help me write, the assistant and the fields other characters read, pasted minors and
  requests for one are refused, nothing a model writes can make them one, and browser autofill is off.
- Saves carry a revision, so a save from an older tab asks before it writes over a newer one.

## 0.1.0

The first version: one character creator for Prospero's Companion, Adventure and Dungeon. A character drafted with
a model from a few words or a pasted text, checked against each app's own models, with the AI-slop audit, saved in a
library and exported as a Character Card V3 that carries each app's shape of them.
