import argparse
import asyncio
import html
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import websockets
from transformers import pipeline

from storage import get_post_count, has_post, init_db, save_post, set_metadata


# ============================================================
# CONFIGURATION
# ============================================================

JETSTREAM_URL = (
    "wss://jetstream.us-east.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents"
    "?collections=app.bsky.feed.post&kinds=commit"
)

BLUESKY_SEARCH_URLS = [
    "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
    "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts",
]

# Twenty configured Mastodon websites.
# An instance may be unavailable or may restrict anonymous API access.
MASTODON_INSTANCES = [
    "https://mastodon.nl",
    "https://mastodon.social",
    "https://mastodon.world",
    "https://mstdn.social",
    "https://fosstodon.org",
    "https://hachyderm.io",
    "https://mas.to",
    "https://techhub.social",
    "https://universeodon.com",
    "https://aus.social",
    "https://mastodon.uno",
    "https://mastodon.art",
    "https://mastodon.green",
    "https://mastodon.online",
    "https://mstdn.jp",
    "https://social.tchncs.de",
    "https://mastodonapp.uk",
    "https://kolektiva.social",
    "https://social.vivaldi.net",
    "https://mastodon.xyz",
]

# Public RSS feeds from general news providers and rail-focused publishers.
# These are news feeds, not social-comment APIs; articles are only admitted
# when their text contains a specific rail disruption/passenger-service signal.
RSS_FEEDS = [
    # The original ten general-news feeds. They are useful as supplementary
    # coverage, but most entries will not be about railway passenger experience.
    {"name": "NOS Nieuws", "url": "https://feeds.nos.nl/nosnieuwsalgemeen"},
    {"name": "NH Nieuws", "url": "https://rss.nhnieuws.nl/rss"},
    {"name": "Omroep West", "url": "https://www.omroepwest.nl/rss/index.xml"},
    {"name": "Rijnmond", "url": "https://www.rijnmond.nl/rss/index.xml"},
    {"name": "RTV Utrecht", "url": "https://www.rtvutrecht.nl/rss/nieuws.xml"},
    {"name": "RTV Noord", "url": "https://www.rtvnoord.nl/rss/index.xml"},
    {"name": "Omroep Brabant", "url": "https://www.omroepbrabant.nl/rss"},
    {"name": "Omroep Gelderland", "url": "https://www.gld.nl/rss/index.xml"},
    {"name": "RTL Nieuws", "url": "https://www.rtlnieuws.nl/rss.xml"},
    {"name": "NU.nl", "url": "http://www.nu.nl/feeds/rss/algemeen.rss"},

    # More rail-focused feeds, publicly linked by the publisher/site.
    {"name": "NS Nieuws", "url": "https://nieuws.ns.nl/feed/nl"},
    {"name": "NS Blog", "url": "https://nieuws.ns.nl/tagfeed/nl/tags/blog"},
    {"name": "Treinreiziger.nl", "url": "https://www.treinreiziger.nl/feed/"},
    {"name": "Omroep Flevoland", "url": "https://www.omroepflevoland.nl/RSS/"},
]

RSS_INTERVAL = 180
RSS_MAX_ITEMS_PER_FEED = 100

# Hacker News comments are collected via Algolia's public HN search API.
# This is a supplementary English-language source, not a primary Dutch
# passenger-feedback source. Strict context checks require Dutch-network
# context plus a railway and service/disruption signal.
HACKER_NEWS_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
HACKER_NEWS_SEARCH_TERMS = [
    "ProRail",
    "NS train",
    "Dutch railway",
    "Netherlands train",
    "Amsterdam train",
    "train delay",
    "train cancellation",
    "railway disruption",
]
HACKER_NEWS_INTERVAL = 180
HACKER_NEWS_LIMIT = 100

BLUESKY_SEARCH_TERMS = [
    "trein",
    "treinen",
    "treinstoring",
    "treinvertraging",
    "vertraging trein",
    "storing NS",
    "spoorwerkzaamheden",
    "wisselstoring",
    "overvolle trein",
    "geen zitplaats trein",
    "sprinter",
    "intercity",
    "station NS",
    "OV-chipkaart",
    "Arriva trein",
    "ProRail",
    "reisplanner NS",
    "lift station",
    "trein valt uit",
    "treinen rijden niet",
    "aansluiting gemist",
    "volle trein",
    "te druk in de trein",
    "lift kapot station",
    "ns app werkt niet",
    "ovpay werkt niet",
    "treinkaartje duur",
    "vertraging Utrecht",
]

MASTODON_TAGS = [
    # Rotate through a wider range of Dutch rail and passenger-experience tags.
    # poll_mastodon still requests only two tags per instance per cycle, so this
    # improves topical coverage without multiplying request volume per cycle.
    "trein",
    "treinstoring",
    "vertraging",
    "ns",
    "station",
    "spoor",
    "ov",
    "intercity",
    "treinvertraging",
    "treinuitval",
    "treinreiziger",
    "openbaarvervoer",
    "ovchipkaart",
    "spoorwerkzaamheden",
    "reisplanner",
    "nsapp",
]

BACKFILL_TAGS = [
    "trein",
    "ns",
    "storing",
    "station",
    "ov",
]

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"

COLLECTION_SECONDS = 48 * 60 * 60
BLUESKY_SEARCH_INTERVAL = 120
MASTODON_INTERVAL = 300
TARGET_POSTS = 300

HTTP_TIMEOUT = 12
MAX_CONCURRENT_REQUESTS = 8
BLUESKY_LIMIT = 100
MASTODON_LIMIT = 40

USER_AGENT = "RailPulseHackathon/1.3 (student project; public posts only)"

DISABLED_INSTANCES = set()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("rail_pulse.log", encoding="utf-8"),
    ],
)


# ============================================================
# KEYWORDS AND TOPICS
# ============================================================

def words(value):
    return [
        part.strip()
        for part in value.split("|")
        if part.strip()
    ]


# Include the standalone Dutch rail operator name: many passenger posts say
# only “NS” plus an experience/complaint, without repeating “trein” or “spoor”.
RAIL_KEYWORDS = words("""
ns|ns.nl|train|trains|railway|railways|railroad|railroads|
commuter rail|train station|train service|trein|treinen|treinreis|treinreizen|
treinstoring|treinstoringen|treinvertraging|treinvertragingen|
treinverkeer|treinuitval|spoor|
spoorlijn|spoorwegen|spoorwerkzaamheden|wisselstoring|seinstoring|
sprinter|intercity|perron|station|stations|ov-chipkaart|
ns international|ns app|prorail|arriva|blauwnet|
nederlandse spoorwegen|reisplanner|ovpay|treinstel
""")

# Passenger/service signals include complaints and positive experiences.
# They only count when a separate railway reference (or Mastodon topic tag)
# is also present, so unrelated opinions are not admitted.
PASSENGER_KEYWORDS = words("""
vertraging|vertraagd|treinvertraging|treinvertragingen|storing|storingen|
treinstoring|treinstoringen|spoorstoring|uitgevallen|treinuitval|
treinen uitgevallen|uitgevallen trein|geannuleerd|geschrapt|rijdt niet|
rijden niet|geen trein|geen treinen|omleiding|omgeleid|stremming|
gestremd|gestrand|gestrande|spoorwerkzaamheden|treinverkeer verstoord|
treinverkeer stilgelegd|vertraging op het spoor|trein botst|aanrijding met trein|
trein ontspoord|wisselstoring|seinstoring|
overvol|overvolle|stampvol|geen zitplaats|volle trein|drukke trein|
drukte in de trein|te druk in de trein|te vol in de trein|
geen plek om te zitten|volle coupe|volle coupé|
vertraging gemeld|aansluiting gemist|overstap gemist|
airco kapot|geen airco|warm in de trein|koud in de trein|
oncomfortabel reizen|
lift kapot|lift defect|lift werkt niet|lift buiten gebruik|
roltrap kapot|rolstoel|niet toegankelijk|perron afgesloten|
wc kapot|toilet kapot|wifi werkt niet|
geen informatie|verkeerde informatie|onjuiste informatie|
onduidelijke informatie|geen omroep|reisplanner werkt niet|
ns app werkt niet|app werkt niet|
ov-chipkaart werkt niet|ovpay werkt niet|
treinkaartje duur|treinabonnement duur|te duur voor de trein|
prijsverhoging|inchecken lukt niet|uitchecken lukt niet|
geld terug bij vertraging|compensatie bij vertraging|
klantenservice onbereikbaar|klacht over de trein|klacht over ns|
klagen over ns|slechte service|goede service|
onveilige situatie in de trein|veiligheid in de trein|
vieze trein|trein is vies|schone trein|
fijn reizen|prettig reizen|goed geregeld bij ns|
goed geholpen door ns|comfortabel reizen|reiservaring|
reizigerservaring|trein rijdt op tijd|op tijd rijden|
punctueel|vertragingen|reiscomfort|
|slecht|goed|geweldig|verschrikkelijk|vervelend|belachelijk|waardeloos|
|irritant|frustrerend|chaos|ellende|onbetrouwbaar|druk|drukte|
|lang wachten|wachten|gewacht|probleem|problemen|klacht|ervaring|
|prima|teleurgesteld|blij|boos|woedend|stilstaan|stil staan|
|stilgestaan|te laat|later|gemist|aansluiting|service|comfort|
|beter|slechter|dramatisch|dramatische|drama|ramp|rampzalig|schandalig|
|onacceptabel|kut|klote|afschuwelijk|uitstekend|top|slecht geregeld|
|goed geregeld|teleurstellend|geweldig geregeld|belachelijke service|
|fijn|leuk|fantastisch|heerlijk|prima|frustrerende|irritant|irritante|
|waanzinnig|waardeloze service|not running|no trains|train delay|delayed|
|late|cancellation|cancelled|canceled|disruption|crowded|overcrowded|
|no seat|broken lift|no information|unreliable|awful|terrible|ridiculous|
|missed connection|too expensive|great service|good service|bad service|
|disappointed|excellent|wonderful|comfortable
""")

NL_RAIL_SIGNALS = words("""
ns|ns.nl|ns app|nederlandse spoorwegen|prorail|ov-chipkaart|ovpay|
9292|arriva|breng|qbuzz|keolis|blauwnet|gvb|ret|htm|r-net|
trein|treinen|treinstoring|treinvertraging|sprinter|intercity|spoor|
amsterdam|utrecht|rotterdam|den haag|leiden|schiphol|arnhem|
groningen|zwolle|eindhoven|breda|nijmegen|maastricht|delft|haarlem|
alkmaar|almere|amersfoort|den bosch|tilburg|deventer|hilversum|
dordrecht|gouda|leeuwarden|enschede|apeldoorn|venlo|roosendaal
""")


# RSS is general news, so it must match a specific passenger-facing rail issue;
# generic words such as "goed", "slecht", or "probleem" are intentionally absent.
RSS_RAIL_SIGNALS = words("""
vertraging|vertraagd|treinvertraging|treinstoring|treinstoringen|
wisselstoring|seinstoring|storing op het spoor|storing aan het spoor|
spoorstoring|treinuitval|treinen uitgevallen|trein uitgevallen|
uitgevallen trein|trein rijdt niet|treinen rijden niet|geen treinen|
geen trein|minder treinen|treinverkeer verstoord|treinverkeer stilgelegd|
stremming|gestremd|omleiding|omgeleid|spoorwerkzaamheden|
vertraging op het spoor|trein strandde|trein gestrand|trein botst|
aanrijding met trein|aanrijding op het spoor|trein ontspoord|
overvolle trein|volle trein|geen zitplaats|geen plek om te zitten|
lift defect op station|lift buiten gebruik op station|perron afgesloten|
NS waarschuwt voor vertraging|NS meldt storing|ProRail meldt storing
""")

HACKER_NEWS_RAIL_SIGNALS = words("""
train|trains|railway|railways|railroad|railroads|commuter rail|train station|
train service|passenger train|rail network|rail transport
""")

HACKER_NEWS_SERVICE_SIGNALS = words("""
delay|delayed|late|cancellation|cancelled|canceled|disruption|disrupted|
service suspended|service stopped|not running|no trains|missed connection|
missed transfer|overcrowded|crowded train|packed train|ticket price|
train ticket|ticketing|strike|broken lift|inaccessible station|platform closed|
refund|compensation|rail replacement bus|replacement bus|rail works
""")

HACKER_NEWS_NL_SIGNALS = words("""
netherlands|dutch|proRail|nederlandse spoorwegen|amsterdam|utrecht|rotterdam|
the hague|den haag|schiphol|eindhoven|leiden|arnhem|groningen|zwolle|
breda|nijmegen|maastricht|delft|haarlem|almere|amersfoort|ns international
""")

TOPICS = {
    "Delays and cancellations": words(
        "vertraging|vertraagd|storing|uitgevallen|geannuleerd|geschrapt|"
        "rijdt niet|geen trein|omleiding|stremming|gestrand|wisselstoring|"
        "seinstoring|spoorwerkzaamheden"
    ),
    "Crowding and comfort": words(
        "overvol|overvolle|stampvol|geen zitplaats|volle trein|te druk|"
        "te vol|drukte in de trein|airco kapot|comfortabel reizen|"
        "warm in de trein|koud in de trein"
    ),
    "Accessibility and facilities": words(
        "lift kapot|lift defect|lift werkt niet|roltrap kapot|rolstoel|"
        "niet toegankelijk|perron afgesloten|wc kapot|toilet kapot|wifi werkt niet"
    ),
    "Passenger information": words(
        "geen informatie|verkeerde informatie|onjuiste informatie|"
        "onduidelijke informatie|geen omroep|reisplanner werkt niet|"
        "ns app werkt niet|app werkt niet"
    ),
    "Tickets and customer service": words(
        "ov-chipkaart werkt niet|ovpay werkt niet|treinkaartje duur|"
        "treinabonnement duur|te duur voor de trein|prijsverhoging|"
        "inchecken lukt niet|uitchecken lukt niet|geld terug bij vertraging|"
        "compensatie bij vertraging|klantenservice onbereikbaar|"
        "klacht over de trein|klacht over ns|slechte service"
    ),
    "Passenger experience": words(
        "fijn reizen|prettig reizen|goed geregeld bij ns|"
        "goed geholpen door ns|comfortabel reizen|reiservaring|"
        "reizigerservaring|goede service|trein rijdt op tijd|"
        "op tijd rijden|punctueel|reiscomfort"
    ),
}


# ============================================================
# TEXT AND DATE HELPERS
# ============================================================

def matches(text, keyword):
    if not isinstance(text, str) or not keyword:
        return False

    pattern = r"\s+".join(
        re.escape(part)
        for part in keyword.lower().split()
    )

    return re.search(
        r"\b" + pattern + r"\b",
        text.lower(),
    ) is not None


def matches_any(text, keywords):
    return any(matches(text, keyword) for keyword in keywords)


def parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, OverflowError):
        return None


def in_scope(text, languages=None, source_context=None):
    """
    Require a railway reference and a passenger-experience/service signal.
    A Mastodon hashtag can supply topic context when the post text relies on
    the hashtag rather than repeating the railway term in the sentence.
    """
    if not isinstance(text, str) or not text.strip():
        return False

    context = source_context if isinstance(source_context, str) else ""
    has_rail_reference = (
        matches_any(text, RAIL_KEYWORDS)
        or matches_any(context, RAIL_KEYWORDS)
    )
    if not has_rail_reference:
        return False

    has_passenger_signal = (
        matches_any(text, PASSENGER_KEYWORDS)
        or matches_any(context, PASSENGER_KEYWORDS)
    )
    if not has_passenger_signal:
        return False

    langs = {
        str(language).lower()
        for language in (languages or [])
    }

    if "nl" in langs:
        return True

    # Non-Dutch or unknown-language posts need a recognizable connection
    # to the Dutch railway network as well as the two relevance checks.
    return matches_any(text, NL_RAIL_SIGNALS) or matches_any(context, NL_RAIL_SIGNALS)


def hacker_news_in_scope(text):
    """Strictly identify HN comments about Dutch railway passenger service."""
    return (
        isinstance(text, str)
        and matches_any(text, HACKER_NEWS_RAIL_SIGNALS)
        and matches_any(text, HACKER_NEWS_SERVICE_SIGNALS)
        and matches_any(text, HACKER_NEWS_NL_SIGNALS)
    )


def get_topic(text):
    for topic, keywords in TOPICS.items():
        if matches_any(text, keywords):
            return topic

    return "General railway passenger experience"


def sentiment_label(prediction):
    try:
        stars = int(
            str(prediction.get("label", "")).split()[0]
        )
    except (ValueError, IndexError):
        return "neutral"

    if stars <= 2:
        return "negative"

    if stars == 3:
        return "neutral"

    return "positive"


def unpack_post(post):
    record = post.get("record") or {}

    languages = record.get("langs") or (
        [post["language"]]
        if post.get("language")
        else []
    )

    created_at = (
        record.get("createdAt")
        or post.get("indexedAt")
        or post.get("created_at")
        or ""
    )

    return (
        record.get("text", ""),
        created_at,
        post.get("uri", ""),
        languages,
    )


def get_json(url, timeout=HTTP_TIMEOUT):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )

    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fingerprint(text):
    """Normalize text to reduce duplicate copies across sources."""
    text = re.sub(r"https?://\S+", " ", text.lower())
    text = re.sub(r"#[\w-]+", " ", text)

    return re.sub(
        r"\W+",
        " ",
        text,
        flags=re.UNICODE,
    ).strip()


# ============================================================
# BLUESKY SEARCH
# ============================================================

def fetch_bluesky_search(query):
    params = urlencode({
        "q": query,
        "sort": "latest",
        "lang": "nl",
        "limit": BLUESKY_LIMIT,
    })

    last_error = None

    for base in BLUESKY_SEARCH_URLS:
        try:
            data = get_json(
                f"{base}?{params}",
                timeout=15,
            )

            if (
                not isinstance(data, dict)
                or not isinstance(data.get("posts", []), list)
            ):
                raise ValueError(
                    "Unexpected Bluesky search response"
                )

            output = []

            for item in data.get("posts", []):
                if not isinstance(item, dict):
                    continue

                post = item.get("post")

                if not isinstance(post, dict):
                    post = item

                record = post.get("record") or item.get("record") or {}

                if not isinstance(record, dict) or not record.get("text"):
                    continue

                output.append({
                    "record": record,
                    "uri": post.get("uri") or item.get("uri", ""),
                    # Keep API indexing time for live-window eligibility.
                    # The original createdAt remains in record for storage.
                    "indexedAt": (
                        post.get("indexedAt")
                        or record.get("createdAt")
                        or ""
                    ),
                    "_source": "Bluesky search",
                })

            return output

        except HTTPError as exc:
            last_error = exc

            if exc.code == 429:
                raise

            if exc.code not in (
                403, 404, 500, 502, 503, 504
            ):
                raise

        except (
            URLError,
            TimeoutError,
            OSError,
            ValueError,
        ) as exc:
            last_error = exc

    if last_error:
        raise last_error

    return []


# ============================================================
# MASTODON
# ============================================================

def fetch_mastodon_tag(instance, tag):
    url = (
        f"{instance}/api/v1/timelines/tag/"
        f"{quote(tag, safe='')}?limit={MASTODON_LIMIT}"
    )

    data = get_json(url, timeout=HTTP_TIMEOUT)

    if not isinstance(data, list):
        raise ValueError("Unexpected Mastodon response")

    output = []

    for status in data:
        if (
            not isinstance(status, dict)
            or status.get("visibility") != "public"
        ):
            continue

        raw = html.unescape(
            re.sub(r"<[^>]+>", " ", status.get("content", ""))
        )

        text = re.sub(r"\s+", " ", raw).strip()

        if not text:
            continue

        created_at = status.get("created_at", "")
        language = status.get("language")

        uri = (
            status.get("uri")
            or status.get("url")
            or f"{instance}/statuses/{status.get('id', '')}"
        )

        output.append({
            "record": {
                "text": text,
                "createdAt": created_at,
                "langs": [language] if language else [],
            },
            "uri": uri,
            "indexedAt": created_at,
            "_context_tag": tag,
            "_source": f"Mastodon #{tag} ({instance})",
        })

    return output



# ============================================================
# PUBLIC RSS NEWS FEEDS
# ============================================================

def _local_xml_name(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _element_text(element):
    if element is None:
        return ""
    return " ".join(part.strip() for part in element.itertext() if part.strip())


def _feed_timestamp(value):
    """Normalize RSS RFC-822 and Atom ISO dates; never invent timestamps."""
    if not value:
        return ""
    parsed = parse_time(value)
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(value.strip())
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            parsed = parsed.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return ""
    return parsed.isoformat(timespec="seconds")


def fetch_rss_feed(feed):
    """Fetch one public RSS/Atom feed and return only specific rail-service items."""
    request = Request(
        feed["url"],
        headers={
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
            "User-Agent": USER_AGENT,
        },
    )

    with urlopen(request, timeout=HTTP_TIMEOUT) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    output = []
    entries = [node for node in root.iter() if _local_xml_name(node.tag) in ("item", "entry")]

    for entry in entries[:RSS_MAX_ITEMS_PER_FEED]:
        fields = {}
        links = []
        for child in list(entry):
            name = _local_xml_name(child.tag)
            value = _element_text(child)
            if name == "link":
                href = child.attrib.get("href", "").strip()
                if href:
                    links.append(href)
                if value:
                    links.append(value)
            elif name not in fields or not fields[name]:
                fields[name] = value

        title = fields.get("title", "")
        description = fields.get("description", "") or fields.get("summary", "")
        content = fields.get("encoded", "") or fields.get("content", "")
        raw_text = " ".join(part for part in (title, description, content) if part)
        raw_text = html.unescape(raw_text)
        raw_text = re.sub(r"<[^>]+>", " ", raw_text)
        text = re.sub(r"\s+", " ", raw_text).strip()

        if not text or not matches_any(text, RAIL_KEYWORDS):
            continue
        if not matches_any(text, RSS_RAIL_SIGNALS):
            continue

        timestamp = _feed_timestamp(
            fields.get("pubdate", "")
            or fields.get("published", "")
            or fields.get("updated", "")
            or fields.get("date", "")
        )
        if not timestamp:
            # Skipping undated items is safer than assigning a false live time.
            continue

        uri = next((link for link in links if link.startswith("http")), "")
        if not uri:
            uri = fields.get("guid", "") or fields.get("id", "")

        output.append({
            "record": {
                "text": text,
                "createdAt": timestamp,
                "langs": ["nl"],
            },
            "uri": uri,
            # Use the item's actual publication time; do not re-label old feed
            # entries as newly observed live posts on every polling cycle.
            "indexedAt": timestamp,
            "_source": f"RSS — {feed['name']}",
        })

    return output


# ============================================================
# HACKER NEWS COMMENTS — PUBLIC ALGOLIA SEARCH API
# ============================================================

def fetch_hacker_news_search(query, since=None):
    """Fetch recent HN comments for a query, retaining only relevant Dutch-rail context."""
    params = {
        "query": query,
        "tags": "comment",
        "hitsPerPage": HACKER_NEWS_LIMIT,
    }
    if since is not None:
        if isinstance(since, datetime):
            since_dt = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        else:
            since_dt = parse_time(str(since))
        if since_dt is not None:
            params["numericFilters"] = f"created_at_i>{int(since_dt.timestamp())}"

    data = get_json(
        f"{HACKER_NEWS_SEARCH_URL}?{urlencode(params)}",
        timeout=HTTP_TIMEOUT,
    )
    hits = data.get("hits", []) if isinstance(data, dict) else []
    output = []

    for hit in hits:
        if not isinstance(hit, dict):
            continue
        comment_html = hit.get("comment_text") or ""
        title_html = hit.get("story_title") or hit.get("title") or ""
        comment = html.unescape(re.sub(r"<[^>]+>", " ", comment_html))
        story_title = html.unescape(re.sub(r"<[^>]+>", " ", title_html))
        comment = re.sub(r"\s+", " ", comment).strip()
        story_title = re.sub(r"\s+", " ", story_title).strip()
        if not comment:
            continue

        # Parent story title is retained as context; author/profile names are not.
        text = f"{story_title} — {comment}" if story_title else comment
        if not hacker_news_in_scope(text):
            continue

        created_at = hit.get("created_at_i")
        if not isinstance(created_at, (int, float)):
            continue
        try:
            timestamp = datetime.fromtimestamp(
                created_at, timezone.utc
            ).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError):
            continue

        item_id = str(hit.get("objectID") or "")
        if not item_id:
            continue

        output.append({
            "record": {
                "text": text,
                "createdAt": timestamp,
                "langs": ["en"],
            },
            "uri": f"https://news.ycombinator.com/item?id={item_id}",
            "indexedAt": timestamp,
            "_stream_time": timestamp,
            "_source": "Hacker News comments",
        })

    return output


# ============================================================
# BLUESKY JETSTREAM
# ============================================================

def normalize_jetstream(raw):
    event = json.loads(raw)

    # time_us describes when Jetstream emitted/observed the event. Keep it
    # separately from record.createdAt, the original publication timestamp.
    stream_time = None
    time_us = event.get("time_us")
    if isinstance(time_us, (int, float)):
        try:
            stream_time = datetime.fromtimestamp(
                time_us / 1_000_000, timezone.utc
            ).isoformat()
        except (OSError, OverflowError, TypeError, ValueError):
            stream_time = None

    # Standard Jetstream commit event.
    if event.get("kind") == "commit":
        commit = event.get("commit") or {}

        if (
            commit.get("operation") != "create"
            or commit.get("collection") != "app.bsky.feed.post"
        ):
            return None

        record = commit.get("record") or {}
        created_at = record.get("createdAt") or stream_time or ""

        did = event.get("did", "")
        rkey = commit.get("rkey", "")

    else:
        payload = event.get("payload") or {}

        if (
            payload.get("operation") != "create"
            or payload.get("collection") != "app.bsky.feed.post"
        ):
            return None

        record = payload.get("record") or {}

        stream_time = (
            stream_time
            or payload.get("time")
            or event.get("time")
            or None
        )
        created_at = (
            record.get("createdAt")
            or payload.get("time")
            or event.get("time")
            or stream_time
            or ""
        )

        did = payload.get("did", "")
        rkey = payload.get("rkey", "")

    if not isinstance(record, dict) or not record.get("text"):
        return None

    uri = (
        f"at://{did}/app.bsky.feed.post/{rkey}"
        if did and rkey
        else ""
    )

    return {
        "record": record,
        "uri": uri,
        "indexedAt": stream_time or created_at,
        "_stream_time": stream_time,
        "_source": "Bluesky Jetstream",
    }


# ============================================================
# FILTER, CLASSIFY, SAVE
# ============================================================

async def process_post(
    post,
    model,
    cutoff_time,
    stats,
    source_fallback,
    historical=False,
):
    text, post_time, uri, languages = unpack_post(post)

    if not isinstance(text, str) or not text.strip():
        stats["empty_text"] += 1
        return

    published = parse_time(post_time)

    if published is None:
        stats["invalid_timestamps"] += 1
        return

    # Backfill is judged by original publication time. During live collection,
    # use the source's arrival/index time so a newly observed post isn't
    # rejected merely because its original createdAt is older. The original
    # publication timestamp is still what we save below.
    if historical:
        eligibility_time = published
    else:
        eligibility_value = (
            post.get("_stream_time")
            or post.get("indexedAt")
            or post.get("indexed_at")
            or post_time
        )
        eligibility_time = parse_time(eligibility_value) or published

    if eligibility_time < cutoff_time:
        stats["too_old"] += 1
        return

    if published > datetime.now(timezone.utc) + timedelta(minutes=5):
        stats["future_timestamps"] += 1
        return

    # Count records that pass the live-time gate before topical filtering, so
    # the final report can distinguish freshness from relevance-filter yield.
    stats["timestamp_eligible"] += 1

    # Bluesky search results are already fetched using railway-related
    # queries. For these, a railway reference plus Dutch/network context is
    # enough. The global Jetstream stream keeps the stricter passenger filter.
    if source_fallback in ("Bluesky search", "Bluesky"):
        language_set = {
            str(language).lower()
            for language in (languages or [])
        }
        relevant_search_post = matches_any(text, RAIL_KEYWORDS) and (
            "nl" in language_set or matches_any(text, NL_RAIL_SIGNALS)
        )
        if not relevant_search_post:
            stats["out_of_scope"] += 1
            return
    elif source_fallback == "Hacker News":
        if not hacker_news_in_scope(text):
            stats["out_of_scope"] += 1
            return
    elif not in_scope(text, languages, post.get("_context_tag")):
        stats["out_of_scope"] += 1
        return

    stats["in_scope"] += 1

    key = fingerprint(text)

    if not key:
        stats["empty_text"] += 1
        return

    if key in stats["seen_this_run"]:
        stats["duplicates"] += 1
        return

    stats["seen_this_run"].add(key)

    if has_post(text, post_time, uri):
        stats["duplicates"] += 1
        return

    predictions = await asyncio.to_thread(
        model,
        text,
        truncation=True,
        max_length=256,
    )

    if not predictions:
        stats["model_errors"] += 1
        return

    prediction = predictions[0]
    topic = get_topic(text)
    sentiment = sentiment_label(prediction)

    saved = save_post(
        text,
        post_time,
        sentiment,
        topic,
        uri,
    )

    if not saved:
        stats["duplicates"] += 1
        return

    stats["saved"] += 1

    if historical:
        stats["backfill_saved"] += 1
    else:
        stats["live_saved"] += 1

    print("\n" + "=" * 56)

    if historical:
        print("RAIL PULSE POST SAVED — HISTORICAL BACKFILL")
    else:
        print("RAIL PULSE POST SAVED — LIVE COLLECTION")

    print("Source:", post.get("_source", source_fallback))
    print("Original publication time:", post_time)
    print("Topic:", topic)
    print(
        "Sentiment:", sentiment,
        "| Model:", prediction.get("label"),
        "| Score:", round(float(prediction.get("score", 0)), 3),
    )
    print("Text:", text[:500])

    print(
        f"Added in this run: {stats['saved']} | "
        f"Backfill: {stats['backfill_saved']} | "
        f"Live: {stats['live_saved']} | "
        f"Database: {get_post_count()}"
    )


# ============================================================
# INITIAL BACKFILL — PRESERVE ORIGINAL POST TIMESTAMPS
# ============================================================

async def backfill_recent(model, stats, hours):
    if hours <= 0:
        print("Historical backfill disabled.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    print(
        f"\nBackfilling public posts from the last {hours} hours. "
        "Original publication timestamps will be preserved."
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    jobs = []

    for term in BLUESKY_SEARCH_TERMS:
        jobs.append(("Bluesky", term, None))

    for site in MASTODON_INSTANCES:
        for tag in BACKFILL_TAGS:
            jobs.append(("Mastodon", tag, site))

    for feed in RSS_FEEDS:
        jobs.append(("RSS", feed, None))

    for term in HACKER_NEWS_SEARCH_TERMS:
        jobs.append(("Hacker News", term, None))

    async def fetch_job(source, query, site):
        async with semaphore:
            try:
                if source == "Bluesky":
                    posts = await asyncio.to_thread(
                        fetch_bluesky_search,
                        query,
                    )
                    return source, query, posts, None

                if source == "RSS":
                    posts = await asyncio.to_thread(fetch_rss_feed, query)
                    return f"RSS ({query['name']})", query["name"], posts, None

                if source == "Hacker News":
                    posts = await asyncio.to_thread(
                        fetch_hacker_news_search, query, cutoff
                    )
                    return source, query, posts, None

                posts = await asyncio.to_thread(
                    fetch_mastodon_tag,
                    site,
                    query,
                )

                return f"Mastodon ({site})", query, posts, None

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                return source, query, [], str(exc)

    results = await asyncio.gather(
        *(fetch_job(*job) for job in jobs)
    )

    total_returned = 0
    failed_jobs = 0

    for source, query, posts, error in results:
        if str(source).startswith("RSS"):
            stats["rss_requests"] += 1
            if error:
                stats["rss_errors"] += 1
            else:
                stats["rss_results"] += len(posts)
        elif source == "Hacker News":
            stats["hackernews_requests"] += 1
            if error:
                stats["hackernews_errors"] += 1
            else:
                stats["hackernews_results"] += len(posts)

        if error:
            failed_jobs += 1
            logging.warning(
                "Backfill source %s query %s failed: %s",
                source,
                query,
                error,
            )
            continue

        total_returned += len(posts)

        for post in posts:
            try:
                await process_post(
                    post,
                    model,
                    cutoff,
                    stats,
                    source,
                    historical=True,
                )

            except asyncio.CancelledError:
                raise

            except Exception:
                logging.exception(
                    "Backfill processing failed for %s",
                    source,
                )

    print(
        "\nBackfill source jobs:", len(jobs),
        "| Failed:", failed_jobs,
        "| Raw results:", total_returned,
    )

    print(
        "Historical posts added:", stats["backfill_saved"],
        "| Database total:", get_post_count(),
    )

    set_metadata(
        "last_backfill_at",
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ============================================================
# CONTINUOUS BLUESKY SEARCH
# ============================================================

async def poll_bluesky_search(
    model,
    started_dt,
    deadline,
    stop,
    stats,
):
    cycle = 0

    while not stop.is_set() and time.monotonic() < deadline:
        cycle_started = time.monotonic()
        returned = 0
        errors = 0

        for query in BLUESKY_SEARCH_TERMS:
            if stop.is_set() or time.monotonic() >= deadline:
                break

            try:
                posts = await asyncio.to_thread(
                    fetch_bluesky_search,
                    query,
                )

                stats["bluesky_search_requests"] += 1
                returned += len(posts)

                for post in posts:
                    try:
                        await process_post(
                            post,
                            model,
                            started_dt,
                            stats,
                            "Bluesky search",
                        )

                    except asyncio.CancelledError:
                        raise

                    except Exception:
                        logging.exception(
                            "Could not process Bluesky search result"
                        )

            except asyncio.CancelledError:
                raise

            except HTTPError as exc:
                errors += 1
                logging.warning(
                    "Bluesky query %r failed with HTTP %s",
                    query,
                    exc.code,
                )

                if exc.code == 429:
                    await asyncio.sleep(10)

            except (
                URLError,
                TimeoutError,
                OSError,
                ValueError,
            ) as exc:
                errors += 1
                logging.warning(
                    "Bluesky query %r failed: %s",
                    query,
                    exc,
                )

            await asyncio.sleep(0.1)

        cycle += 1

        logging.info(
            "Bluesky search cycle %s: %s results; %s request errors",
            cycle,
            returned,
            errors,
        )

        wait = max(
            0,
            BLUESKY_SEARCH_INTERVAL - (time.monotonic() - cycle_started),
        )

        try:
            await asyncio.wait_for(
                stop.wait(),
                timeout=min(
                    wait,
                    max(0, deadline - time.monotonic()),
                ),
            )

        except asyncio.TimeoutError:
            pass


# ============================================================
# CONTINUOUS MASTODON COLLECTION
# ============================================================

async def poll_mastodon(
    model,
    started_dt,
    deadline,
    stop,
    stats,
):
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    cycle = 0

    while not stop.is_set() and time.monotonic() < deadline:
        cycle_started = time.monotonic()

        offset = (cycle * 2) % len(MASTODON_TAGS)

        tags = [
            MASTODON_TAGS[offset],
            MASTODON_TAGS[(offset + 1) % len(MASTODON_TAGS)],
        ]

        jobs = [
            (site, tag)
            for site in MASTODON_INSTANCES
            if site not in DISABLED_INSTANCES
            for tag in tags
        ]

        async def fetch_one(site, tag):
            async with semaphore:
                try:
                    posts = await asyncio.to_thread(
                        fetch_mastodon_tag,
                        site,
                        tag,
                    )

                    return site, tag, posts, None

                except asyncio.CancelledError:
                    raise

                except HTTPError as exc:
                    if exc.code in (401, 403, 404, 422):
                        DISABLED_INSTANCES.add(site)

                        logging.warning(
                            "Disabling %s after HTTP %s: "
                            "anonymous hashtag access unavailable",
                            site,
                            exc.code,
                        )

                    return site, tag, [], f"HTTP {exc.code}"

                except (
                    URLError,
                    TimeoutError,
                    OSError,
                    ValueError,
                ) as exc:
                    return site, tag, [], str(exc)

        results = await asyncio.gather(
            *(fetch_one(site, tag) for site, tag in jobs)
        )

        total = 0
        active_sites = set()

        for site, tag, posts, error in results:
            if error:
                if site not in DISABLED_INSTANCES:
                    logging.warning(
                        "Mastodon %s #%s failed: %s",
                        site,
                        tag,
                        error,
                    )
                continue

            active_sites.add(site)
            stats["mastodon_requests"] += 1
            total += len(posts)

            for post in posts:
                try:
                    await process_post(
                        post,
                        model,
                        started_dt,
                        stats,
                        f"Mastodon ({site})",
                    )

                except asyncio.CancelledError:
                    raise

                except Exception:
                    logging.exception(
                        "Could not process Mastodon post from %s",
                        site,
                    )

        cycle += 1

        status = (
            f"Mastodon cycle {cycle}: "
            f"{len(active_sites)}/{len(MASTODON_INSTANCES)} responding | "
            f"{total} results | live saves: {stats['live_saved']}"
        )

        print(status)
        logging.info(status)

        wait = max(
            0,
            MASTODON_INTERVAL - (time.monotonic() - cycle_started),
        )

        try:
            await asyncio.wait_for(
                stop.wait(),
                timeout=min(
                    wait,
                    max(0, deadline - time.monotonic()),
                ),
            )

        except asyncio.TimeoutError:
            pass



# ============================================================
# CONTINUOUS RSS COLLECTION
# ============================================================

async def poll_rss_feeds(model, started_dt, deadline, stop, stats):
    cycle = 0
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def fetch_one(feed):
        async with semaphore:
            try:
                posts = await asyncio.to_thread(fetch_rss_feed, feed)
                return feed, posts, None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return feed, [], str(exc)

    while not stop.is_set() and time.monotonic() < deadline:
        cycle_started = time.monotonic()
        results = await asyncio.gather(*(fetch_one(feed) for feed in RSS_FEEDS))
        active = 0
        total = 0

        for feed, posts, error in results:
            stats["rss_requests"] += 1
            if error:
                stats["rss_errors"] += 1
                logging.warning("RSS feed %s failed: %s", feed["name"], error)
                continue

            active += 1
            total += len(posts)
            stats["rss_results"] += len(posts)

            for post in posts:
                try:
                    await process_post(
                        post, model, started_dt, stats,
                        f"RSS ({feed['name']})",
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.exception("Could not process RSS item from %s", feed["name"])

        cycle += 1
        status = (
            f"RSS cycle {cycle}: {active}/{len(RSS_FEEDS)} websites responding | "
            f"{total} relevant feed items | live saves: {stats['live_saved']}"
        )
        print(status)
        logging.info(status)

        wait = max(0, RSS_INTERVAL - (time.monotonic() - cycle_started))
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=min(wait, max(0, deadline - time.monotonic()))
            )
        except asyncio.TimeoutError:
            pass


# ============================================================
# CONTINUOUS HACKER NEWS COLLECTION
# ============================================================

async def poll_hacker_news(model, started_dt, deadline, stop, stats):
    cycle = 0
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def fetch_one(term):
        async with semaphore:
            try:
                posts = await asyncio.to_thread(
                    fetch_hacker_news_search, term, started_dt
                )
                return term, posts, None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                return term, [], str(exc)

    while not stop.is_set() and time.monotonic() < deadline:
        cycle_started = time.monotonic()
        results = await asyncio.gather(
            *(fetch_one(term) for term in HACKER_NEWS_SEARCH_TERMS)
        )
        relevant = 0
        errors = 0

        for term, posts, error in results:
            stats["hackernews_requests"] += 1
            if error:
                stats["hackernews_errors"] += 1
                errors += 1
                logging.warning("Hacker News query %r failed: %s", term, error)
                continue

            relevant += len(posts)
            stats["hackernews_results"] += len(posts)
            for post in posts:
                try:
                    await process_post(
                        post, model, started_dt, stats, "Hacker News"
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logging.exception("Could not process Hacker News comment")

        cycle += 1
        status = (
            f"Hacker News cycle {cycle}: {relevant} relevant comments | "
            f"{errors} query errors | live saves: {stats['live_saved']}"
        )
        print(status)
        logging.info(status)

        wait = max(0, HACKER_NEWS_INTERVAL - (time.monotonic() - cycle_started))
        try:
            await asyncio.wait_for(
                stop.wait(), timeout=min(wait, max(0, deadline - time.monotonic()))
            )
        except asyncio.TimeoutError:
            pass


# ============================================================
# BLUESKY JETSTREAM LISTENER
# ============================================================

async def consume_jetstream(
    model,
    started_dt,
    deadline,
    stop,
    stats,
):
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            async with websockets.connect(
                JETSTREAM_URL,
                subprotocols=["xrpc.v1.json"],
                ping_interval=20,
                ping_timeout=90,
                open_timeout=30,
                close_timeout=10,
                max_size=2**22,
            ) as ws:
                stats["jetstream_connections"] += 1
                print("Connected to Bluesky Jetstream.")

                while not stop.is_set() and time.monotonic() < deadline:
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(),
                            timeout=45,
                        )

                    except asyncio.TimeoutError:
                        continue

                    try:
                        post = normalize_jetstream(raw)

                    except (
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                    ):
                        stats["invalid_stream_messages"] += 1
                        continue

                    if post is None:
                        continue

                    stats["jetstream_posts_received"] += 1

                    try:
                        await process_post(
                            post,
                            model,
                            started_dt,
                            stats,
                            "Bluesky Jetstream",
                        )

                    except asyncio.CancelledError:
                        raise

                    except Exception:
                        logging.exception(
                            "Could not process Jetstream post"
                        )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            if not stop.is_set():
                logging.warning(
                    "Jetstream disconnected: %s; reconnecting in 5 seconds",
                    exc,
                )

                try:
                    await asyncio.wait_for(
                        stop.wait(),
                        timeout=5,
                    )

                except asyncio.TimeoutError:
                    pass


# ============================================================
# PROGRESS REPORT
# ============================================================

async def progress_reporter(
    stats,
    started_mono,
    duration,
    deadline,
    stop,
):
    while not stop.is_set() and time.monotonic() < deadline:
        try:
            await asyncio.wait_for(
                stop.wait(),
                timeout=300,
            )

        except asyncio.TimeoutError:
            hours = max(
                (time.monotonic() - started_mono) / 3600,
                1 / 60,
            )

            rate = stats["live_saved"] / hours
            projected = int(rate * (duration / 3600))

            print(
                f"\n[PROGRESS] "
                f"Backfill={stats['backfill_saved']} | "
                f"Live={stats['live_saved']} | "
                f"Live rate={rate:.2f}/hour | "
                f"Projected live posts={projected} | "
                f"DB={get_post_count()} | "
                f"Too old={stats['too_old']} | "
                f"Out of scope={stats['out_of_scope']} | "
                f"Duplicates={stats['duplicates']}\n"
            )


# ============================================================
# SOURCE CHECK
# ============================================================

async def check_source():
    print(
        f"Checking Bluesky, {len(MASTODON_INSTANCES)} Mastodon websites, "
        f"{len(RSS_FEEDS)} RSS feeds, and Hacker News; "
        "no collection timer starts."
    )

    try:
        posts = await asyncio.to_thread(
            fetch_bluesky_search,
            "trein",
        )

        print(f"Bluesky search: OK ({len(posts)} posts returned)")

    except Exception as exc:
        print("Bluesky search: FAILED -", exc)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def check_one(site):
        async with semaphore:
            try:
                posts = await asyncio.to_thread(
                    fetch_mastodon_tag,
                    site,
                    "trein",
                )

                return site, True, len(posts)

            except Exception as exc:
                return site, False, str(exc)

    results = await asyncio.gather(
        *(check_one(site) for site in MASTODON_INSTANCES)
    )

    working = 0

    for site, ok, detail in results:
        print(f"{'OK' if ok else 'UNAVAILABLE'} {site}: {detail}")
        working += int(ok)

    print(
        f"Mastodon sites responding: "
        f"{working}/{len(MASTODON_INSTANCES)}"
    )

    async def check_rss(feed):
        async with semaphore:
            try:
                items = await asyncio.to_thread(fetch_rss_feed, feed)
                return feed, True, len(items)
            except Exception as exc:
                return feed, False, str(exc)

    rss_results = await asyncio.gather(
        *(check_rss(feed) for feed in RSS_FEEDS)
    )
    rss_working = 0
    for feed, ok, detail in rss_results:
        if ok:
            print(f"OK RSS {feed['name']}: {detail} relevant items")
        else:
            print(f"UNAVAILABLE RSS {feed['name']}: {detail}")
        rss_working += int(ok)

    print(f"RSS feeds responding: {rss_working}/{len(RSS_FEEDS)}")
    unique_rss_hosts = len({feed["url"].split("/")[2].lower() for feed in RSS_FEEDS})
    print(f"Distinct RSS publisher domains configured: {unique_rss_hosts}")

    async def check_hn(term):
        async with semaphore:
            try:
                posts = await asyncio.to_thread(
                    fetch_hacker_news_search, term, None
                )
                return term, True, len(posts)
            except Exception as exc:
                return term, False, str(exc)

    hn_results = await asyncio.gather(
        *(check_hn(term) for term in HACKER_NEWS_SEARCH_TERMS)
    )
    hn_working = 0
    hn_relevant_total = 0
    for term, ok, detail in hn_results:
        if ok:
            print(f"OK Hacker News query {term!r}: {detail} relevant comments")
            hn_relevant_total += detail
        else:
            print(f"FAILED Hacker News query {term!r}: {detail}")
        hn_working += int(ok)

    print(
        f"Hacker News queries responding: "
        f"{hn_working}/{len(HACKER_NEWS_SEARCH_TERMS)}; "
        f"{hn_relevant_total} relevant query-results before deduplication"
    )

    print("No posts saved; no collection timer started.")


# ============================================================
# MAIN COLLECTION
# ============================================================

async def main(duration_seconds, backfill_hours):
    init_db()

    print("Loading the local sentiment model...")

    model = pipeline(
        "text-classification",
        model=MODEL_NAME,
        device=-1,
    )

    print("Model ready. Existing database rows:", get_post_count())

    stats = {
        "saved": 0,
        "backfill_saved": 0,
        "live_saved": 0,
        "duplicates": 0,
        "in_scope": 0,
        "timestamp_eligible": 0,
        "out_of_scope": 0,
        "too_old": 0,
        "future_timestamps": 0,
        "invalid_timestamps": 0,
        "empty_text": 0,
        "model_errors": 0,
        "invalid_stream_messages": 0,
        "jetstream_posts_received": 0,
        "jetstream_connections": 0,
        "bluesky_search_requests": 0,
        "mastodon_requests": 0,
        "rss_requests": 0,
        "rss_results": 0,
        "rss_errors": 0,
        "hackernews_requests": 0,
        "hackernews_results": 0,
        "hackernews_errors": 0,
        "seen_this_run": set(),
    }

    # Backfill preserves each post's real publication timestamp.
    # The 48-hour live timer starts after backfill completes.
    await backfill_recent(
        model,
        stats,
        backfill_hours,
    )

    started_dt = datetime.now(timezone.utc)
    started_at = started_dt.isoformat(timespec="seconds")

    loop = asyncio.get_running_loop()
    deadline = loop.time() + duration_seconds
    started_mono = time.monotonic()

    set_metadata("collection_started_at", started_at)
    set_metadata("collection_completed_at", "")

    stop = asyncio.Event()

    print("\nLIVE COLLECTION STARTED (UTC):", started_at)
    print(
        "Live sources: Bluesky Jetstream + Bluesky searches + up to 20 Mastodon "
        f"websites + {len(RSS_FEEDS)} RSS feeds + Hacker News comments"
    )
    print(f"Live duration: {duration_seconds / 3600:g} hours")
    print(
        "Historical backfill saved:",
        stats["backfill_saved"],
        "(original publication timestamps preserved)",
    )
    print(
        f"Goal: add {TARGET_POSTS} records across backfill + live. "
        "Live-only saves are reported separately."
    )
    print(
        "Existing database rows are not counted as new saves in this run."
    )
    print("Keep the terminal/computer running; Ctrl+C stops early.\n")

    tasks = [
        asyncio.create_task(
            consume_jetstream(
                model, started_dt, deadline, stop, stats
            )
        ),
        asyncio.create_task(
            poll_bluesky_search(
                model, started_dt, deadline, stop, stats
            )
        ),
        asyncio.create_task(
            poll_mastodon(
                model, started_dt, deadline, stop, stats
            )
        ),
        asyncio.create_task(
            poll_rss_feeds(
                model, started_dt, deadline, stop, stats
            )
        ),
        asyncio.create_task(
            poll_hacker_news(
                model, started_dt, deadline, stop, stats
            )
        ),
        asyncio.create_task(
            progress_reporter(
                stats,
                started_mono,
                duration_seconds,
                deadline,
                stop,
            )
        ),
    ]

    completed = False

    try:
        await asyncio.sleep(duration_seconds)
        completed = True

    finally:
        stop.set()

        for task in tasks:
            task.cancel()

        await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        if completed:
            set_metadata(
                "collection_completed_at",
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )

            print("\nLive collection window completed.")

        else:
            print("\nLive collection stopped early; run incomplete.")

        print("\n========== FINAL COLLECTION REPORT ==========")
        print("Historical backfill saves:", stats["backfill_saved"])
        print("New live saves:", stats["live_saved"])
        print(
            "Total new records added by this run:",
            stats["saved"],
            "/",
            TARGET_POSTS,
        )
        print("Jetstream posts received:", stats["jetstream_posts_received"])
        print("Bluesky search requests:", stats["bluesky_search_requests"])
        print("Mastodon requests:", stats["mastodon_requests"])
        print("RSS feed requests:", stats["rss_requests"])
        print("RSS relevant items returned:", stats["rss_results"])
        print("RSS feed errors:", stats["rss_errors"])
        print("RSS websites configured:", len(RSS_FEEDS))
        print("Hacker News requests:", stats["hackernews_requests"])
        print("Hacker News relevant comments returned:", stats["hackernews_results"])
        print("Hacker News errors:", stats["hackernews_errors"])
        print("Timestamp-eligible items checked by relevance filter:", stats["timestamp_eligible"])
        print("In-scope posts examined:", stats["in_scope"])
        print("Rejected as too old:", stats["too_old"])
        print("Rejected as out of scope:", stats["out_of_scope"])
        print("Invalid timestamps:", stats["invalid_timestamps"])
        print("Duplicates skipped:", stats["duplicates"])
        print("Database total:", get_post_count())
        print(
            "300-new-record goal reached across backfill + live:",
            stats["saved"] >= TARGET_POSTS,
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rail Pulse live sentiment collector with Hacker News"
    )

    parser.add_argument(
        "--check-source",
        action="store_true",
        help="Check APIs without saving posts or starting a timer",
    )

    parser.add_argument(
        "--test-minutes",
        type=int,
        default=0,
        help="Run a timed test instead of the default 48 hours",
    )

    parser.add_argument(
        "--backfill-hours",
        type=int,
        default=72,
        help="Import recent public posts with original timestamps; use 0 to disable",
    )

    args = parser.parse_args()

    try:
        if args.check_source:
            asyncio.run(check_source())

        else:
            duration = (
                args.test_minutes * 60
                if args.test_minutes > 0
                else COLLECTION_SECONDS
            )

            asyncio.run(
                main(
                    duration,
                    max(0, args.backfill_hours),
                )
            )

    except KeyboardInterrupt:
        print(
            "\nRail Pulse stopped manually. "
            "The live collection is incomplete."
        )