You help someone edit a character for Prospero's apps, where the same character can be a companion who lives an everyday life and chats with them, or someone in a tabletop roleplaying story. A check marked some words in the character's text that read as written by a model rather than a person. Replace only the marked words.

{{rules}}

The character so far, as JSON:
{{character}}

"what_people_believe" is what other people believe about them; write it as true. A "secret", when you are shown one, is theirs: say it outright only where it already is.

The text with the marked words, each between [[n]] and [[/n]]:

{{marked}}

Why each one was marked:
{{why}}

For each marked number, write what goes in its place:

- It drops in exactly where the marked words were, so the sentence around it still reads naturally, with the same punctuation around it. Keep its meaning and the character's facts; say it plainly, the way a person would.
- Use different words from the marked ones. A name becomes another ordinary name that fits the person; when the same name is marked more than once, give it the same new name every time.
- It may be empty when the sentence reads just as well without the words.
- Write only the replacement, never the words around it or the markers.

Reply with one JSON object and nothing else: {"spans": {"1": "...", "2": "..."}}, with every marked number.
