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
time times people person anybody everyone nobody tell tells told says said
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


# Words that say what people believe of them isn't so, which give a secret away without its own words: "the truth
# is", "but really", "what nobody knows", "people think she's a nurse, but".
BREAKS_COVER = re.compile(
    r"\b(?:the (?:real |whole )?truth is|in truth|but really|really (?:is|was) (?:a|an|the)|the real reason|secretly"
    r"|in secret|behind (?:closed doors|everyone's back)|(?:what|something|things?) (?:people|nobody|no one|few|others"
    r"|everyone|anyone)\s+(?:else\s+)?(?:(?:do|does|did)(?:n't|n’t| not)\s+|never\s+|would(?:n't|n’t| not)\s+)?"
    r"(?:knows?|suspects?|sees?|guess(?:es)?|realis(?:es?)|realiz(?:es?))|(?:nobody|no one|few people) (?:else )?"
    r"(?:knows?|suspects?)|(?:people|everyone|others|most people|they|the town|her friends|his friends) (?:think|thinks"
    r"|believe|believes|assume|assumes|suppose|see|sees)\b[^.!?;]{0,80}?\bbut\b)", re.IGNORECASE)


def breaks_cover(text: str) -> str:
    """The words in a field anyone reads that say what people believe isn't so, or ''."""
    found = BREAKS_COVER.search(text or '')
    return found[0] if found else ''


def problem(labels: list[str], found: str = '') -> str:
    said = f' ("{found}")' if found else ''
    return (f"it put their secret into {', '.join(labels)}{said}, which other characters read. Keep the secret in "
            '"secret" (and their inner fields): everywhere else, write only what people believe, as plainly true.')
