// TERRAIN - widget Scriptable
// Affiche l'information sport business du moment sur l'ecran d'accueil
// ou l'ecran verrouille de l'iPhone.
//
// Parametre du widget : FR (par defaut) ou INT.

const API = "https://terrain-0dgm.onrender.com/api/news";
const ACCENT = new Color("#5B8CFF");
const WHITE = new Color("#FFFFFF");
const GREY = new Color("#8E8E93");
const BLACK = new Color("#000000");

const LANG = (args.widgetParameter || "FR").trim().toUpperCase() === "INT" ? "INT" : "FR";
const COPY = {
  FR: { fallback: "Information indisponible", updated: (t) => `Mis à jour à ${t}` },
  INT: { fallback: "News unavailable", updated: (t) => `Updated at ${t}` },
};

// ---------------------------------------------------------------------------
// Donnees : reseau d'abord, dernier contenu connu en secours.
// ---------------------------------------------------------------------------

function cacheFile() {
  const fm = FileManager.local();
  return fm.joinPath(fm.cacheDirectory(), "terrain-news.json");
}

async function loadNews() {
  try {
    const req = new Request(API);
    req.timeoutInterval = 8;
    const data = await req.loadJSON();
    if (data && data.FR) {
      FileManager.local().writeString(cacheFile(), JSON.stringify(data));
      return data;
    }
  } catch (e) {
    // service endormi ou hors ligne : on retombe sur le cache
  }
  try {
    const fm = FileManager.local();
    const path = cacheFile();
    if (fm.fileExists(path)) return JSON.parse(fm.readString(path));
  } catch (e) {}
  return null;
}

function hostLabel(url) {
  try {
    const host = url.split("/")[2].replace(/^www\./, "").toLowerCase();
    return host.includes("google.") ? null : host;
  } catch (e) {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Rendu
// ---------------------------------------------------------------------------

function buildAccessory(item) {
  // Bandeau de l'ecran verrouille : iOS impose un rendu monochrome et compact.
  const w = new ListWidget();
  w.backgroundColor = new Color("#000000", 0);

  const cat = w.addText((item.category || "TERRAIN").toUpperCase());
  cat.font = Font.boldSystemFont(10);
  cat.textColor = WHITE;
  cat.lineLimit = 1;

  w.addSpacer(2);

  const head = w.addText(item.headline || "");
  head.font = Font.systemFont(12);
  head.textColor = WHITE;
  head.lineLimit = 2;
  head.minimumScaleFactor = 0.8;

  return w;
}

function buildHome(item, updated, family) {
  const w = new ListWidget();
  w.backgroundColor = BLACK;
  w.setPadding(14, 16, 14, 16);

  const big = family === "large";
  const small = family === "small";

  // Entete : pastille bleue et nom de l'app
  const header = w.addStack();
  header.centerAlignContent();
  const dot = header.addText("●");
  dot.font = Font.systemFont(7);
  dot.textColor = ACCENT;
  header.addSpacer(5);
  const name = header.addText("TERRAIN");
  name.font = Font.boldSystemFont(9);
  name.textColor = WHITE;
  header.addSpacer();
  const market = header.addText(LANG);
  market.font = Font.mediumSystemFont(9);
  market.textColor = GREY;

  w.addSpacer(small ? 8 : 12);

  const cat = w.addText((item.category || "").toUpperCase());
  cat.font = Font.boldSystemFont(small ? 8 : 9);
  cat.textColor = ACCENT;
  cat.lineLimit = 1;

  w.addSpacer(small ? 4 : 7);

  const head = w.addText(item.headline || COPY[LANG].fallback);
  head.font = Font.semiboldSystemFont(small ? 13 : big ? 22 : 16);
  head.textColor = WHITE;
  head.lineLimit = small ? 4 : big ? 6 : 3;
  head.minimumScaleFactor = 0.7;

  w.addSpacer();

  // Pied : media source et heure de derniere mise a jour
  const foot = w.addStack();
  foot.centerAlignContent();
  const host = hostLabel(item.url || "");
  if (host) {
    const src = foot.addText(host);
    src.font = Font.mediumSystemFont(small ? 8 : 9);
    src.textColor = GREY;
    src.lineLimit = 1;
  }
  foot.addSpacer();
  if (updated && !small) {
    const time = foot.addText(COPY[LANG].updated(updated));
    time.font = Font.systemFont(9);
    time.textColor = new Color("#5A5A5F");
  }

  return w;
}

// ---------------------------------------------------------------------------

const news = await loadNews();
const item = (news && news[LANG]) || { category: "", headline: COPY[LANG].fallback, url: "" };
const family = config.widgetFamily || "medium";

const widget = family.startsWith("accessory")
  ? buildAccessory(item)
  : buildHome(item, news && news.updated, family);

// Un appui sur le widget ouvre l'article, sinon l'application.
widget.url = /^https?:\/\//.test(item.url || "")
  ? item.url
  : "https://terrain-0dgm.onrender.com";

// Le moteur publie a l'heure pile et a la demie : on demande a iOS de repasser
// un quart d'heure plus tard. Le systeme reste maitre de la frequence reelle.
widget.refreshAfterDate = new Date(Date.now() + 15 * 60 * 1000);

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  await widget.presentMedium();
}
Script.complete();
