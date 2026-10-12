"""Keyword lexicons behind the rule-based analyzer and rule-based dating agent.

Used whenever no LLM is configured. Everything here matches literal words in the
scraped profile text, so each claim can quote the line that produced it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# label -> keywords. Matched on word boundaries, case-insensitively.
HOBBIES: dict[str, list[str]] = {
    "Hiking and trekking": ["hike", "hiking", "trek", "trekking", "trail", "trails", "summit", "backpacking"],
    "Running": ["running", "runner", "marathon", "half marathon", "5k", "10k", "ultramarathon"],
    "Gym and strength training": ["gym", "workout", "crossfit", "weightlifting", "lifting", "strength training", "fitness"],
    "Yoga and mindfulness": ["yoga", "meditation", "mindfulness", "pilates", "breathwork"],
    "Cycling": ["cycling", "cyclist", "bike ride", "biking", "bikepacking"],
    "Travel": ["travel", "traveler", "traveller", "traveling", "travelling", "wanderlust", "road trip", "roadtrip", "backpacker", "vacation", "holiday", "expedition"],
    "Photography": ["photography", "photographer", "photographed", "photo walk", "camera", "timelapse"],
    "Cooking and food": ["cooking", "recipe", "recipes", "chef", "baking", "foodie", "homemade", "brunch", "sourdough", "restaurant"],
    "Coffee": ["coffee", "espresso", "latte", "cafe", "café"],
    "Reading": ["reading", "reader", "book", "books", "novel", "bookclub", "book club"],
    "Writing": ["writing", "writer", "blog", "blogger", "blogging", "essay", "newsletter", "poetry", "poem", "author"],
    "Music": ["music", "concert", "guitar", "piano", "singing", "playlist", "gig", "vinyl", "jazz", "band", "album", "song"],
    "Dance": ["dance", "dancing", "dancer", "salsa", "ballet"],
    "Art and design": ["painting", "sketch", "sketching", "drawing", "illustration", "gallery", "ceramics", "pottery", "museum", "exhibition"],
    "Film and TV": ["film", "films", "movie", "movies", "cinema", "documentary", "filmmaking", "streaming"],
    "Gaming and chess": ["gaming", "gamer", "video game", "video games", "chess", "board game", "board games", "esports"],
    "Football": ["football", "soccer", "premier league", "fifa"],
    "Cricket": ["cricket", "ipl"],
    "Basketball": ["basketball", "nba"],
    "Racket sports": ["tennis", "badminton", "padel", "pickleball", "squash"],
    "Water sports": ["swimming", "surf", "surfing", "scuba", "diving", "sailing", "kayak", "kayaking", "kitesurfing", "kiteboarding", "paddleboard"],
    "Climbing": ["climbing", "bouldering", "mountaineering"],
    "Snow sports": ["ski", "skiing", "snowboard", "snowboarding"],
    "Golf": ["golf", "golfing"],
    "Nature and the outdoors": ["nature", "outdoors", "camping", "mountains", "beach", "sunset", "sunrise", "wildlife", "forest", "ocean", "island"],
    "Pets and animals": ["dog", "dogs", "puppy", "cat", "cats", "pets", "rescue"],
    "Fashion and style": ["fashion", "outfit", "ootd", "streetwear"],
    "Gardening": ["garden", "gardening", "plants"],
    "Podcasts": ["podcast", "podcasts"],
}

INTERESTS: dict[str, list[str]] = {
    "Artificial intelligence": ["artificial intelligence", "ai", "machine learning", "llm", "deep learning", "generative ai", "genai"],
    "Startups and entrepreneurship": ["startup", "startups", "founder", "co-founder", "cofounder", "entrepreneur", "entrepreneurship", "venture"],
    "Technology and software": ["software", "engineer", "engineering", "developer", "programming", "coding", "technology", "open source", "saas", "cloud"],
    "Product and design": ["product manager", "product design", "ux", "design thinking", "designer", "product management"],
    "Investing and finance": ["investing", "investor", "finance", "fintech", "venture capital", "stocks", "crypto", "markets", "banking"],
    "Climate and sustainability": ["climate", "sustainability", "sustainable", "renewable", "clean energy", "carbon", "global warming", "conservation"],
    "Health and medicine": ["healthcare", "global health", "public health", "mental health", "nutrition", "medicine", "vaccines", "malnutrition"],
    "Education and mentoring": ["education", "teaching", "teacher", "mentor", "mentoring", "students"],
    "Science and research": ["research", "science", "scientist", "phd", "physics", "biology", "astronomy"],
    "Marketing and storytelling": ["marketing", "brand", "branding", "storytelling", "content creator", "creator", "social media", "advertising"],
    "Leadership": ["leadership", "ceo", "chairman", "managing director", "chief executive", "head of"],
    "Philanthropy and social impact": ["philanthropy", "social impact", "foundation", "equity", "inclusion", "nonprofit", "charity", "humanitarian"],
    "Media and journalism": ["journalism", "journalist", "media", "editor", "reporter"],
    "Law and public policy": ["policy", "lawyer", "legal", "government", "public policy", "human rights"],
    "Space": ["space", "rocket", "aerospace", "satellite", "astronaut"],
    "Business and strategy": ["business", "strategy", "consulting", "mba", "operations", "sales"],
    "History and heritage": ["history", "heritage", "tradition", "anthropology", "archaeology"],
}


@dataclass(frozen=True)
class Signal:
    """One behavioural signal and what it implies about a person."""

    key: str
    keywords: tuple[str, ...]
    trait: str
    value: str
    need: str


SIGNALS: tuple[Signal, ...] = (
    Signal(
        "ambition",
        ("founder", "co-founder", "ceo", "entrepreneur", "built", "launched", "scaled", "startup", "chairman", "mission"),
        "Driven and ambitious",
        "Building things that matter",
        "A partner who respects a demanding, purpose-driven schedule",
    ),
    Signal(
        "curiosity",
        ("reader", "reading", "book", "books", "learning", "curious", "curiosity", "research", "phd", "science"),
        "Curious, lifelong learner",
        "Growth and learning",
        "Intellectual curiosity and conversations with real depth",
    ),
    Signal(
        "creativity",
        ("design", "designer", "artist", "photography", "photographer", "writer", "music", "creative", "filmmaker", "illustration", "painting"),
        "Creative and expressive",
        "Creativity and self-expression",
        "Room for creative pursuits, and someone who genuinely appreciates them",
    ),
    Signal(
        "community",
        ("volunteer", "volunteering", "community", "nonprofit", "mentor", "mentoring", "giving back", "philanthropy", "charity", "foundation", "generosity"),
        "Community-minded and generous",
        "Giving back",
        "Shared values around kindness and contribution",
    ),
    Signal(
        "adventure",
        ("travel", "traveler", "traveller", "adventure", "adventurer", "explore", "explorer", "expedition", "surf", "climbing", "thrill", "road trip", "wanderlust"),
        "Adventurous and open to new experiences",
        "Freedom and new experiences",
        "A companion who says yes to trips and new experiences",
    ),
    Signal(
        "active",
        ("gym", "fitness", "running", "marathon", "yoga", "workout", "cycling", "training", "hiking", "tennis", "swimming"),
        "Active and health-conscious",
        "Health and balance",
        "Someone who shares or supports an active lifestyle",
    ),
    Signal(
        "family",
        ("family", "kids", "children", "daughter", "son", "parents", "mom", "dad", "grandchildren", "siblings"),
        "Family-oriented",
        "Family and close relationships",
        "Someone who values family and long-term closeness",
    ),
    Signal(
        "expressive",
        ("blogger", "blog", "speaker", "podcast", "storytelling", "keynote", "newsletter", "author", "wrote", "sharing"),
        "Open communicator who shares ideas publicly",
        "Honest, open communication",
        "Open, engaged communication rather than guesswork",
    ),
    Signal(
        "nature",
        ("nature", "outdoors", "mountains", "wildlife", "ocean", "forest", "camping", "conservation", "island", "beach"),
        "Grounded, at home outdoors",
        "Nature and sustainability",
        "Unhurried time outdoors together",
    ),
    Signal(
        "social",
        ("friends", "party", "celebrate", "celebrating", "team", "crew", "together", "festival", "wedding", "hosting"),
        "Sociable and people-oriented",
        "Friendship and connection",
        "A partner comfortable with a full, social calendar",
    ),
    Signal(
        "food",
        ("cooking", "recipe", "chef", "foodie", "restaurant", "dinner", "brunch", "baking", "coffee", "wine"),
        "Enjoys good food and long meals",
        "Sharing meals and hospitality",
        "Someone to share long dinners and food discoveries with",
    ),
    Signal(
        "humour",
        ("joke", "funny", "laugh", "lol", "haha", "fool", "prank", "fun"),
        "Playful sense of humour",
        "Not taking life too seriously",
        "Someone who can laugh with them",
    ),
)

DATE_IDEAS: dict[str, str] = {
    "Hiking and trekking": "a morning trail walk followed by a slow coffee",
    "Running": "an easy run together, then brunch",
    "Gym and strength training": "an active date — a class or a climb — then something to eat",
    "Yoga and mindfulness": "a morning yoga class and an unhurried breakfast",
    "Cycling": "a bike ride to somewhere with good food at the end",
    "Travel": "a day trip to a place neither of them has been",
    "Photography": "a photo walk through an interesting neighbourhood",
    "Cooking and food": "cooking dinner together, or a food-market crawl",
    "Coffee": "a long conversation at an independent café",
    "Reading": "browsing a bookshop, then talking over what they picked",
    "Writing": "a quiet café and swapping the things they've written",
    "Music": "a live gig",
    "Dance": "a dance class neither has tried",
    "Art and design": "an afternoon at a gallery",
    "Film and TV": "a film, then a proper debrief over a drink",
    "Gaming and chess": "a board-game café",
    "Water sports": "a day on the water",
    "Climbing": "a bouldering session",
    "Nature and the outdoors": "a picnic somewhere green",
}

_STOPWORDS = {
    "with", "from", "that", "this", "have", "been", "were", "their", "about", "into",
    "over", "under", "after", "before", "and", "the", "for", "you", "your", "they",
    "them", "what", "when", "where", "which", "would", "could", "should", "someone",
    "something", "partner", "person", "people", "really", "very", "more", "most",
    "also", "just", "like", "than", "then", "there", "here", "does", "will", "shares",
    "share", "time", "things", "thing", "public", "profile", "profiles", "values",
    "open", "good", "real", "long", "life", "love", "loves", "enjoy", "enjoys",
    "based", "work", "works", "working",
}


@lru_cache(maxsize=2048)
def _pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(keyword) + r"(?![A-Za-z0-9])", re.IGNORECASE)


def content_lines(text: str) -> list[str]:
    """Profile lines worth matching against — skips the bracketed source header."""
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.startswith("[")]


def snippet(line: str, match: re.Match[str], width: int = 170) -> str:
    """The sentence around a keyword hit, kept verbatim so it validates as evidence."""
    start = max(
        (line.rfind(sep, 0, match.start()) for sep in (". ", "! ", "? ", "; ", ": ")),
        default=-1,
    )
    start = start + 2 if start >= 0 else 0
    end = min(
        (i for i in (line.find(sep, match.end()) for sep in (". ", "! ", "? ")) if i != -1),
        default=len(line),
    )
    piece = line[start : min(end + 1, len(line))].strip().strip('"-–• ')
    if len(piece) > width:
        lo = max(0, match.start() - start - width // 2)
        piece = piece[lo : lo + width].strip()
    return piece


_URL = re.compile(r"https?://\S+")


def find_hits(text: str, keywords: list[str] | tuple[str, ...]) -> tuple[int, str]:
    """Count keyword hits in a source and return the first supporting snippet."""
    count, evidence = 0, ""
    for line in content_lines(text):
        links = [m.span() for m in _URL.finditer(line)]
        for keyword in keywords:
            for match in _pattern(keyword).finditer(line):
                # Short-link slugs like "lnkd.in/g4Jyi-Ai" are not prose.
                if any(lo <= match.start() < hi for lo, hi in links):
                    continue
                count += 1
                if not evidence:
                    evidence = snippet(line, match)
    return count, evidence


@lru_cache(maxsize=16384)
def tokens(text: str) -> frozenset[str]:
    """Significant, crudely stemmed word tokens of a label."""
    out: set[str] = set()
    for word in re.findall(r"[A-Za-z][A-Za-z\-']{2,}", (text or "").lower()):
        if word in _STOPWORDS:
            continue
        for suffix in ("ing", "ers", "er", "es", "s"):
            if len(word) > len(suffix) + 3 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.add(word)
    return frozenset(out)


@lru_cache(maxsize=16384)
def topic_keys(text: str) -> frozenset[str]:
    """Lexicon topics a free-text label touches (hobby/interest labels + signal keys)."""
    keys: set[str] = set()
    for table in (HOBBIES, INTERESTS):
        for label, keywords in table.items():
            if any(_pattern(k).search(text or "") for k in keywords):
                keys.add(label)
    stripped = (text or "").strip().lower()
    for signal in SIGNALS:
        # A signal's own trait/value/need wording maps straight back to its key.
        own_wording = (signal.trait.lower(), signal.value.lower(), signal.need.lower())
        if stripped in own_wording or any(
            _pattern(k).search(text or "") for k in signal.keywords
        ):
            keys.add(signal.key)
    return frozenset(keys)


def related(a: str, b: str) -> bool:
    """True when two free-text labels are about the same thing."""
    if not a or not b:
        return False
    if a.strip().lower() == b.strip().lower():
        return True
    if tokens(a) & tokens(b):
        return True
    return bool(topic_keys(a) & topic_keys(b))
