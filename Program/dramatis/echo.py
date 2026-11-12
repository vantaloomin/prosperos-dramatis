"""Their secret kept out of the fields other characters read. A model shown the secret tends to write it into the
background, the wants or the fears (Wren's red-team runs: the assistant 9 times in 19, the split 8 in 15), so a field
anyone can read that uses two or more words found only in the secret's truth, or one number, is sent back once. The
assistant, shown the secret, has those fields written again without it (assistant.covered); this check stays for the
fields Help me write does not write and for the split.

"Only in the secret" means words the truth uses and what is already known does not: what people believe instead and,
for the assistant, the fields anyone could read before its edit and what the user wrote in their message."""
import re

from dramatis import fields

# The fields that may hold the secret: the secret itself, and how they are inside (their arc, psyche and how they see
# themselves).
INNER = ('secret', 'arc', 'psyche')
WORD = re.compile(r"[a-z0-9][a-z0-9'’]+")
# Words too common to say anything about the secret.
COMMON = set('''
about above after again against also always among another anyone anything around because been before being below
between both cannot could does doing done down during each either else ever every from have having here hers herself
himself into itself just keep keeps kept know knows known like made make makes many might more most much must never
none nothing once only other others ought ours over really same should since some someone something still such than
that their theirs them themselves then there these they thing things this those though through under until upon very
want wants were what when where whether which while whom whose will with within without would your yours years year
time times people person anybody everyone nobody tell tells told says said till
'''.split())


def public(key: str) -> bool:
    """Whether other characters read this field: everything but the secret and their inner fields."""
    return key != 'sees_self' and key.split('.')[0] not in INNER


def words(text: str) -> set[str]:
    return {stem(word) for word in WORD.findall((text or '').lower())
            if (len(word) > 3 or any(char.isdigit() for char in word)) and word not in COMMON}


def stem(word: str) -> str:
    word = word.replace('’', "'").removesuffix("'s")
    for ending in ('ing', 'ed', 'es', 's'):
        if word.endswith(ending) and len(word) - len(ending) > 3:
            word = word[:-len(ending)]
            # skimming, skimmed: skim
            return word[:-1] if ending in ('ing', 'ed') and word[-1] == word[-2] and word[-1] not in 'aeiouls' else word
    return word


def texts(value) -> str:
    """The words of a field's value, whatever its shape: a text, a list, an emotional edge, a weekly block."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(texts(item) for item in value)
    if isinstance(value, dict):
        return ' '.join(texts(item) for item in value.values())
    return ''


def secret_words(secret, *known: str) -> set[str]:
    """The words of their secret's truth that nothing else about them uses: not what people believe instead, and not
    `known` (what anyone can already read about them, and what the user wrote themselves)."""
    secret = secret if isinstance(secret, dict) else {}
    outside = words(secret.get('cover_story') or '')
    for text in known:
        outside |= words(text)
    return words(secret.get('truth') or '') - outside


def public_text(character: dict) -> str:
    """Every field of theirs anyone can read, as one text."""
    found = []
    for spec in fields.SPECS:
        if public(spec.key):
            value = character
            for part in spec.at():
                value = value.get(part) if isinstance(value, dict) else None
            found.append(texts(value))
    return ' '.join(found)


def echoed(value, secret: set[str]) -> list[str]:
    """The secret's own words a value uses, when there are two or more of them or one is a number (911, 2019); []
    otherwise."""
    found = sorted(words(texts(value)) & secret)
    return found if len(found) >= 2 or any(char.isdigit() for word in found for char in word) else []


# A heading in a pasted character that names their secret: "Secret:", "What she hides:", "The truth:".
SECRET_HEAD = re.compile(r"^\W*(?:(?:her|his|their|the|a|dark|hidden)\s+)?(?:secrets?|what (?:s?he|they) hides?|hidden"
                         r"|truth|private|nobody knows|no one knows)\b[^:\n]{0,20}:", re.IGNORECASE)
HEADING = re.compile(r"^\W*[\w'’][\w '’/()-]{0,30}:")


def has_secret(character: dict) -> bool:
    secret = character.get('secret') if isinstance(character.get('secret'), dict) else {}
    return bool((secret.get('truth') or '').strip())


def outside_secret(text: str, secret) -> str:
    """A pasted character without what tells their secret: the lines under a heading that names it, and each sentence
    whose words are mostly the secret's. What is left is the card's own, which the split may copy anywhere ("runs the
    night desk at a small hotel", when the secret is about the hotel safe)."""
    truth = words((secret or {}).get('truth') if isinstance(secret, dict) else '')
    blocks, hidden = [], False
    for line in (text or '').splitlines():
        if not line.strip() or HEADING.match(line):
            hidden = bool(SECRET_HEAD.match(line))
            blocks.append('')
        if not hidden:
            blocks[-1:] = [(blocks[-1] if blocks else '') + ' ' + line]
    kept = []
    for sentence in re.split(r'(?<=[.!?])\s+', ' '.join(blocks)):
        found = words(sentence)
        if not found or len(found & truth) * 2 < len(found):
            kept.append(sentence)
    return ' '.join(kept)


# Words that say what people believe of them isn't so, which give a secret away without its own words: "the truth
# is", "but really", "what nobody knows", "people think she's a nurse, but".
BREAKS_COVER = re.compile(
    r"\b(?:the (?:real |whole )?truth is|in truth|but really|really (?:is|was) (?:a|an|the)|the real reason|secretly"
    r"|in secret|behind (?:closed doors|everyone's back)|(?:what|something|things?) (?:people|nobody|no one|few|others"
    r"|everyone|anyone)\s+(?:else\s+)?(?:(?:do|does|did)(?:n't|n’t| not)\s+|never\s+|would(?:n't|n’t| not)\s+)?"
    r"(?:knows?|suspects?|sees?|guess(?:es)?|realis(?:es?)|realiz(?:es?))|(?:nobody|no one|few people) (?:else )?"
    r"(?:knows?|suspects?)|(?:people|everyone|others|most people|they|the town|her friends|his friends) (?:think|thinks"
    r"|believe|believes|assume|assumes|suppose|see|sees)\b[^.!?;]{0,80}?\bbut\b"
    # Wren's fifth pass: "exposed as a fraud", "the truth about", "the thing she'd never tell anyone", "left not for
    # nursing but", "her secret".
    r"|(?:exposed|unmasked|found out|caught out|seen through)\s+as\s+(?:a|an|the)?\s*\w+|(?:being|getting|be) (?:found|caught)"
    r" out|the (?:whole |real )?truth about|never (?:tell|tells|told|telling) (?:anyone|anybody|a soul|people|her|him|them)"
    r"|(?:won't|won’t|will not|doesn't|doesn’t|does not|never) (?:talk|talks|speak|speaks) (?:about|of)"
    r"|\bnot (?:for|because|over)\b[^.!?;]{1,60}?\bbut\b|\b(?:her|his|their|the) (?:dark |real |one |big )?secret\b"
    r"(?!\s+(?:to|of|recipe|ingredient|garden|santa|weapon|handshake|menu)\b))", re.IGNORECASE)


def breaks_cover(text: str) -> str:
    """The words in a field anyone reads that say what people believe isn't so, or ''."""
    found = BREAKS_COVER.search(text or '')
    return found[0] if found else ''


def problem(labels: list[str], found: str = '') -> str:
    said = f' ("{found}")' if found else ''
    return (f"it put their secret into {', '.join(labels)}{said}, which other characters read. Keep the secret in "
            '"secret" (and their inner fields): everywhere else, write only what people believe, as plainly true.')
