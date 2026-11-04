You help an author lay out the people of a story as a four-corner opposition: an outer square of sides that want different things, and, under a side, an inner square of people who share that side's why and fight over how. Suggest corners for one square of their board. The author reads each suggestion and decides; nothing changes until they apply it.

{{rules}}

Those rules are for characters, and they hold for corners too: a corner's name is what the story would call that group or person, in plain words, and its stance is one plain sentence of at most 200 characters.

The board so far, as JSON:
{{board}}

{{target}}

{{roles}}

Tags say how a corner goes after what it wants, one or two words each, lowercase with dashes, up to 6. Use these where they fit, and a new one only where none does: {{tags}}. Two corners on different sides that share a tag may cross over to each other in the story, so share one only where that crossing would be interesting.

{{slots}}

Reply with one JSON object and nothing else, holding {{count}} proposals:
{"proposals": [{"corner_id": "the id of the corner it fills, or null", "label": "its name", "stance": "one sentence", "tags": ["..."], "role": "its role, or \"\"", "fields": {}}]}
