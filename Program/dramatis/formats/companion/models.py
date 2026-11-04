# Vendored from vantaloomin/prosperos-companion Program/companion/models.py by scripts/sync_format.py. Edit it there, then sync.
"""Request bodies. Input mirrors prosperos-study server/models.py at bbcbde4."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Relationship = Literal['friendship', 'romance', 'mentor', 'family', 'other']
Layer = Literal['user_fact', 'shared_experience', 'plan', 'temporary', 'relationship', 'companion_life']
PlanStatus = Literal['proposed', 'agreed', 'postponed', 'cancelled', 'completed']
EventKind = Literal['routine', 'plan', 'ordinary', 'thread']
BlockKind = Literal['work', 'study', 'errand', 'leisure', 'social', 'rest', 'sleep']
ClockTime = Annotated[str, Field(pattern=r'^([01][0-9]|2[0-3]):[0-5][0-9]$')]
Intensity = Literal['mild', 'moderate', 'strong']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class RoutineBlock(Input):
    """One recurring part of the companion's day, in the companion's timezone (PRD T2)."""
    key: str = Field(default='', max_length=60, pattern=r'^[a-z0-9-]*$')
    label: str = Field(min_length=1, max_length=120)
    kind: BlockKind = 'leisure'
    days: list[int] = Field(default_factory=lambda: list(range(7)), min_length=1, max_length=7)
    start: ClockTime
    end: ClockTime
    themes: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def check(self):
        if self.start == self.end:
            raise ValueError('A routine block must not start and end at the same time.')
        if any(day < 0 or day > 6 for day in self.days) or len(set(self.days)) != len(self.days):
            raise ValueError('Days are distinct weekday numbers from 0 (Monday) to 6 (Sunday).')
        return self


class TheirHours(Input):
    """How their week sits against the user's clock (companion/life/their_hours.py). The form sends the mode back;
    the shift is always worked out on the server."""
    mode: Literal['fit', 'mine', 'city'] = 'city'
    shift: int = Field(default=0, ge=-1440, le=1440)
    why: str = Field(default='', max_length=20)
    zone: str = Field(default='', max_length=64)
    fit: int = Field(default=0, ge=-1440, le=1440)


class EmotionalTrait(Input):
    """An opt-in trait such as jealousy or guilt over absence (PRD C6). None are enabled by default."""
    name: str = Field(min_length=1, max_length=60)
    intensity: Intensity = 'mild'
    note: str = Field(default='', max_length=500)


class TextingStyle(Input):
    """How the companion texts (companion/texting.py); all off is texting like anyone else."""
    bursts: bool = False
    lowercase: bool = False
    typos: bool = False
    # Quick to reply: they read texts at the quick pace while free (companion/life/reading.py).
    quick: bool = False


class IntimacySetup(Input):
    """What the user set about a companion's adult side (companion/world/intimacy.py); empty uses the roll."""
    orientation: Literal['', 'straight', 'gay', 'lesbian', 'bisexual', 'pansexual', 'queer', 'asexual'] = ''
    level: Literal['', 'reserved', 'conventional', 'curious', 'adventurous', 'wild'] = ''
    drive: Literal['', 'low', 'average', 'high'] = ''
    interests: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=24)
    # The user chose the interests themselves, so an empty list means none rather than the roll.
    interests_picked: bool = False
    # Their own turn-ons and turn-offs, in the user's words, beyond the bank.
    own_into: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=8)
    not_into: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=8)
    note: str = Field(default='', max_length=600)

    @field_validator('own_into', 'not_into')
    @classmethod
    def between_adults(cls, value: list[str]) -> list[str]:
        from dramatis.stand_ins import intimacy
        if not all(intimacy.allowed(entry) for entry in value):
            raise ValueError('Keep it to things between consenting adults.')
        return value


class MoneySetup(Input):
    """How the companion's money works (companion/life/money.py). Everything else comes from city data."""
    # A career id from the world data; empty guesses one from who they are, else an ordinary wage.
    career: str = Field(default='', max_length=60)
    style: Literal['careful', 'balanced', 'spender'] = 'balanced'
    # Empty lets the life simulation pick an everyday goal each half year.
    saving_for: str = Field(default='', max_length=120)
    goal: float = Field(default=0, ge=0, le=100_000_000)
    goal_since: str = Field(default='', pattern=r'^(\d{4}-\d{2}-\d{2})?$')
    # Their hours (companion/life/shifts.py): empty follows their work (shifts that change each week for a bartender,
    # gigs for a freelancer), or the same days every week ('staff'), shifts ('rota') or gigs ('freelance').
    employment: Literal['', 'staff', 'rota', 'freelance'] = ''
    # What a student studies (companion/life/job_words.py); empty reads it from who they are.
    field: str = Field(default='', max_length=60)
    # Work of their own (career 'own', companion/life/money.py OWN): what it is, as the user wrote it.
    job: str = Field(default='', max_length=60)
    # What they take home a month in their city's money: None works it out from their work and city, 0 is unpaid
    # (a volunteer, a carer).
    pay: float | None = Field(default=None, ge=0, le=1_000_000_000)


class Looks(Input):
    """What they look like, field by field (companion/world/looks.py); an empty field is drawn for them."""
    age: int | None = Field(default=None, ge=18, le=120)
    height_cm: int | None = Field(default=None, ge=120, le=230)
    weight_kg: int | None = Field(default=None, ge=35, le=250)
    build: str = Field(default='', max_length=120)
    skin: str = Field(default='', max_length=120)
    face: str = Field(default='', max_length=120)
    jaw: str = Field(default='', max_length=120)
    nose: str = Field(default='', max_length=120)
    eyes: str = Field(default='', max_length=120)
    eye_shape: str = Field(default='', max_length=120)
    hair: str = Field(default='', max_length=200)
    facial_hair: str = Field(default='', max_length=120)
    feature: str = Field(default='', max_length=200)
    # The values the app filled in when a townsperson became a companion (companion/cast.py): a field still equal to
    # its drawn value is the app's, so it may change over time (companion/life/grooming.py); one the user edited is not.
    drawn: dict[str, int | str] = Field(default_factory=dict, max_length=20)


class PersonalitySlider(Input):
    """One personality slider (companion/world/personality.py): low (0), in between (1) or high (2), and who set
    it: the roll, the character's own words, or the user."""
    level: int = Field(ge=0, le=2)
    source: Literal['rolled', 'idea', 'you'] = 'rolled'


PersonalityTrait = Literal['social', 'warmth', 'order', 'curiosity', 'stress']


class CharacterDefinition(Input):
    # Empty when creating gives them a name that fits (companion/characters.py); a revision needs one.
    name: str = Field(default='', max_length=120)
    identity: str = Field(default='', max_length=4000)
    personality: str = Field(default='', max_length=8000)
    voice: str = Field(default='', max_length=4000)
    # What they are good at and what costs them, so the character reads as a person (both optional).
    skills: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=20)
    flaws: list[Annotated[str, Field(max_length=300)]] = Field(default_factory=list, max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=50)
    background: str = Field(default='', max_length=12000)
    appearance: str = Field(default='', max_length=4000)
    # The "In photos" line pictures use in place of the appearance (companion/images/prompts.py `in_photos`); empty
    # follows the appearance, filtered to what a camera can see.
    in_photos: str = Field(default='', max_length=2000)
    # Their name in picture prompts for every image model (Vanta, 2026-10-28), for a character a model may know by name
    # (Sett, Spock). Off by default: a name means nothing to a model for someone original and invites lettering.
    name_in_pictures: bool = False
    # Face shape, height, build and the rest, so every picture shows the same person; empty fields are drawn.
    looks: Looks = Field(default_factory=Looks)
    routine: str = Field(default='', max_length=8000)
    location: str = Field(default='', max_length=200)
    # City id in the installed world data (for example "baltimore"); events use its real places.
    home_city: str = Field(default='', max_length=60)
    relationship: Relationship = 'friendship'
    # How close they start (a closeness stage, 1 = Just met) and how the two of them know each other already.
    starting_closeness: int = Field(default=1, ge=1, le=5)
    history_together: str = Field(default='', max_length=2000)
    # How others see them and how they see themselves (companion/world/perception.py); empty fills itself in.
    seen_as: str = Field(default='', max_length=400)
    sees_self: str = Field(default='', max_length=1200)
    # Empty means neutral about absence. Jealousy, guilt or missing the user are opt-in traits.
    absence_reaction: str = Field(default='', max_length=2000)
    emotional_traits: list[EmotionalTrait] = Field(default_factory=list, max_length=12)
    timezone: str = Field(default='UTC', max_length=64)
    # Structured routine for the life simulation; empty uses a gentle default day.
    schedule: list[RoutineBlock] = Field(default_factory=list, max_length=24)
    # Their week moved to fit the user's evenings, or onto the user's clock (companion/life/their_hours.py).
    their_hours: TheirHours | None = None
    # Themes automatic events may draw on (PRD T3).
    life_themes: list[str] = Field(default_factory=list, max_length=20)
    # "MM-DD"; empty picks a date from the companion's id (companion/life/occasions.py).
    texting: TextingStyle = Field(default_factory=TextingStyle)
    birthday: str = Field(default='', pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')
    # Everyone gets older (companion/life/ages.py): on, they stay the age written, for characters who shouldn't age.
    keeps_age: bool = False
    # Lifespans (companion/world/lifespans.py): the kind of person they are ('elf'), empty to read it from their words,
    # and how long they live in years, None for as long as their kind does and 0 for "Doesn't age".
    kind: str = Field(default='', max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = Field(default=None, ge=0, le=5000)
    money: MoneySetup = Field(default_factory=MoneySetup)
    # Their adult side, only used with Settings > Realism > Adult side of life on; None uses the roll.
    intimacy: IntimacySetup | None = None
    # Personality sliders (companion/world/personality.py); None, or a trait left out, is read from their words and
    # rolled.
    personality_sliders: dict[PersonalityTrait, PersonalitySlider] | None = None
    # The weeks of shifts or gigs the app adds when it reads the companion (companion/life/shifts.py). Accepted so a
    # form can send back what it was given, and never saved.
    rota: dict | None = Field(default=None, exclude=True)
    # What their life chapters add to the definition the app reads (companion/characters.py `apply_changes`): the
    # neighbourhood a move cleared, their own business and a long-term condition. Accepted back from the form the
    # same way, and never saved: the chapters keep them.
    near: str | None = Field(default=None, exclude=True)
    business: dict | None = Field(default=None, exclude=True)
    health: dict | None = Field(default=None, exclude=True)

    @field_validator('lifespan')
    @classmethod
    def lifespan_or_ageless(cls, value):
        if value is not None and 0 < value < 40:
            raise ValueError('A lifespan is 40 years or more.')
        return value


DraftField = Literal['identity', 'personality', 'voice', 'skills', 'flaws', 'interests', 'background', 'appearance',
                     'routine', 'life_themes', 'schedule']


class CharacterDraftRequest(Input):
    """The quick start: a short idea and a few optional picks; the model drafts the rest."""
    idea: str = Field(default='', max_length=2000)
    name: str = Field(default='', max_length=120)
    relationship: Relationship = 'friendship'
    age: str = Field(default='', max_length=40)
    vibe: str = Field(default='', max_length=300)
    home_city: str = Field(default='', max_length=60)
    timezone: str = Field(default='UTC', max_length=64)
    # Jealousy, guilt over absence and similar traits stay off unless the user asks for them (PRD C6).
    emotional_edges: bool = False


class PerceptionRequest(Input):
    """The character form as it stands, for suggestions for how others see them and how they see themselves."""
    definition: dict


class PersonalityRequest(Input):
    """The character form as it stands, for its personality sliders: what its words settle and the rest rolled.
    `roll` > 0 rolls the Rolled sliders again; `type` sets four of them from a four-letter type."""
    definition: dict
    seed: str = Field(default='', max_length=80)
    roll: int = Field(default=0, ge=0, le=100000)
    type: str = Field(default='', max_length=4)


class TownsfolkPersonality(Input):
    """The sliders the user set on a townsperson's profile; a trait left out goes back to the roll."""
    key: str = Field(min_length=1, max_length=200)
    sliders: dict[PersonalityTrait, PersonalitySlider] = Field(default_factory=dict)


class FieldDraftRequest(Input):
    """Rewrite one field of a character being edited, in keeping with the rest of it."""
    definition: dict
    field: DraftField
    request: str = Field(default='', max_length=500)


class CharacterSplitRequest(Input):
    """A whole character the user already has, pasted in, to be split into the form's fields."""
    text: str = Field(min_length=1, max_length=40000)
    relationship: Relationship = 'friendship'
    timezone: str = Field(default='UTC', max_length=64)
    emotional_edges: bool = False


class ImportPick(Input):
    """Which parts of a character or lorebook file to import (companion/imports/characters.py); everything by default.
    `entries` are positions in the file's lorebook as the preview listed them, all of them when None. `lore_for` is
    whose the lorebook becomes: '' for the app's choice, 'new' (the character being imported), 'world' or a
    companion's id."""
    character: bool = True
    picture: bool = True
    book: bool = True
    entries: list[int] | None = Field(default=None, max_length=5000)
    lore_for: str = Field(default='', max_length=64)


class CharacterCardFile(Input):
    """A character card file (JSON or PNG) read into plain text for the paste box; nothing is saved."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)


class CharacterImportFile(CharacterCardFile):
    """A character card, CHARX, BYAF or lorebook file, base64 encoded, with the parts of it to import."""
    pick: ImportPick = Field(default_factory=ImportPick)


class WorldMapPick(Input):
    """Which parts of a Marinara world map to import (companion/world/marinara.py): the city, its places' notes as
    lore, and which of those notes, all of them when None."""
    city: bool = True
    book: bool = True
    entries: list[int] | None = Field(default=None, max_length=5000)


class WorldMapImport(BaseModel):
    """A Marinara world map, its pictures already left out by the page, with the parts of it to import."""
    model_config = ConfigDict(extra='forbid')
    map: dict
    pick: WorldMapPick = Field(default_factory=WorldMapPick)


class ChatFile(Input):
    """An old chat file (companion/imports/chats.py), base64 encoded, for a companion or the one in focus."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)
    companion_id: str | None = Field(default=None, max_length=100)


class LibraryFile(Input):
    """A long text for the reference library (companion/library.py), base64 encoded: the open companion's book, or
    the world's."""
    filename: str = Field(min_length=1, max_length=260)
    data: str = Field(min_length=1, max_length=14_000_000)
    world: bool = False


class LoreSwitch(Input):
    """Turn an imported lorebook, or one of its entries, on or off (companion/lore.py)."""
    enabled: bool


class LoreWhen(Input):
    """When a lore entry applies besides its keywords (companion/lore_moments.py): conditions such as "weather:rain"."""
    when: list[Annotated[str, Field(max_length=160)]] = Field(max_length=40)


class SidecarTurn(Input):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=40000)


class SidecarRequest(Input):
    """One message to the sidecar. It reads the app's context; `definition` is the character form while it is open."""
    message: str = Field(min_length=1, max_length=40000)
    history: list[SidecarTurn] = Field(default_factory=list, max_length=12)
    view: str = Field(default='', max_length=60)
    definition: dict | None = None
    focus_message_id: str | None = Field(default=None, max_length=100)


class MessageEdit(Input):
    text: str = Field(min_length=1, max_length=8000)
    expected_text: str = Field(max_length=40000)


class VoicePin(Input):
    pinned: bool = True


class PromptUpdate(Input):
    text: str = Field(min_length=1, max_length=20000)


class CharacterRevision(Input):
    definition: CharacterDefinition
    note: str = Field(default='', max_length=500)
    expected_version_id: str


class CastDraftRequest(Input):
    """A townsperson the main character has met (companion/cast.py)."""
    key: str = Field(min_length=1, max_length=200)


class Tie(Input):
    """How the new companion and one already here know each other, told once on the form that makes them one."""
    companion_id: str = Field(min_length=1, max_length=100)
    level: int | None = Field(None, ge=1, le=5)
    how: str = Field('', max_length=300)


class CastSwitch(Input):
    """Make that townsperson the main character, with the definition the user reviewed."""
    key: str = Field(min_length=1, max_length=200)
    definition: CharacterDefinition
    ties: list[Tie] = Field(default_factory=list, max_length=200)


class TownSeed(Input):
    """Seed new townsfolk for the companion, or go back to the city's shared ones."""
    fresh: bool


class CastFocus(Input):
    companion_id: str = Field(min_length=1, max_length=64)


class ChatRead(Input):
    thread_id: str = Field(min_length=1, max_length=64)
    seq: int | None = Field(default=None, ge=0)


class StartOverConfirm(Input):
    name: str = Field(max_length=200)


HEX = r'^#[0-9a-fA-F]{6}$'


class Palette(Input):
    """A custom color scheme, as Prospero's Study's custom palette."""
    accent: str = Field(pattern=HEX)
    background: str = Field(pattern=HEX)
    surface: str = Field(pattern=HEX)
    text: str = Field(pattern=HEX)


class OocMarker(Input):
    """An out-of-character marker: a starting word (`open` only, like OOC:) or an opening and closing pair."""
    open: str = Field(min_length=1, max_length=12, pattern=r'\S')
    close: str = Field(default='', max_length=12)


class SettingsUpdate(Input):
    user_timezone: str | None = Field(default=None, max_length=64)
    # 'detected': the interface reporting this PC's zone; 'pc': Use this PC's timezone; otherwise chosen.
    user_timezone_source: Literal['detected', 'pc', 'chosen'] | None = None
    automatic_memory: bool | None = None
    sensitive_memory: bool | None = None
    share_profile_across_timelines: bool | None = None
    background_activity: bool | None = None
    model_memory_suggestions: bool | None = None
    chat_style: Literal['feed', 'bubbles', 'community', 'retro', 'novel'] | None = None
    chat_sounds: bool | None = None
    chat_retro_dark: bool | None = None
    # Period words in period cities (companion/world/era_words.py).
    period_words: bool | None = None
    # Keep my colours everywhere (companion/their_look.py): no companion's own colours or name font anywhere.
    keep_my_colours: bool | None = None
    # Look for Claude Code and Codex accounts on this PC (companion/providers/cli_accounts.py, Settings > Models).
    find_cli_accounts: bool | None = None
    color_scheme: Literal['ink', 'slate', 'umber', 'moss', 'wine', 'ash', 'custom'] | None = None
    custom_palette: Palette | None = None
    # 'system' matches the computer (Paper or Ink), 'paper' is the light profile, 'scheme' uses color_scheme.
    theme: Literal['system', 'scheme', 'paper'] | None = None
    ask_about_people: bool | None = None
    story_mode: bool | None = None
    show_secret_slips: bool | None = None
    show_moods: bool | None = None
    show_news: bool | None = None
    show_odds: bool | None = None
    # The adult side of life (companion/world/intimacy.py) and whether townsfolk's shows.
    adult_side: bool | None = None
    show_adult_side: bool | None = None
    # The numbers behind home life, such as upkeep meters (Settings > Realism > Hidden values).
    show_home_meters: bool | None = None
    # They can ask to remember more (companion/memory/look_back.py).
    recall_more: bool | None = None
    # Out-of-character messages go to the helper (Settings > Chat).
    ooc_to_helper: bool | None = None
    ooc_markers: list[OocMarker] | None = Field(default=None, max_length=12)
    # Automatic backups of every world (companion/auto_backup.py).
    auto_backups: Literal['off', 'daily', 'weekly'] | None = None
    review_complete: bool | None = None
    # The first-run notice: the characters are AI, and the user is 18 or older. Only ever confirmed.
    ai_notice_confirmed: Literal[True] | None = None


class ConnectionUpdate(Input):
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, max_length=4000)
    max_output_tokens: int = Field(default=800, ge=64, le=128000)
    context_tokens: int = Field(default=16000, ge=1024, le=2000000)
    timeout_seconds: int = Field(default=180, ge=10, le=1800)
    # Optional embedding model on the same connection; empty keeps recall keyword-only.
    embedding_model: str | None = Field(default=None, max_length=200)


class MessageCreate(Input):
    text: str = Field(default='', max_length=40000)
    client_id: str = Field(min_length=8, max_length=100)
    # Pictures uploaded for this message (companion/pictures.py).
    picture_ids: list[str] = Field(default_factory=list, max_length=4)
    # The companion whose chat the window shows (conversation.in_focus).
    companion_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def something_to_send(self):
        if not self.text.strip() and not self.picture_ids:
            raise ValueError('Write a message or add a picture.')
        return self


class MemoryCreate(Input):
    layer: Layer
    subject: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=4000)
    reality: Literal['real', 'fiction'] = 'real'
    boundary: bool = False
    sensitive: bool = False
    plan_status: PlanStatus | None = None
    applies_from: str | None = None
    applies_until: str | None = None
    source_message_ids: list[str] = Field(default_factory=list, max_length=20)
    tentative: bool = False
    # The companion whose Memories or chat the window shows, when no source message says it.
    companion_id: str | None = Field(default=None, max_length=100)


class MemoryCorrection(Input):
    value: str = Field(min_length=1, max_length=4000)
    plan_status: PlanStatus | None = None
    applies_from: str | None = None
    applies_until: str | None = None
    expected_revision: int


class MemoryDelete(Input):
    delete_sources: bool = False


class EventProposal(Input):
    idempotency_key: str = Field(min_length=8, max_length=200)
    kind: EventKind
    summary: str = Field(min_length=1, max_length=2000)
    details: dict = Field(default_factory=dict)
    starts_at: str
    ends_at: str
    inputs: dict = Field(default_factory=dict)


class EventCorrection(Input):
    summary: str = Field(min_length=1, max_length=2000)
    details: dict = Field(default_factory=dict)


class LifeSettingsUpdate(Input):
    """Catch-up and background limits (PRD T3–T5). Ceilings are the tested maximums."""
    automatic_events: bool | None = None
    phrase_with_model: bool | None = None
    catch_up_on_return: bool | None = None
    catch_up_max_events: int | None = Field(default=None, ge=0, le=6)
    catch_up_lookback_hours: int | None = Field(default=None, ge=6, le=336)
    return_gap_hours: int | None = Field(default=None, ge=1, le=48)
    background_interval_minutes: int | None = Field(default=None, ge=15, le=1440)
    background_daily_events: int | None = Field(default=None, ge=0, le=8)
    texts_first: bool | None = None
    texts_daily: int | None = Field(default=None, ge=1, le=6)
    texts_gap_hours: int | None = Field(default=None, ge=1, le=24)
    # Messages sent while the user is away, from all companions together (companion/away.py); 0 for none.
    away_daily: int | None = Field(default=None, ge=0, le=40)
    # 0 sizes the circle by how sociable the companion is (companion/life/circle.py).
    circle_size: int | None = Field(default=None, ge=0, le=12)
    # Storylines from quiet (0) through realistic and dramatic to soap opera (3).
    drama: int | None = Field(default=None, ge=0, le=3)
    # Kitchen ups and downs (companion/life/kitchen.py), on the same scale.
    kitchen_realism: int | None = Field(default=None, ge=0, le=3)
    # Reading, watching and listening (companion/life/media.py), on the same scale.
    media_realism: int | None = Field(default=None, ge=0, le=3)
    # "MM-DD", or empty to forget it (companion/life/occasions.py).
    # Replies wait while the companion is at work or asleep (companion/life/pacing.py).
    paced_replies: bool | None = None
    # How quickly they read your texts while free (companion/life/reading.py): 0 at once, 1 quick, 2 natural, 3 slow.
    read_pace: int | None = Field(default=None, ge=0, le=3)
    # The shape of a new companion's family (companion/life/family_tree.py): 0 simple, 1 gentle, 2 true to life, 3 more.
    family_shapes: int | None = Field(default=None, ge=0, le=3)
    day_shifts: bool | None = None
    # Life admin calendar (companion/life/admin.py): 0 off, 1 light, 2 true to life, 3 dramatic.
    admin_realism: int | None = Field(default=None, ge=0, le=3)
    # Work life (companion/life/work.py): 0 off, 1 steady, 2 true to life, 3 dramatic.
    work_realism: int | None = Field(default=None, ge=0, le=3)
    # Group chat guests (companion/group_guests.py): how often someone named in a group is pulled in, 0 never to 3.
    guests_realism: int | None = Field(default=None, ge=0, le=3)
    # Hobbies that progress (companion/life/hobbies.py): 0 off, 1 light, 2 true to life, 3 dramatic.
    hobbies_realism: int | None = Field(default=None, ge=0, le=3)
    memes_realism: int | None = Field(default=None, ge=0, le=3)
    # Inner voice (companion/life/narrator.py): 0 just what happened, 1 a few thoughts, 2 true to life, 3 everything.
    inner_voice: int | None = Field(default=None, ge=0, le=3)
    # Their look in chat (companion/their_look.py): 0 off, 1 steady, 2 true to life, 3 expressive.
    their_look: int | None = Field(default=None, ge=0, le=3)
    # Waking them (companion/life/waking.py): 0 they never mind, 1 easygoing, 2 true to life, 3 it wears thin fast.
    waking_realism: int | None = Field(default=None, ge=0, le=3)
    # Getting together (companion/life/together.py): 0 never on their own, 1 light, 2 true to life, 3 often.
    together_realism: int | None = Field(default=None, ge=0, le=3)
    # Moving on (companion/life/onward.py): 0 never, 1 now and then, 2 true to life, 3 often.
    onward_realism: int | None = Field(default=None, ge=0, le=3)
    # Rough patches (companion/life/rough_patches.py): 0 off, 1 easy, 2 true to life, 3 dramatic.
    rough_patches_realism: int | None = Field(default=None, ge=0, le=3)
    # Next steps (companion/life/steps.py): 0 only when the user brings it up, 1 slow, 2 true to life, 3 fast.
    steps_pace: int | None = Field(default=None, ge=0, le=3)
    friends_fall: bool | None = None
    # Their own love life (companion/life/love_life.py): 0 nothing new, 1 quiet, 2 true to life, 3 lots going on.
    love_life: int | None = Field(default=None, ge=0, le=3)
    # Life's big turns (companion/life/big_turns.py): 0 off, 1 gentle (good turns only), 2 true to life, 3 eventful.
    life_turns: int | None = Field(default=None, ge=0, le=3)
    # Births and growing families (companion/life/families.py): 0 none, 1 now and then, 2 true to life, 3 lots.
    growing_families: int | None = Field(default=None, ge=0, le=3)
    # Our child (companion/life/our_child.py): 0 easy kids, 1 gentle, 2 true to life, 3 true-to-life chaos.
    family_life: int | None = Field(default=None, ge=0, le=3)
    # Loss and grief (companion/life/loss.py): whether people can pass away, and how often (0 rare ... 3 often).
    people_pass_away: bool | None = None
    loss: int | None = Field(default=None, ge=0, le=3)
    # Local politics (companion/life/politics.py): 0 off, 1 quiet, 2 true to life, 3 lively.
    politics_realism: int | None = Field(default=None, ge=0, le=3)
    # Trolls and snark on posts (companion/life/social.py): 0 off, 1 rivals only, 2 snarky, 3 trolls.
    trolls_realism: int | None = Field(default=None, ge=0, le=3)
    # Breaks and breakups (companion/life/breakups.py): on for real life and drama, off for an easy life.
    breakups: bool | None = None
    on_her_mind: bool | None = None
    model_routines: bool | None = None
    # Looks that change (companion/life/grooming.py): never (0), now and then, like real life, often (3).
    looks_realism: int | None = Field(default=None, ge=0, le=3)
    # Pets with lives of their own (companion/life/pets.py): 0 off, 1 light, 2 true to life, 3 dramatic.
    pets_realism: int | None = Field(default=None, ge=0, le=3)
    pets_can_die: bool | None = None
    # While you were away (companion/recap.py): days away before a catch-up shows; 0 turns it off.
    recap_after_days: int | None = Field(default=None, ge=0, le=60)
    # Home upkeep (companion/life/upkeep.py): 0 off, 1 light, 2 true to life, 3 messy.
    upkeep_realism: int | None = Field(default=None, ge=0, le=3)
    user_birthday: str | None = Field(default=None, pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')


class NotificationSettingsUpdate(Input):
    """Desktop notifications (PRD compute and job control). The cap's ceiling is the tested maximum."""
    enabled: bool | None = None
    quiet_start: str | None = Field(default=None, max_length=5)
    quiet_end: str | None = Field(default=None, max_length=5)
    preview: Literal['full', 'name', 'private'] | None = None
    daily_cap: int | None = Field(default=None, ge=1, le=6)
    min_gap_minutes: int | None = Field(default=None, ge=30, le=720)


class NotificationCheck(Input):
    focused: bool = False


class ContextLocation(Input):
    """The user's own city or region, typed by hand (PRD X1). Coordinates are optional."""
    user_place: str = Field(default='', max_length=120)
    user_latitude: float | None = Field(default=None, ge=-90, le=90)
    user_longitude: float | None = Field(default=None, ge=-180, le=180)


class ContextService(Input):
    name: str = Field(min_length=1, max_length=80)
    transport: Literal['stdio', 'http']
    # The program and its arguments, one item each (stdio only).
    command: list[Annotated[str, Field(max_length=1000)]] = Field(default_factory=list, max_length=40)
    url: str = Field(default='', max_length=2000)
    secret: str = Field(default='', max_length=4000)
    # The environment variable (stdio) or header (HTTP) that carries the key.
    secret_name: str = Field(default='', max_length=100)
    clear_secret: bool = False


class ContextLinks(Input):
    read_links: bool


class ContextPreset(Input):
    preset: Literal['parallel', 'exa', 'firecrawl']


class ContextBuiltin(Input):
    kind: Literal['weather', 'pulse', 'culture']


class ToolArgument(Input):
    source: Literal['place', 'latitude', 'longitude', 'topic', 'date', 'literal', 'url', 'session']
    value: str | int | float | bool | None = None


class ToolMapping(Input):
    tool: str = Field(min_length=1, max_length=128)
    arguments: dict[Annotated[str, Field(max_length=100)], ToolArgument] = Field(default_factory=dict, max_length=12)
    run_in: list[Literal['conversation', 'companion_city', 'ambient']] = Field(
        default_factory=lambda: ['conversation'], min_length=1, max_length=3)


class ToolApproval(Input):
    digest: str = Field(min_length=64, max_length=64)


class ContextLookup(Input):
    """A lookup the user starts from Settings to try a mapping."""
    category: Literal['weather', 'news', 'local_events']
    purpose: Literal['conversation', 'companion_city'] = 'conversation'
    topic: str = Field(default='', max_length=80)


class TimelineFork(Input):
    """Branch from here without text; Edit from here (the user's own messages) with the edited words."""
    message_id: str = Field(min_length=1, max_length=64)
    text: str | None = Field(default=None, min_length=1, max_length=40000)
    label: str = Field(default='', max_length=80)


class TimelineUpdate(Input):
    label: str | None = Field(default=None, max_length=80)
    clear_draft: bool | None = None


class StudyWorkspace(Input):
    """A Prospero's Study folder or its SQLite database file, opened read-only."""
    path: str = Field(min_length=1, max_length=2000)


class StudyCharacter(StudyWorkspace):
    character_id: str = Field(min_length=1, max_length=100)


class StudyImport(StudyCharacter):
    review_token: str = Field(min_length=64, max_length=64)


Gender = Literal['woman', 'man', 'nonbinary', '']
Birthday = Annotated[str, Field(pattern=r'^(?:(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))?$')]


# Lifespans (companion/world/lifespans.py `SPANS`): what How long they live offers, besides as their kind.
LIFESPANS = (80, 150, 300, 600, 1000)
# A persona's age: up to 120, and up to 5,000 for a long-lived kind (companion/worlds.py).
PERSONA_AGES = (120, 5000)


class PersonaPet(Input):
    """One of the user's own pets (companion/life/pets.py gives it a life): their words, never invented."""
    name: str = Field(min_length=1, max_length=40, pattern=r'\S')
    kind: str = Field(default='cat', min_length=1, max_length=20)
    looks: str = Field(default='', max_length=160)
    # Years old, when the user says; otherwise the pet keeps the birth date it was given.
    age: int | None = Field(default=None, ge=0, le=90)


class PictureMake(Input):
    """Make one: How you look as the form has it, saved before the picture is made; None keeps the saved words."""
    looks: str | None = Field(None, max_length=600)


class PersonaInput(Input):
    """Who the user is in a persona's worlds (companion/worlds.py). Only the user says this; blanks stay blank."""
    name: str | None = Field(None, max_length=80)
    gender: Gender | None = None
    # Past 120 only for a long-lived kind, picked below or read from About you (companion/worlds.py checks it).
    age: int | None = Field(None, ge=18, le=PERSONA_AGES[1])
    about: str | None = Field(None, max_length=2000)
    # How they look, for pictures of moments they share with a companion (companion/persona_pictures.py).
    looks: str | None = Field(None, max_length=600)
    birthday: Birthday | None = None
    pets: list[PersonaPet] | None = Field(None, max_length=8)
    # Kind and How long they live (companion/world/lifespans.py), as on the Character page: '' and None leave both to
    # their words, 0 years is "Doesn't age".
    kind: str | None = Field(None, max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = None

    @field_validator('lifespan')
    @classmethod
    def listed(cls, value):
        if value not in (None, 0, *LIFESPANS):
            raise ValueError('Pick one of the lifespans listed.')
        return value


class NewPersona(PersonaInput):
    """A new persona, and the city their world is in: the current one unless the user picks another, or
    `somewhere-new` for the app to pick (companion/worlds.py)."""
    city_id: str | None = Field(None, min_length=1, max_length=120)


class PersonaCopy(Input):
    """Where a copy of a persona gets their world (companion/worlds.py): as for a new persona."""
    city_id: str | None = Field(None, min_length=1, max_length=120)


class HomeChange(Input):
    """Where the user lives in a world (companion/life/where.py): a city and a neighbourhood there; a blank
    neighbourhood lets the app pick one."""
    city_id: str = Field(min_length=1, max_length=120)
    neighbourhood: str = Field(default='', max_length=120)


class WorldChange(Input):
    """Rename a world, or give it to another persona."""
    name: str | None = Field(None, max_length=80)
    persona_id: str | None = Field(None, min_length=1, max_length=100)


class Become(Input):
    """Become a townsperson (companion/worlds.py): the key of someone met around town."""
    key: str = Field(min_length=1, max_length=200)


class NewWorld(Input):
    """A new world: for the active persona and in the current city unless these say otherwise."""
    persona_id: str | None = Field(None, min_length=1, max_length=100)
    name: str | None = Field(None, max_length=80)
    city_id: str | None = Field(None, min_length=1, max_length=120)
    # Watch a city: the world starts just watching (companion/observer.py).
    watch: bool = False
    # Start in a past year (companion/world_year.py): its clock runs in that year at real speed.
    year: int | None = Field(None, ge=1990, le=9999)


class BackWhen(Input):
    """Go back to a year with a companion (companion/back_when.py): the main character unless another is named.
    `from_history` is "Work it out from our history", off: the two of you start as strangers."""
    year: int = Field(ge=1990, le=9999)
    from_history: bool = False
    companion_id: str | None = Field(None, min_length=1, max_length=100)


class RecapRead(Input):
    """The catch-up the user read, by the message it followed (companion/recap.py)."""
    since: str = Field(min_length=1, max_length=40)


class StatusUpdate(Input):
    """The user's status line for a companion (companion/life/status.py); empty lets the app write it."""
    text: str = Field(default='', max_length=200)




class KindChange(Input):
    """Someone's kind and How long they live, picked on their page: '' and None leave both to the app, 0 years is
    "Doesn't age" (companion/world/lifespans.py)."""
    kind: str = Field(default='', max_length=40, pattern=r'^[a-z0-9-]*$')
    lifespan: int | None = Field(default=None)

    @field_validator('lifespan')
    @classmethod
    def listed(cls, value):
        if value not in (None, 0, *LIFESPANS):
            raise ValueError('Pick one of the lifespans listed.')
        return value
