import os
import sys
import time
import ssl
import base64
import urllib.request
import urllib.error
import feedparser
import schedule
import re
import json
import difflib
import threading
import http.server
import socketserver
from concurrent.futures import ThreadPoolExecutor

os.environ['TZ'] = 'Europe/Paris'
if hasattr(time, 'tzset'):
    time.tzset()

APP_NAME = "TERRAIN"
STATE_FILE = "state.json"
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'

FETCH_TIMEOUT = 6
RESOLVE_TIMEOUT = 6
VALIDATE_TIMEOUT = 5

print(f"--> [START] Moteur {APP_NAME} (Selection stricte Fait Pivot Sport Business)", flush=True)

current_news = {
    "updated": time.strftime("%H:%M"),
    "FR": {
        "category": "Sport business",
        "headline": "Analyse de l'industrie en cours...",
        "url": "https://news.google.fr"
    },
    "INT": {
        "category": "Sports business",
        "headline": "Industry analysis in progress...",
        "url": "https://news.google.com"
    }
}

# ---------------------------------------------------------------------------
# SOURCES
# Les flux RSS bougent regulierement. Lancer "python engine.py --test-sources"
# pour verifier lesquels repondent avant de deployer.
# ---------------------------------------------------------------------------

SOURCES_FR = [
    {"name": "Sport Buzz Business", "url": "https://www.sportbuzzbusiness.fr/feed", "domain": "https://www.sportbuzzbusiness.fr"},
    {"name": "Ecofoot", "url": "https://www.ecofoot.fr/feed/", "domain": "https://www.ecofoot.fr"},
    {"name": "Sport Stratégies", "url": "https://www.sportstrategies.com/feed/", "domain": "https://www.sportstrategies.com"},
    {"name": "Sportune", "url": "https://www.sportune.fr/feed", "domain": "https://www.sportune.fr"},
    {"name": "Google News Sport Business", "url": "https://news.google.com/rss/search?q=%22sport+business%22+OR+sponsoring+OR+%22droits+TV%22+OR+%22%C3%A9conomie+du+sport%22+when:2d&hl=fr&gl=FR&ceid=FR:fr", "domain": "https://news.google.com"},
    {"name": "Google News Économie Clubs", "url": "https://news.google.com/rss/search?q=(club+OR+ligue+OR+f%C3%A9d%C3%A9ration)+(rachat+OR+partenariat+OR+budget+OR+diffuseur)+when:2d&hl=fr&gl=FR&ceid=FR:fr", "domain": "https://news.google.com"}
]

SOURCES_INT = [
    {"name": "SportsPro", "url": "https://www.sportspromedia.com/feed/", "domain": "https://www.sportspromedia.com"},
    {"name": "SportBusiness", "url": "https://www.sportbusiness.com/feed/", "domain": "https://www.sportbusiness.com"},
    {"name": "Front Office Sports", "url": "https://frontofficesports.com/feed/", "domain": "https://frontofficesports.com"},
    {"name": "Sportico", "url": "https://www.sportico.com/feed/", "domain": "https://www.sportico.com"},
    {"name": "Google News Sports Business", "url": "https://news.google.com/rss/search?q=%22sports+business%22+OR+%22media+rights%22+OR+sponsorship+OR+%22club+valuation%22+when:2d&hl=en-US&gl=US&ceid=US:en", "domain": "https://news.google.com"},
    {"name": "Google News Sports Deals", "url": "https://news.google.com/rss/search?q=(league+OR+club+OR+federation)+(acquisition+OR+investment+OR+broadcast+OR+kit+deal)+when:2d&hl=en-US&gl=US&ceid=US:en", "domain": "https://news.google.com"}
]

# Signaux business : plus un titre en contient, plus il remonte dans la selection.
BUSINESS_SIGNALS_FR = {
    "droits tv", "droits médias", "diffuseur", "diffusion", "sponsoring", "sponsor", "naming",
    "partenariat", "partenaire", "contrat", "équipementier", "maillot", "levée de fonds",
    "rachat", "acquisition", "actionnaire", "investisseur", "investissement", "fonds",
    "chiffre d'affaires", "budget", "déficit", "dncg", "billetterie", "hospitalité",
    "fédération", "ligue", "lfp", "cio", "fifa", "uefa", "franchise", "valorisation",
    "merchandising", "marque", "stade", "enceinte", "abonnés", "audience", "millions",
    "milliards", "€", "recrutement", "emploi", "formation", "salaire", "masse salariale",
    "appel d'offres", "licence", "streaming", "paris sportifs", "jo", "coupe du monde",
    "transfert record", "indemnité", "prize money", "économie", "marché"
}

BUSINESS_SIGNALS_INT = {
    "media rights", "broadcast", "streaming", "sponsorship", "sponsor", "naming rights",
    "kit deal", "apparel", "partnership", "deal", "valuation", "funding", "investment",
    "private equity", "stake", "acquisition", "takeover", "owner", "revenue", "profit",
    "loss", "salary cap", "expansion", "franchise", "league", "federation", "fifa", "uefa",
    "ioc", "ticketing", "hospitality", "merchandising", "betting", "sportsbook",
    "billion", "million", "$", "£", "contract", "rights holder", "audience", "ratings",
    "market", "ipo", "sponsorship deal", "commercial"
}

# Bruit purement sportif : score penalise, on veut du business, pas du resultat.
NOISE_FR = {
    "revivez", "en direct", "direct :", "résumé", "les notes", "compo probable",
    "composition", "pronostic", "blessure", "blessé", "suspendu", "carton rouge",
    "but de", "score", "mi-temps", "classement du jour"
}

NOISE_INT = {
    "live blog", "live updates", "recap", "highlights", "box score", "injury report",
    "starting lineup", "final score", "halftime", "player ratings", "prediction"
}

COMMON_ACRONYMS = {
    "TV", "OTT", "VOD", "IA", "AI", "US", "USA", "UE", "EU", "UK",
    "FIFA", "UEFA", "CIO", "IOC", "LFP", "LNR", "LNB", "FFF", "FFR", "FFT", "FFBB",
    "NBA", "NFL", "NHL", "MLB", "MLS", "WNBA", "NCAA", "F1", "ATP", "WTA", "PGA", "LIV",
    "PSG", "OM", "OL", "ASSE", "RCT", "UBB", "RCF",
    "JO", "OG", "CDM", "CAN", "CDF", "DNCG", "RSE", "ESG",
    "PIB", "GDP", "TVA", "VAT", "CA", "CEO", "PDG", "CFO", "CMO", "COO", "DRH", "RH",
    "IPO", "M&A", "PE", "ROI", "KPI", "B2B", "B2C", "RSS", "API", "PPV",
    "DAZN", "ESPN", "BBC", "CBS", "NBC", "TF1", "M6", "L1", "L2", "PL"
}

CATEGORIES_FR = {
    "Droits TV", "Sponsoring", "Investissement", "Instances",
    "Événements", "Équipementiers", "Clubs", "Marché"
}

CATEGORIES_INT = {
    "Media rights", "Sponsorship", "Investment", "Governance",
    "Events", "Apparel", "Clubs", "Market"
}

SSL_CONTEXT = ssl._create_unverified_context()


# ---------------------------------------------------------------------------
# RESEAU
# ---------------------------------------------------------------------------

def http_get(url, timeout, max_bytes=None):
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, context=SSL_CONTEXT, timeout=timeout) as res:
        data = res.read(max_bytes) if max_bytes else res.read()
        return res.geturl(), data


def is_google_news(url):
    return "news.google." in (url or "")


# Domaines qui ne sont jamais un article : infrastructure, mesure d'audience,
# publicite, reseaux sociaux. Compares sur le domaine racine, pas en sous-chaine.
BLOCKED_DOMAINS = {
    "google.com", "google.fr", "google.co.uk", "google-analytics.com",
    "googletagmanager.com", "googleapis.com", "googleusercontent.com",
    "googlesyndication.com", "googleadservices.com", "gstatic.com", "ggpht.com",
    "doubleclick.net", "youtube.com", "youtu.be", "blogger.com", "gvt1.com",
    "facebook.com", "fbcdn.net", "twitter.com", "x.com", "t.co", "linkedin.com",
    "instagram.com", "pinterest.com", "whatsapp.com", "tiktok.com",
    "schema.org", "w3.org", "cloudflare.com", "jsdelivr.net", "cdnjs.com",
    "gmpg.org", "wp.com", "gravatar.com", "adobe.com", "sentry.io", "hotjar.com",
    "cookielaw.org", "onetrust.com", "didomi.io", "sddan.com", "criteo.com",
}


def host_of(url):
    try:
        return url.split("/")[2].lower().split("@")[-1].split(":")[0]
    except IndexError:
        return ""


def root_domain(host):
    """Domaine racine approximatif : suffisant pour comparer deux hotes."""
    parts = (host or "").replace("www.", "", 1).split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    # Gere les suffixes composes du type .co.uk / .com.au
    if parts[-2] in ("co", "com", "org", "net", "gov", "ac") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def is_publisher_url(url, expected_host=None):
    """Vrai si l'URL pointe vers un article de media.
    Trois conditions, chacune ayant deja laisse passer une erreur :
      - le domaine racine n'est pas un domaine technique (google-analytics et co),
      - l'URL a un vrai chemin d'article, pas une simple page d'accueil,
      - si le flux indique l'editeur, le domaine doit correspondre."""
    if not url or not url.startswith("http"):
        return False
    host = host_of(url)
    if len(host) < 4 or "." not in host:
        return False
    if root_domain(host) in BLOCKED_DOMAINS:
        return False

    path = url.split("/", 3)[3] if url.count("/") >= 3 else ""
    if len(path.strip("/")) < 3:
        return False

    if expected_host:
        return root_domain(host) == root_domain(expected_host)
    return True


def resolve_google_news(url, expected_host=None):
    """Remonte de l'URL encodee Google News vers l'article de l'editeur.
    Retourne l'URL d'origine si la resolution echoue."""
    if not is_google_news(url):
        return url
    # 1. L'identifiant Google encode souvent l'URL de l'editeur en base64.
    decoded = decode_google_news_id(url, expected_host)
    if decoded:
        return decoded

    # 2. Sinon on suit la redirection et on lit la page interstitielle.
    try:
        final_url, body = http_get(url, RESOLVE_TIMEOUT, max_bytes=200000)
        if final_url and is_publisher_url(final_url, expected_host):
            return final_url

        html = body.decode("utf-8", errors="ignore")
        match = re.search(r'data-n-au="(https?://[^"]+)"', html)
        if match and is_publisher_url(match.group(1), expected_host):
            return match.group(1)
        for candidate in re.findall(r'https?://[^\s"\'<>\\]+', html):
            if is_publisher_url(candidate, expected_host):
                return candidate
    except Exception:
        pass
    return url


def decode_google_news_id(url, expected_host=None):
    """Les identifiants d'articles Google News contiennent frequemment l'URL
    de l'editeur en base64. On la recupere sans appel reseau."""
    match = re.search(r'/(?:rss/)?(?:articles|read)/([A-Za-z0-9_\-]+)', url or "")
    if not match:
        return None
    token = match.group(1)
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:
        return None
    text = raw.decode("utf-8", errors="ignore")
    for candidate in re.findall(r'https?://[^\s\x00-\x1f"\'<>\\]+', text):
        candidate = candidate.rstrip('.,;)\x01\x02\x03')
        if is_publisher_url(candidate, expected_host):
            return candidate
    return None


def url_is_reachable(url):
    """Un lien est retenu s'il repond, meme derriere un paywall ou un anti-bot.
    Un 400 (URL malformee) et un 404 / 410 le disqualifient : c'est exactement
    ce que renvoyait Google sur les liens retapes par le modele."""
    if not url or not url.startswith("http"):
        return False
    try:
        http_get(url, VALIDATE_TIMEOUT, max_bytes=2048)
        return True
    except urllib.error.HTTPError as err:
        return err.code not in (400, 404, 410)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# COLLECTE
# ---------------------------------------------------------------------------

def score_item(title, signals, noise):
    low = title.lower()
    score = sum(1 for s in signals if s in low)
    score -= sum(2 for n in noise if n in low)
    return score


def fetch_one_source(source, signals, noise):
    items = []
    try:
        _, body = http_get(source["url"], FETCH_TIMEOUT)
        feed = feedparser.parse(body)
    except Exception:
        return items

    for index, entry in enumerate(feed.entries[:8]):
        title = getattr(entry, 'title', '').replace("\n", " ").strip()
        link = getattr(entry, 'link', '').strip()
        if link.startswith("/"):
            link = source["domain"] + link
        if not title or not link:
            continue

        # Google News indique l'editeur reel de l'article dans la balise <source>.
        # C'est la reference qui permet de verifier le lien resolu.
        publisher = getattr(entry, 'source', None) or {}
        publisher_host = host_of(publisher.get('href', '')) if hasattr(publisher, 'get') else ''
        publisher_name = (publisher.get('title', '') if hasattr(publisher, 'get') else '') or source["name"]

        score = score_item(title, signals, noise)
        if index < 3:
            score += 1
        # Un flux d'editeur donne un lien direct, donc une source toujours
        # affichable. On le prefere nettement a Google News, dont le lien doit
        # etre resolu et peut echouer.
        if not is_google_news(link):
            score += 4

        items.append({
            "title": title,
            "link": link,
            "source": publisher_name if is_google_news(link) else source["name"],
            "publisher_host": publisher_host,
            "score": score
        })
    return items


def collect_candidates(sources, signals, noise):
    """Interroge les flux en parallele et renvoie la liste des candidats numerotes."""
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        results = list(pool.map(lambda s: fetch_one_source(s, signals, noise), sources))

    items = []
    seen_titles = set()
    for chunk in results:
        for item in chunk:
            key = item["title"].lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            items.append(item)

    items.sort(key=lambda x: x["score"], reverse=True)
    selection = [i for i in items if i["score"] > 0][:32] or items[:32]

    selection = vet_links(selection)[:28]

    for position, item in enumerate(selection, start=1):
        item["id"] = position
    return selection


def vet_links(items):
    """Les liens sont assainis AVANT de montrer la liste au modele : le titre
    retenu a donc toujours un lien d'editeur qui fonctionne, et le lien affiche
    correspond toujours au titre affiche.
    Les liens issus des flux d'editeurs sont fiables par construction, seuls les
    liens Google News sont resolus puis testes."""
    def vet(item):
        if not is_google_news(item["link"]):
            return item
        expected = item.get("publisher_host") or None
        url = resolve_google_news(item["link"], expected)
        if not is_publisher_url(url, expected) or not url_is_reachable(url):
            return None
        item["link"] = url
        return item

    with ThreadPoolExecutor(max_workers=12) as pool:
        vetted = list(pool.map(vet, items))

    kept = [i for i in vetted if i]
    dropped = len(items) - len(kept)
    if dropped:
        print(f"  -> {dropped} lien(s) Google News ecarte(s), non resolus vers un editeur.", flush=True)
    return kept


def format_candidates(candidates):
    lines = []
    for item in candidates:
        badge = "[SIGNAL_FORT]" if item["id"] <= 8 else "[SECONDAIRE]"
        lines.append(f"[{item['id']:02d}] {badge} [{item['source']}] {item['title']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# NETTOYAGE
# ---------------------------------------------------------------------------

def sanitize_category(text, allowed, fallback):
    text = re.sub(r'[^\w\sÀ-ÿ&\'-]', '', text or '').strip()
    for cat in allowed:
        if cat.lower() == text.lower():
            return cat
    for cat in allowed:
        if cat.lower() in text.lower():
            return cat
    return fallback


def sanitize_headline(text):
    text = text.strip().strip('"').strip("'")
    text = re.sub(r'(?i)^\s*(?:REWRITTEN_HEADLINE|TITRE_REECRIT|HEADLINE|TITRE|TITLE|CATEGORIE|CATEGORY)\b[\s:]*', '', text)
    text = text.replace("|||", "").strip()
    text = text.replace("'", "’")

    words = text.split()
    letters = [c for c in text if c.isalpha()]
    if letters:
        upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if upper_ratio > 0.55:
            new_words = []
            for w in words:
                clean_w = re.sub(r'[^\w]', '', w).upper()
                has_figure = any(c.isdigit() or c in "€$£%" for c in w)
                if clean_w in COMMON_ACRONYMS or has_figure or re.match(r'^(?:[A-Z]\.){2,}$', w):
                    new_words.append(w.upper() if not has_figure else w)
                else:
                    new_words.append(w.lower())
            text = " ".join(new_words)
            if len(text) > 0:
                text = text[0].upper() + text[1:]
        else:
            new_words = []
            for w in words:
                clean_w = re.sub(r'[^\w]', '', w).upper()
                if clean_w in COMMON_ACRONYMS:
                    new_words.append(re.sub(r'\b' + clean_w + r'\b', clean_w, w, flags=re.IGNORECASE))
                else:
                    new_words.append(w)
            text = " ".join(new_words)

    return text.strip()


# ---------------------------------------------------------------------------
# PROMPTS
# Le modele ne renvoie jamais d'URL : il renvoie le numero du titre retenu.
# ---------------------------------------------------------------------------

def build_prompt(lang, candidates_block, current_h):
    if lang == "FR":
        return f"""
Voici la selection numerotee des titres remontes par les medias specialises du sport business :
{candidates_block}

Information actuellement affichee : "{current_h}"

RÔLE : Rédacteur en chef d'un média de veille dédié à l'industrie du sport.
LECTEURS : dirigeants de clubs, agences, marques, fédérations, écoles de commerce du sport.
MISSION : Extraire l'UNIQUE information qui structure le marché du sport à cet instant précis.

MÉCANIQUE DE SÉLECTION STRICTE :
1. TEST DU BUSINESS : ne retiens que ce qui touche l'argent, le pouvoir ou la structure du marché.
   Droits de diffusion, sponsoring et naming, rachat de club, levée de fonds, contrat équipementier,
   attribution d'un grand événement, décision d'une instance, résultats financiers, emploi et formation.
2. TEST DU CONSENSUS : privilégie un sujet couvert par plusieurs rédactions ou marqué [SIGNAL_FORT].
3. EXCLUSIONS TOTALES : résultats sportifs, comptes rendus de match, transferts de joueurs traités
   sous l'angle sportif, blessures, polémiques d'avant-match, contenus magazine froids.
   Un transfert n'est retenu que si le montant redessine le marché.
4. FORMAT & TON : direct, factuel, orienté chiffres. Le montant ou le chiffre clé passe en premier
   quand il existe. Deux-points autorisés (ex : "Droits TV : la LFP boucle un accord à 500 M€ par saison").
5. LONGUEUR : 50 à 75 caractères maximum.
6. MAJUSCULES : conserve les majuscules des noms propres, marques, clubs et sigles réels
   (LFP, UEFA, CIO, DAZN, NBA, JO, PSG, etc.), y compris après les deux-points.
7. TYPOGRAPHIE : apostrophe courbe (’) obligatoire. Pas de tiret cadratin.
8. CATÉGORIE : choisis exactement une valeur parmi cette liste, sans rien inventer :
   Droits TV, Sponsoring, Investissement, Instances, Événements, Équipementiers, Clubs, Marché.
9. NUMÉRO : indique le numéro à deux chiffres du titre source que tu as retenu, tel qu'il apparaît
   entre crochets dans la liste. N'écris jamais d'adresse web.

FORMAT DE SORTIE STRICT (AUCUN AUTRE MOT, AUCUNE BALISE) :
CATEGORIE|||TITRE|||NUMERO
"""

    return f"""
Here is the numbered selection of headlines pulled from sports business media:
{candidates_block}

Currently displayed headline: "{current_h}"

ROLE: Editor-in-chief of an industry watch product covering the business of sport.
READERS: club executives, agencies, brands, federations, sport business schools.
MISSION: Extract the SINGLE story reshaping the sports industry at this exact moment.

STRICT SELECTION MECHANICS:
1. BUSINESS TEST: keep only what moves money, power or market structure.
   Media rights, sponsorship and naming, club takeovers, funding rounds, apparel contracts,
   event hosting decisions, governing body rulings, financial results, jobs and workforce.
2. CONSENSUS TEST: prioritise stories covered by several newsrooms or flagged [SIGNAL_FORT].
3. STRICT EXCLUSIONS: match results, game recaps, player transfers covered from a sporting angle,
   injuries, pre-game controversy, soft magazine features.
   A transfer qualifies only if the fee reshapes the market.
4. FORMAT & TONE: direct, factual, figure-led. Lead with the number when there is one.
   Colons are allowed (e.g. "Media rights: NBA closes an 11-year, $76bn package").
5. STRICT LENGTH: 50 to 75 characters maximum.
6. CAPITALIZATION: keep exact case for proper nouns, brands, clubs and real acronyms
   (NBA, NFL, UEFA, IOC, DAZN, ESPN, F1, etc.), including after a colon.
7. TYPOGRAPHY: curly apostrophes (’). No em dash.
8. CATEGORY: pick exactly one value from this list, invent nothing:
   Media rights, Sponsorship, Investment, Governance, Events, Apparel, Clubs, Market.
9. NUMBER: give the two-digit number of the source headline you selected, exactly as it appears
   in brackets in the list. Never write a web address.

STRICT OUTPUT FORMAT (NO INTRO, NO LABELS):
CATEGORY|||HEADLINE|||NUMBER
"""


# ---------------------------------------------------------------------------
# MODELES
# ---------------------------------------------------------------------------

def call_anthropic(prompt):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"[ANTHROPIC] Erreur SDK : {e}", flush=True)
        return None

    for m in ["claude-haiku-4-5-20251001", "claude-sonnet-5"]:
        try:
            res = client.messages.create(
                model=m,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            text = "".join(block.text for block in res.content if block.type == "text").strip()
            if "|||" in text:
                print(f"[ANTHROPIC OK] Modele : {m}", flush=True)
                return text
        except Exception as err:
            print(f"  -> Tentative {m} : {str(err)[:120]}...", flush=True)
            continue
    return None


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"[GEMINI] SDK indisponible : {e}", flush=True)
        return None

    for m in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-lite-latest"]:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res and res.text and "|||" in res.text:
                print(f"[GEMINI OK] Modele : {m}", flush=True)
                return res.text.strip()
        except Exception as err:
            print(f"  -> Tentative {m} : {str(err)[:120]}...", flush=True)
            continue
    return None


def evaluate_news(lang, candidates_block):
    if not candidates_block.strip():
        print(f"[{lang}] Aucun titre recupere depuis les flux.", flush=True)
        return None

    prompt = build_prompt(lang, candidates_block, current_news[lang]["headline"])

    order = [call_anthropic, call_gemini]
    if os.environ.get("LLM_PROVIDER", "").lower() == "gemini":
        order = [call_gemini, call_anthropic]

    for provider in order:
        result = provider(prompt)
        if result:
            return result

    print(f"[LLM] Aucun modele n'a pu repondre pour {lang}.", flush=True)
    return None


# ---------------------------------------------------------------------------
# RESOLUTION DU LIEN
# ---------------------------------------------------------------------------

STOPWORDS = {
    "dans", "pour", "avec", "sans", "sous", "leur", "leurs", "cette", "cettes",
    "elle", "elles", "nous", "vous", "plus", "moins", "tout", "tous", "toute",
    "toutes", "entre", "apres", "avant", "chez", "vers", "depuis", "selon",
    "encore", "aussi", "mais", "donc", "alors", "quand", "comme", "meme",
    "with", "from", "that", "this", "they", "their", "will", "have", "been",
    "into", "over", "after", "before", "than", "them", "were", "what", "when",
    "sport", "sports", "news", "info", "article",
}


def significant_words(text):
    """Mots porteurs de sens d'un titre, sans accents ni mots outils."""
    normalized = (text or "").lower()
    for a, b in (("àâä", "a"), ("éèêë", "e"), ("îï", "i"), ("ôö", "o"),
                 ("ùûü", "u"), ("ç", "c")):
        for ch in a:
            normalized = normalized.replace(ch, b)
    words = re.findall(r"[a-z0-9€$£]{4,}", normalized)
    return {w for w in words if w not in STOPWORDS}


def titles_related(headline, source_title):
    """Le titre publie doit parler du meme sujet que le titre source.
    C'est ce controle qui empeche d'afficher un titre sur les droits TV
    au-dessus d'un lien vers un article sur le sponsoring maillot."""
    a, b = significant_words(headline), significant_words(source_title)
    if a & b:
        return True
    return difflib.SequenceMatcher(None, (headline or "").lower(),
                                   (source_title or "").lower()).ratio() >= 0.45


def match_candidate(raw_ref, headline, candidates):
    """Retrouve le candidat choisi par le modele : d'abord par numero, sinon par
    rapprochement du titre. Dans les deux cas le sujet doit concorder, sinon on
    ne publie rien : un lien qui ne correspond pas au titre est pire que pas de
    mise a jour du tout."""
    if not candidates:
        return None

    by_id = {c["id"]: c for c in candidates}
    ref = (raw_ref or "").strip()
    # Un numero, meme entoure de ponctuation. Jamais les chiffres d'une URL.
    candidate = None
    if "http" not in ref.lower():
        digits = re.findall(r'\d{1,2}', ref)
        if digits:
            candidate = by_id.get(int(digits[0]))

    if candidate and titles_related(headline, candidate["title"]):
        return candidate

    if candidate:
        print(f"  -> Numero {candidate['id']} incoherent avec le titre publie, verification par titre.", flush=True)

    titles = [c["title"] for c in candidates]
    close = difflib.get_close_matches(headline, titles, n=1, cutoff=0.30)
    if close:
        for c in candidates:
            if c["title"] == close[0] and titles_related(headline, c["title"]):
                print(f"  -> Rapprochement par titre : {c['title'][:60]}", flush=True)
                return c

    # Dernier essai : le candidat qui partage le plus de mots avec le titre publie.
    words = significant_words(headline)
    best, best_score = None, 0
    for c in candidates:
        overlap = len(words & significant_words(c["title"]))
        if overlap > best_score:
            best, best_score = c, overlap
    if best and best_score >= 2:
        print(f"  -> Rapprochement par mots-cles : {best['title'][:60]}", flush=True)
        return best

    print("  -> Impossible de relier le titre publie a une source, publication annulee.", flush=True)
    return None


def final_link(candidate):
    """Les liens ont deja ete assainis par vet_links : on refuse simplement de
    publier quoi que ce soit qui ne soit pas une URL d'editeur."""
    url = candidate.get("link", "")
    if is_google_news(url) or not is_publisher_url(url, candidate.get("publisher_host") or None):
        print("  -> Lien inexploitable pour le titre retenu, publication annulee.", flush=True)
        return None
    return url


def parse_result(lang, raw, candidates):
    parts = [p.strip() for p in raw.split("|||")]

    if len(parts) >= 3:
        category, headline, ref = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        category, headline, ref = "", parts[0], parts[1]
    else:
        return None

    allowed = CATEGORIES_FR if lang == "FR" else CATEGORIES_INT
    fallback = "Marché" if lang == "FR" else "Market"

    headline = sanitize_headline(headline)
    if not headline:
        return None

    candidate = match_candidate(ref, headline, candidates)
    if not candidate:
        return None

    url = final_link(candidate)
    if not url:
        return None

    return {
        "category": sanitize_category(category, allowed, fallback),
        "headline": headline,
        "url": url,
        "source": candidate["source"]
    }


# ---------------------------------------------------------------------------
# PERSISTANCE
# ---------------------------------------------------------------------------

def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(current_news, f, ensure_ascii=False)
    except Exception:
        pass


def sanitize_loaded_state():
    """Un etat sauvegarde par une version precedente peut contenir un lien
    douteux : on le vide plutot que de le reafficher."""
    for lang in ("FR", "INT"):
        url = current_news.get(lang, {}).get("url", "")
        if url and not is_publisher_url(url):
            print(f"[BOOT] Lien invalide ecarte pour {lang} : {url[:70]}", flush=True)
            current_news[lang]["url"] = ""


def load_state():
    """Au demarrage, on repart de la derniere information connue plutot que
    d'afficher un ecran d'attente : state.json d'abord, sinon le JSON embarque
    dans index.html livre avec le depot."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("FR", {}).get("headline"):
                current_news.update(data)
                sanitize_loaded_state()
                print("[BOOT] Etat repris depuis state.json", flush=True)
                return
    except Exception:
        pass

    for filename in ["app.html", "index.html"]:
        try:
            if not os.path.exists(filename):
                continue
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()
            match = re.search(r'<script id="news-data" type="application/json">(.*?)</script>', content, re.DOTALL)
            if match:
                data = json.loads(match.group(1).strip())
                if data.get("FR", {}).get("headline"):
                    current_news.update(data)
                    sanitize_loaded_state()
                    print(f"[BOOT] Etat repris depuis {filename}", flush=True)
                    return
        except Exception:
            continue


def update_html_files():
    json_payload = json.dumps(current_news, ensure_ascii=False)

    for filename in ["app.html", "index.html"]:
        if not os.path.exists(filename):
            continue
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = r'(<script id="news-data" type="application/json">).*?(</script>)'
            # Fonction de remplacement : evite toute interpretation des antislashs
            # presents dans le JSON (guillemets echappes, unicode).
            new_content = re.sub(
                pattern,
                lambda m: f'{m.group(1)}\n  {json_payload}\n  {m.group(2)}',
                content,
                flags=re.DOTALL
            )

            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CYCLE
# ---------------------------------------------------------------------------

_update_lock = threading.Lock()


def run_market(lang, sources, signals, noise):
    candidates = collect_candidates(sources, signals, noise)
    if not candidates:
        print(f"[{lang}] Aucun flux exploitable.", flush=True)
        return
    raw = evaluate_news(lang, format_candidates(candidates))
    if not raw:
        return
    parsed = parse_result(lang, raw, candidates)
    if parsed and parsed["headline"]:
        current_news[lang] = parsed
        print(f"[{lang}] {parsed['category']} - {parsed['headline']}", flush=True)
        print(f"     source : {parsed['source']} | {parsed['url'][:100]}", flush=True)


def check_and_update():
    if not _update_lock.acquire(blocking=False):
        print("[SKIP] Une evaluation est deja en cours.", flush=True)
        return

    started = time.time()
    try:
        print(f"\n[{time.strftime('%H:%M:%S')}] --- EVALUATION SPORT BUSINESS ---", flush=True)
        for lang, sources, signals, noise in [
            ("FR", SOURCES_FR, BUSINESS_SIGNALS_FR, NOISE_FR),
            ("INT", SOURCES_INT, BUSINESS_SIGNALS_INT, NOISE_INT),
        ]:
            try:
                run_market(lang, sources, signals, noise)
            except Exception as e:
                print(f"Erreur {lang} : {e}", flush=True)

        current_news["updated"] = time.strftime("%H:%M")
        save_state()
        update_html_files()
        print(f"--- FIN EVALUATION ({time.time() - started:.1f}s) ---\n", flush=True)
    finally:
        _update_lock.release()


def test_sources():
    print(f"\n--- TEST DES FLUX {APP_NAME} ---\n", flush=True)
    for label, sources in [("FR", SOURCES_FR), ("INT", SOURCES_INT)]:
        print(f"[{label}]", flush=True)
        for source in sources:
            try:
                _, body = http_get(source["url"], 10)
                feed = feedparser.parse(body)
                count = len(feed.entries)
                if count:
                    print(f"  OK {source['name']} : {count} entrees | ex. {feed.entries[0].title[:70]}", flush=True)
                else:
                    print(f"  VIDE {source['name']} : flux joignable mais vide", flush=True)
            except Exception as e:
                print(f"  KO {source['name']} : {str(e)[:80]}", flush=True)
        print("", flush=True)


def test_links():
    """Verifie que chaque lien candidat repond, avec resolution Google News."""
    print(f"\n--- TEST DES LIENS {APP_NAME} ---\n", flush=True)
    for label, sources, signals, noise in [
        ("FR", SOURCES_FR, BUSINESS_SIGNALS_FR, NOISE_FR),
        ("INT", SOURCES_INT, BUSINESS_SIGNALS_INT, NOISE_INT),
    ]:
        print(f"[{label}]", flush=True)
        for item in collect_candidates(sources, signals, noise)[:12]:
            url = item["link"]
            status = "OK  " if url_is_reachable(url) else "MORT"
            print(f"  {status} [{item['id']:02d}] {item['title'][:50]} -> {url[:85]}", flush=True)
        print("", flush=True)


# ---------------------------------------------------------------------------
# SERVEUR
# ---------------------------------------------------------------------------

WIDGET_PAGE = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>TERRAIN — widget iPhone</title>
<style>
 *{box-sizing:border-box;margin:0;padding:0;-webkit-font-smoothing:antialiased}
 body{background:#000;color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      padding:calc(env(safe-area-inset-top,20px) + 20px) 20px calc(env(safe-area-inset-bottom,20px) + 28px);
      line-height:1.5}
 h1{font-size:1.05rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:4px}
 .sub{color:#8E8E93;font-size:.82rem;margin-bottom:22px}
 ol{margin:0 0 22px 18px;font-size:.88rem;color:#D8D8DC}
 ol li{margin-bottom:7px}
 button{width:100%;border:none;border-radius:14px;background:#5B8CFF;color:#fff;
        font-size:1rem;font-weight:600;padding:15px;cursor:pointer;-webkit-tap-highlight-color:transparent}
 button:active{opacity:.75}
 .done{background:#1E1E20;color:#5B8CFF}
 textarea{width:100%;height:230px;margin-top:18px;background:#0C0C0D;color:#9A9AA0;
          border:1px solid #232326;border-radius:12px;padding:12px;font-family:ui-monospace,Menlo,monospace;
          font-size:.66rem;line-height:1.35}
 .note{color:#5A5A5F;font-size:.74rem;margin-top:14px}
 a{color:#5B8CFF}
</style></head><body>
<h1>Widget TERRAIN</h1>
<div class="sub">Pour l'écran d'accueil et l'écran verrouillé de l'iPhone.</div>
<ol>
  <li>Installe <a href="https://apps.apple.com/app/scriptable/id1405459188">Scriptable</a> depuis l'App Store, c'est gratuit.</li>
  <li>Appuie sur le bouton bleu ci-dessous pour copier le script.</li>
  <li>Ouvre Scriptable, appuie sur le + en haut à droite, colle, puis renomme le script TERRAIN.</li>
  <li>Reviens à l'écran d'accueil, appui long, +, cherche Scriptable, choisis la taille bandeau.</li>
  <li>Appui long sur le widget, Modifier le widget, Script : TERRAIN. Paramètre : FR ou INT.</li>
</ol>
<button id="copy">Copier le script</button>
<textarea readonly id="code">__SCRIPT__</textarea>
<div class="note">Si le bouton ne fonctionne pas, appuie longuement dans le cadre, Tout sélectionner, puis Copier.</div>
<script>
document.getElementById('copy').addEventListener('click', async function () {
  var ta = document.getElementById('code');
  try {
    await navigator.clipboard.writeText(ta.value);
  } catch (e) {
    ta.focus(); ta.setSelectionRange(0, ta.value.length); document.execCommand('copy');
  }
  this.textContent = 'Script copié';
  this.className = 'done';
});
</script>
</body></html>"""


def build_widget_page():
    try:
        with open("widget-terrain.js", "r", encoding="utf-8") as f:
            script = f.read()
    except Exception:
        script = "// widget-terrain.js introuvable sur le serveur"
    escaped = script.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return WIDGET_PAGE.replace("__SCRIPT__", escaped)


class TerrainHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, body, content_type, cache="no-cache, no-store, must-revalidate"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', cache)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Ping de maintien en eveil : reponse immediate, aucun appel modele.
        if self.path in ['/healthz', '/health', '/up']:
            self._send("OK", 'text/plain; charset=utf-8')
            return

        if self.path in ['/ping', '/cron', '/refresh']:
            threading.Thread(target=check_and_update, daemon=True).start()
            self._send("OK - Refresh triggered", 'text/plain; charset=utf-8')
            return

        if self.path.startswith('/api/news'):
            body = json.dumps(current_news, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == '/manifest.json':
            manifest_content = {
                "id": "/",
                "short_name": APP_NAME.title(),
                "name": f"{APP_NAME} — Sport business",
                "description": "L'info qui compte dans le sport business, une seule à la fois.",
                "start_url": "/?pwa=1",
                "scope": "/",
                "display": "standalone",
                "orientation": "portrait",
                "background_color": "#000000",
                "theme_color": "#000000",
                "lang": "fr",
                "icons": [
                    {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                    {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                    {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
                ]
            }
            self._send(json.dumps(manifest_content, ensure_ascii=False),
                       'application/json; charset=utf-8', cache="public, max-age=3600")
            return

        # Page d'installation du widget iPhone : elle affiche le script
        # Scriptable et permet de le copier d'un seul appui, depuis le telephone.
        if self.path in ['/widget', '/widget/']:
            self._send(build_widget_page(), 'text/html; charset=utf-8')
            return

        # Le service worker ne doit jamais etre servi depuis un cache navigateur,
        # sinon une mise a jour de l'app ne se propage plus.
        if self.path == '/sw.js':
            if os.path.exists("sw.js"):
                with open("sw.js", 'rb') as f:
                    self._send(f.read(), 'application/javascript; charset=utf-8')
                return

        if self.path in ['/', '/index.html', '/app.html']:
            filename = "app.html" if os.path.exists("app.html") else "index.html"
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    self._send(f.read(), 'text/html; charset=utf-8')
                return
        return super().do_GET()


class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    with ThreadedServer(("", port), TerrainHandler) as httpd:
        print(f"[HTTP] {APP_NAME} en ecoute sur le port {port}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    if "--test-sources" in sys.argv:
        test_sources()
        sys.exit(0)

    if "--test-links" in sys.argv:
        test_links()
        sys.exit(0)

    load_state()

    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=check_and_update, daemon=True).start()

    schedule.every().hour.at(":00").do(lambda: threading.Thread(target=check_and_update, daemon=True).start())
    schedule.every().hour.at(":30").do(lambda: threading.Thread(target=check_and_update, daemon=True).start())

    while True:
        schedule.run_pending()
        time.sleep(1)
