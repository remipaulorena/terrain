import os
import sys
import time
import ssl
import urllib.request
import feedparser
import schedule
import re
import json
import threading
import http.server
import socketserver

os.environ['TZ'] = 'Europe/Paris'
if hasattr(time, 'tzset'):
    time.tzset()

APP_NAME = "TERRAIN"

print(f"--> [START] Moteur {APP_NAME} (Sélection stricte Fait Pivot Sport Business)", flush=True)

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
# Les flux RSS bougent régulièrement. Lancer "python engine.py --test-sources"
# pour vérifier lesquels répondent avant de déployer.
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

# Signaux business : plus un titre en contient, plus il remonte dans la sélection.
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

# Bruit purement sportif : score pénalisé, on veut du business, pas du résultat.
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


def score_item(title, signals, noise):
    low = title.lower()
    score = sum(1 for s in signals if s in low)
    score -= sum(2 for n in noise if n in low)
    return score


def fetch_rss_items(sources, signals, noise):
    context = ssl._create_unverified_context()
    items = []
    seen_titles = set()

    for source in sources:
        try:
            req = urllib.request.Request(
                source["url"],
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
            )
            html = urllib.request.urlopen(req, context=context, timeout=8).read()
            feed = feedparser.parse(html)

            for index, entry in enumerate(feed.entries[:8]):
                title = getattr(entry, 'title', '').replace("\n", " ").strip()
                link = getattr(entry, 'link', '').strip()
                if link.startswith("/"):
                    link = source["domain"] + link

                if not title or title in seen_titles:
                    continue

                seen_titles.add(title)
                score = score_item(title, signals, noise)
                if index < 3:
                    score += 1

                items.append({
                    "title": title,
                    "link": link,
                    "source": source["name"],
                    "score": score
                })
        except Exception:
            continue

    items.sort(key=lambda x: x["score"], reverse=True)
    selection = [i for i in items if i["score"] > 0][:28] or items[:28]

    lines = []
    for i, item in enumerate(selection):
        badge = "[SIGNAL_FORT]" if i < 8 else "[SECONDAIRE]"
        lines.append(f"{badge} [{item['source']}] TITRE: {item['title']} | LINK: {item['link']}")

    return "\n".join(lines)


def clean_url(raw_url):
    match = re.search(r'https?://[^\s"\'<>]+', raw_url)
    return match.group(0) if match else raw_url.strip()


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


def build_prompt(lang, news_list, current_h):
    if lang == "FR":
        return f"""
Voici la sélection des titres remontés par les médias spécialisés du sport business :
{news_list}

Information actuellement affichée : "{current_h}"

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

FORMAT DE SORTIE STRICT (AUCUN AUTRE MOT, AUCUNE BALISE) :
CATEGORIE|||TITRE|||LINK
"""

    return f"""
Here is the selection of headlines pulled from sports business media:
{news_list}

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

STRICT OUTPUT FORMAT (NO INTRO, NO LABELS):
CATEGORY|||HEADLINE|||LINK
"""


def call_gemini(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"❌ [GEMINI] Erreur SDK : {e}", flush=True)
        return None

    for m in ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-lite-latest"]:
        try:
            res = client.models.generate_content(model=m, contents=prompt)
            if res and res.text and "|||" in res.text:
                print(f"✅ [GEMINI OK] Modèle : {m}", flush=True)
                return res.text.strip()
        except Exception as err:
            print(f"  ↳ Tentative {m} : {str(err)[:120]}...", flush=True)
            continue
    return None


def call_anthropic(prompt):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print(f"❌ [ANTHROPIC] Erreur SDK : {e}", flush=True)
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
                print(f"✅ [ANTHROPIC OK] Modèle : {m}", flush=True)
                return text
        except Exception as err:
            print(f"  ↳ Tentative {m} : {str(err)[:120]}...", flush=True)
            continue
    return None


def evaluate_news(lang, news_list):
    if not news_list.strip():
        print(f"⚠️ [{lang}] Aucun titre récupéré depuis les flux.", flush=True)
        return None

    prompt = build_prompt(lang, news_list, current_news[lang]["headline"])

    order = [call_gemini, call_anthropic]
    if os.environ.get("LLM_PROVIDER", "").lower() == "anthropic":
        order = [call_anthropic, call_gemini]

    for provider in order:
        result = provider(prompt)
        if result:
            return result

    print(f"❌ [LLM] Aucun modèle n'a pu répondre pour {lang}.", flush=True)
    return None


def parse_result(lang, raw):
    parts = [p.strip() for p in raw.split("|||")]

    if len(parts) >= 3:
        category, headline, url = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        category, headline, url = "", parts[0], parts[1]
    else:
        return None

    allowed = CATEGORIES_FR if lang == "FR" else CATEGORIES_INT
    fallback = "Marché" if lang == "FR" else "Market"

    return {
        "category": sanitize_category(category, allowed, fallback),
        "headline": sanitize_headline(headline),
        "url": clean_url(url)
    }


def update_html_files():
    json_payload = json.dumps(current_news, ensure_ascii=False)

    for filename in ["app.html", "index.html"]:
        if not os.path.exists(filename):
            continue
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            pattern = r'(<script id="news-data" type="application/json">).*?(</script>)'
            replacement = rf'\1\n  {json_payload}\n  \2'

            new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception:
            pass


def check_and_update():
    print(f"\n[{time.strftime('%H:%M:%S')}] --- ÉVALUATION SPORT BUSINESS ---", flush=True)

    try:
        news_fr = fetch_rss_items(SOURCES_FR, BUSINESS_SIGNALS_FR, NOISE_FR)
        res_fr = evaluate_news("FR", news_fr)
        if res_fr:
            parsed = parse_result("FR", res_fr)
            if parsed and parsed["headline"]:
                current_news["FR"] = parsed
                print(f"📢 [FR] {parsed['category']} — {parsed['headline']}", flush=True)
    except Exception as e:
        print(f"⚠️ Erreur FR : {e}", flush=True)

    try:
        news_int = fetch_rss_items(SOURCES_INT, BUSINESS_SIGNALS_INT, NOISE_INT)
        res_int = evaluate_news("INT", news_int)
        if res_int:
            parsed = parse_result("INT", res_int)
            if parsed and parsed["headline"]:
                current_news["INT"] = parsed
                print(f"📢 [INT] {parsed['category']} — {parsed['headline']}", flush=True)
    except Exception as e:
        print(f"⚠️ Erreur INT : {e}", flush=True)

    current_news["updated"] = time.strftime("%H:%M")
    update_html_files()
    print("--- FIN ÉVALUATION ---\n", flush=True)


def test_sources():
    context = ssl._create_unverified_context()
    print(f"\n--- TEST DES FLUX {APP_NAME} ---\n", flush=True)

    for label, sources in [("FR", SOURCES_FR), ("INT", SOURCES_INT)]:
        print(f"[{label}]", flush=True)
        for source in sources:
            try:
                req = urllib.request.Request(
                    source["url"],
                    headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
                )
                html = urllib.request.urlopen(req, context=context, timeout=10).read()
                feed = feedparser.parse(html)
                count = len(feed.entries)
                if count:
                    print(f"  ✅ {source['name']} : {count} entrées | ex. {feed.entries[0].title[:70]}", flush=True)
                else:
                    print(f"  ⚠️ {source['name']} : flux joignable mais vide", flush=True)
            except Exception as e:
                print(f"  ❌ {source['name']} : {str(e)[:80]}", flush=True)
        print("", flush=True)


class TerrainHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ['/ping', '/cron', '/refresh']:
            threading.Thread(target=check_and_update, daemon=True).start()
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"OK - Refresh triggered")
            return

        if self.path.startswith('/api/news'):
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(json.dumps(current_news, ensure_ascii=False).encode('utf-8'))
            return

        if self.path == '/manifest.json':
            manifest_content = {
                "short_name": APP_NAME.title(),
                "name": f"{APP_NAME} — Sport business",
                "start_url": "/?pwa=1",
                "display": "standalone",
                "background_color": "#000000",
                "theme_color": "#000000"
            }
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(manifest_content, ensure_ascii=False).encode('utf-8'))
            return

        if self.path in ['/', '/index.html', '/app.html']:
            filename = "app.html" if os.path.exists("app.html") else "index.html"
            if os.path.exists(filename):
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                with open(filename, 'rb') as f:
                    self.wfile.write(f.read())
                return
        return super().do_GET()


def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), TerrainHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    if "--test-sources" in sys.argv:
        test_sources()
        sys.exit(0)

    threading.Thread(target=run_http_server, daemon=True).start()
    threading.Thread(target=check_and_update, daemon=True).start()

    schedule.every().hour.at(":00").do(lambda: threading.Thread(target=check_and_update, daemon=True).start())
    schedule.every().hour.at(":30").do(lambda: threading.Thread(target=check_and_update, daemon=True).start())

    while True:
        schedule.run_pending()
        time.sleep(1)
