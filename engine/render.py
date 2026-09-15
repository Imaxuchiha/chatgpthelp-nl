"""Statische sitegenerator: content/*.json → dist/. Geen dependencies buiten Pillow (beelden).
Mobile-first, één CSS-bestand, JSON-LD, RSS, sitemap + news-sitemap, AI-label op elk artikel
(EU AI Act art. 50), bronnen onder elk artikel."""
from __future__ import annotations

import html
import json
import re
import shutil
from datetime import datetime, timedelta

from . import images
from .config import ASSETS, CATEGORIES, DIST, SITE
from .editorial import load_articles, load_memes, load_prompts

MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]
E = html.escape


def nl_date(iso: str) -> str:
    d = datetime.fromisoformat(iso[:10])
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def rfc822(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return d.strftime("%a, %d %b %Y %H:%M:%S +0200")


def inline(text: str) -> str:
    t = E(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    return t


def prose(body: str) -> str:
    out = []
    for block in re.split(r"\n\s*\n", (body or "").strip()):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if all(re.match(r"^\s*[-•*]\s+", ln) for ln in lines):
            out.append("<ul>" + "".join(f"<li>{inline(re.sub(r'^\s*[-•*]\s+', '', ln))}</li>" for ln in lines) + "</ul>")
        elif all(re.match(r"^\s*\d+[.)]\s+", ln) for ln in lines):
            out.append("<ol>" + "".join(f"<li>{inline(re.sub(r'^\s*\d+[.)]\s+', '', ln))}</li>" for ln in lines) + "</ol>")
        elif lines[0].startswith(">"):
            out.append("<blockquote>" + inline(" ".join(ln.lstrip("> ") for ln in lines)) + "</blockquote>")
        elif lines[0].startswith("### "):
            out.append(f"<h3>{inline(lines[0][4:])}</h3>" + (f"<p>{inline(' '.join(lines[1:]))}</p>" if len(lines) > 1 else ""))
        else:
            out.append(f"<p>{inline(' '.join(lines))}</p>")
    return "\n".join(out)


def words(art: dict) -> int:
    t = " ".join([art.get("intro", "")] + [s.get("body", "") for s in art.get("sections", [])])
    return len(re.findall(r"\w+", t))


def page(title: str, desc: str, path: str, body: str, og: str = "/img/og-default.png", ldjson: list | None = None,
         kind: str = "website", extra_head: str = "", nav_on: str = "") -> str:
    url = SITE["url"] + path
    ld = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (ldjson or []))
    brand = f" | {SITE['name']}"
    full_title = title if SITE["name"] in title or len(title) + len(brand) > 62 else title + brand
    measure = ""
    if SITE.get("ga4"):
        measure = f"""<!-- GA4 met first-party analytics-cookies, zonder banner. Advertentie-opslag en -signalen staan uit. -->
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('consent','default',{{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'granted',functionality_storage:'granted',personalization_storage:'denied',security_storage:'granted'}});
gtag('set','allow_google_signals',false);gtag('set','allow_ad_personalization_signals',false);</script>
<script async src="https://www.googletagmanager.com/gtag/js?id={SITE['ga4']}"></script>
<script>gtag('js',new Date());gtag('config','{SITE['ga4']}',{{anonymize_ip:true}});</script>"""
    nav = "".join(
        f'<a href="/{slug}/"{" class=on" if nav_on == slug else ""}>{E(name)}</a>' for slug, (name, _) in CATEGORIES.items()
    ) + f'<a href="/prompts/"{" class=on" if nav_on == "prompts" else ""}>Prompts</a><a href="/memes/"{" class=on" if nav_on == "memes" else ""}>Memes</a>'
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
{measure}
<title>{E(full_title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="{kind}"><meta property="og:site_name" content="{E(SITE['name'])}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{SITE['url']}{og}"><meta property="og:locale" content="nl_NL">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/img/favicon.png" type="image/png"><link rel="apple-touch-icon" href="/img/logo.png">
<link rel="alternate" type="application/rss+xml" title="{E(SITE['name'])}" href="/feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=Inter:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/style.css?v=4">
{ld}{extra_head}
</head>
<body>
<div class="wrap">
<header class="topbar"><a class="logo" href="/"><i></i>ChatGPT<span style="color:var(--accent)">Help</span><small>.nl</small></a><span class="meta">AI-nieuws & uitleg · elke dag</span></header>
<nav class="main" aria-label="Rubrieken"><a href="/"{" class=on" if nav_on == "home" else ""}>Voorpagina</a>{nav}</nav>
<main>
{body}
</main>
<footer>
<div class="cols">
<div><strong>{E(SITE['name'])}</strong><br>{E(SITE['tagline'])}<br><br>Deze site wordt volledig door AI gemaakt en gepubliceerd, zonder menselijke eindredactie. Elk artikel vermeldt zijn bronnen. <a href="/over/">Hoe dat werkt</a>.</div>
<div><strong>Rubrieken</strong><br>{" · ".join(f'<a href="/{s}/">{E(n)}</a>' for s, (n, _) in CATEGORIES.items())}<br><a href="/prompts/">Prompt van de dag</a> · <a href="/memes/">Meme van de dag</a></div>
<div><strong>Over</strong><br><a href="/over/">Over deze site</a> · <a href="/privacy/">Privacy</a> · <a href="/feed.xml">RSS</a> · <a href="{SITE['bluesky']}" rel="me noopener" target="_blank">Bluesky</a><br><br>Onafhankelijk. Niet verbonden aan OpenAI. ChatGPT is een merk van OpenAI.<br>© {datetime.now().year} {E(SITE['domain'])}</div>
</div>
</footer>
</div>
</body>
</html>"""


def card(a: dict, big=False) -> str:
    return (f'<a class="card" href="{a["path"]}"><img src="{a["og"]}" alt="" loading="lazy" width="1200" height="630">'
            f'<div class="b"><span class="kicker">{E(CATEGORIES[a["category"]][0])}</span><h3>{E(a["title"])}</h3>'
            f'<p>{E(a["meta"])}</p><div class="meta" style="margin-top:8px">{nl_date(a["published"])}</div></div></a>')


def sponsor() -> str:
    s = SITE["sponsor"]
    return (f'<aside class="sponsor"><strong>{E(s["label"])}</strong> — {E(s["text"])} '
            f'<a href="{s["url"]}" rel="sponsored noopener" target="_blank">Bekijk de training →</a><small>Advertentie van de uitgever van deze site.</small></aside>')


KIND_LABEL = {"column": "Column", "practice": "Uit de praktijk", "review": "Review"}


def author_box() -> str:
    return ('<aside class="author"><div class="av">M</div><div><strong>Maxim</strong> · oprichter van Adsvantage, performance-marketeer<br>'
            '<span>Bouwt zijn eigen AI-agents, beheert Google Ads- en Shopify-accounts en test alles eerst in de praktijk. '
            '<a href="/maxim/">Meer over Maxim</a></span></div></aside>')


def ai_label(a: dict) -> str:
    """Kleine transparantieregel helemaal onderaan het artikel (EU AI Act art. 50)."""
    if a.get("kind") in KIND_LABEL:
        return '<p class="ai-note">Tekst en beeld gemaakt met AI in de stem van Maxim. <a href="/maxim/">Hoe dat werkt</a>.</p>'
    if a.get("take"):
        return '<p class="ai-note">Tekst en beeld gemaakt met AI op basis van de genoemde bronnen, de take in de stem van Maxim. <a href="/over/">Hoe dat werkt</a>.</p>'
    return '<p class="ai-note">Tekst en beeld gemaakt met AI op basis van de genoemde bronnen. <a href="/over/">Hoe dat werkt</a>.</p>'


def article_page(a: dict, all_arts: list[dict]) -> str:
    cat_name = CATEGORIES[a["category"]][0]
    secs = "".join(f'<h2>{E(s.get("heading", ""))}</h2>{prose(s.get("body", ""))}' for s in a.get("sections", []))
    take = "".join(f"<li>{inline(t)}</li>" for t in a.get("takeaways", []))
    nl_head = "Wat moet je hiermee?" if a.get("kind") in KIND_LABEL else "Wat betekent dit voor Nederland?"
    nl = f'<div class="nl"><h3>{nl_head}</h3>{prose(a["nl_angle"])}</div>' if a.get("nl_angle") else ""
    take_box = (f'<div class="take"><div class="av">M</div><div><strong>Maxims take</strong><p>{inline(a["take"])}</p>'
            f'</div></div>') if a.get("take") else ""
    is_persona = a.get("kind") in KIND_LABEL
    faq = "".join(f'<details><summary>{E(f["q"])}</summary><p>{inline(f["a"])}</p></details>' for f in a.get("faq", []) if f.get("q"))
    srcs = "".join(f'<li>{E(s["name"])}: <a href="{E(s["url"])}" rel="nofollow noopener" target="_blank">{E(s["title"])}</a></li>' for s in a.get("sources", []))
    tags = "".join(f'<a href="/{a["category"]}/">{E(t)}</a>' for t in a.get("tags", [])[:6])
    related = [x for x in all_arts if x["category"] == a["category"] and x["slug"] != a["slug"]][:4]
    more = "".join(f'<a href="{x["path"]}">{E(x["title"])}</a>' for x in related)
    rt = max(1, round(words(a) / 220))
    ld = [{
        "@context": "https://schema.org", "@type": "NewsArticle" if a.get("kind") != "evergreen" else "Article",
        "headline": a["title"], "description": a["meta"], "datePublished": a["published"] + ":00+02:00",
        "dateModified": a["published"] + ":00+02:00", "inLanguage": "nl",
        "image": [SITE["url"] + a["og"]], "mainEntityOfPage": SITE["url"] + a["path"],
        "author": ({"@type": "Person", "name": "Maxim", "url": SITE["url"] + "/maxim/"} if a.get("kind") in KIND_LABEL
                   else {"@type": "Organization", "name": SITE["name"] + " (AI-redactie)", "url": SITE["url"] + "/over/"}),
        "publisher": {"@type": "Organization", "name": SITE["name"], "logo": {"@type": "ImageObject", "url": SITE["url"] + "/img/logo.png"}},
        "isBasedOn": [s["url"] for s in a.get("sources", [])][:5],
        "keywords": ", ".join(a.get("tags", [])),
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Voorpagina", "item": SITE["url"] + "/"},
            {"@type": "ListItem", "position": 2, "name": cat_name, "item": SITE["url"] + f"/{a['category']}/"},
            {"@type": "ListItem", "position": 3, "name": a["title"]}]}]
    if a.get("faq"):
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in a["faq"] if f.get("q")]})
    body = f"""<article class="post">
<span class="kicker"><a href="/{a['category']}/" style="text-decoration:none">{E(KIND_LABEL.get(a.get('kind'), cat_name))}</a></span>
<h1>{E(a['title'])}</h1>
<div class="meta">{'Door Maxim · ' if is_persona else ''}{nl_date(a['published'])} · {rt} min lezen</div>
<img class="og" src="{a['og']}" alt="" width="1200" height="630">
<p class="intro">{inline(a.get('intro', ''))}</p>
<div class="takeaways"><h3>In het kort</h3><ul>{take}</ul></div>
{secs}
{nl}
{take_box}
{author_box() if is_persona else ''}
{f'<section class="faq"><h2>Veelgestelde vragen</h2>{faq}</section>' if faq else ''}
{sponsor()}
<div class="tags">{tags}</div>
{f'<div class="sources"><strong>Bronnen</strong><ul>{srcs}</ul></div>' if srcs else ''}
{f'<section class="block"><h2>Meer in {E(cat_name)}</h2><div class="more">{more}</div></section>' if more else ''}
{ai_label(a)}
</article>"""
    return page(a.get("seo_title") or a["title"], a["meta"], a["path"], body, a["og"], ld, kind="article", nav_on=a["category"])


def home(arts: list[dict], memes: list[dict], prompts: list[dict]) -> str:
    news = [a for a in arts if a.get("kind") != "evergreen"] or arts
    lead = news[0] if news else None
    side = news[1:4]
    rest = [a for a in arts if not lead or a["slug"] != lead["slug"]][:12]
    body = '<h1 class="home-h1">AI-nieuws en ChatGPT-uitleg in het Nederlands</h1>'
    if lead:
        body += f"""<section class="hero">
<a class="lead" href="{lead['path']}"><span class="blob" style="width:420px;height:420px;background:var(--violet);right:-120px;top:-160px"></span><span class="blob" style="width:300px;height:300px;background:var(--accent);left:-90px;bottom:-140px"></span>
<span class="kicker">{E(CATEGORIES[lead['category']][0])} · {nl_date(lead['published'])}</span><h2>{E(lead['title'])}</h2><p>{E(lead['meta'])}</p></a>
<div class="side">{"".join(f'<a class="item" href="{s["path"]}"><span class="kicker">{E(CATEGORIES[s["category"]][0])}</span><h3>{E(s["title"])}</h3><span>{nl_date(s["published"])}</span></a>' for s in side)}</div>
</section>"""
    day = ""
    if memes or prompts:
        m = memes[0] if memes else None
        p = prompts[0] if prompts else None
        day = '<section class="block"><div class="sec-head"><h2>Vandaag</h2></div><div class="dayrow">'
        if m:
            day += f'<a class="memebox" href="/memes/{m["date"]}/"><img src="{m["img"]}" alt="{E(m.get("alt", "AI-meme van de dag"))}" width="1080" height="1080"></a>'
        if p:
            day += prompt_box(p, link=True)
        day += "</div></section>"
    body += day
    if rest:
        body += f'<section class="block"><div class="sec-head"><h2>Laatste artikelen</h2><a href="/feed.xml">RSS</a></div><div class="grid">{"".join(card(a) for a in rest)}</div></section>'
    body += sponsor()
    for slug, (name, desc) in CATEGORIES.items():
        cat = [a for a in arts if a["category"] == slug][:4]
        if cat:
            body += f'<section class="block"><div class="sec-head"><h2>{E(name)}</h2><a href="/{slug}/">Alles in {E(name)} →</a></div><div class="grid">{"".join(card(a) for a in cat)}</div></section>'
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE["name"], "url": SITE["url"], "inLanguage": "nl",
           "description": SITE["description"]},
          {"@context": "https://schema.org", "@type": "Organization", "name": SITE["name"], "url": SITE["url"],
           "logo": SITE["url"] + "/img/logo.png", "email": SITE["email"]}]
    return page(f"AI-nieuws en ChatGPT-uitleg in het Nederlands | {SITE['name']}", "Dagelijks AI-nieuws in het Nederlands: ChatGPT, OpenAI, Gemini en Claude uitgelegd, plus gratis prompts, tools en wat AI betekent voor Nederland.", "/", body, ldjson=ld, nav_on="home")


def prompt_box(p: dict, link=False) -> str:
    title = f'<a href="{p["path"]}" style="color:inherit;text-decoration:none">{E(p["title"])}</a>' if link else E(p["title"])
    return (f'<div class="promptbox"><span class="kicker">Prompt van de dag · {nl_date(p["date"])}</span><h3>{title}</h3>'
            f'<p style="color:#c9c8c0">{E(p.get("situation", ""))}</p><pre id="p-{p["date"]}">{E(p["prompt"])}</pre>'
            f'<button class="copy" data-for="p-{p["date"]}" onclick="navigator.clipboard.writeText(document.getElementById(this.dataset.for).innerText).then(()=>{{this.textContent=\'Gekopieerd ✓\'}})">Kopieer prompt</button>'
            f'<p class="tip" style="margin-top:12px">Tip: {E(p.get("tip", ""))}</p></div>')


# rubriek → (H1, title-tag, meta description)
CAT_SEO = {
    "nieuws": ("AI-nieuws vandaag", "AI-nieuws vandaag: het laatste nieuws over AI en ChatGPT",
               "Het laatste AI-nieuws in het Nederlands: ChatGPT, OpenAI, Google Gemini, Claude en wat het betekent voor Nederland. Elke dag bijgewerkt."),
    "chatgpt": ("ChatGPT-nieuws en updates", "ChatGPT nieuws: updates, functies en abonnementen",
                "Alles over ChatGPT in het Nederlands: nieuwe functies, modellen, prijzen van Plus en Pro en wat je er in Nederland mee kunt."),
    "tools": ("AI-tools uitgelegd en vergeleken", "AI-tools vergelijken: Claude, Gemini, Copilot en meer",
              "Welke AI-tool past bij jou? Claude, Gemini, Copilot, Midjourney en andere AI-tools uitgelegd en vergeleken, in het Nederlands."),
    "uitleg": ("AI en ChatGPT uitgelegd", "ChatGPT uitleg: zo gebruik je AI, stap voor stap",
               "Heldere Nederlandse uitleg over ChatGPT en AI: hoe het werkt, hoe je betere prompts schrijft en hoe je AI slim inzet op werk en thuis."),
    "bedrijven": ("AI voor bedrijven", "AI voor bedrijven: toepassingen en nieuws voor het mkb",
                  "Hoe Nederlandse bedrijven AI inzetten: praktijkvoorbeelden, kosten, risico's en nieuws over AI op de werkvloer voor ondernemers en het mkb."),
    "beleid": ("AI-wetgeving en beleid", "AI-wetgeving: EU AI Act, privacy en toezicht",
               "Nieuws en uitleg over AI-wetgeving: de EU AI Act, privacy (AVG), toezicht door de AP en wat de regels betekenen voor Nederland."),
    "mening": ("Columns over AI, Google Ads en Shopify", "Columns over AI in marketing, Google Ads en Shopify",
               "Columns, praktijkverhalen en reviews over AI in marketing: wat werkt echt in Google Ads, Shopify en AI-tools, met cijfers uit de praktijk."),
}


def listing(title: str, desc: str, path: str, arts: list[dict], nav_on: str) -> str:
    h1, seo_title, seo_desc = CAT_SEO.get(nav_on, (title, title, desc))
    body = f'<section class="block"><h1>{E(h1)}</h1><p class="meta" style="max-width:640px">{E(desc)}</p><div class="grid" style="margin-top:22px">{"".join(card(a) for a in arts)}</div></section>'
    if not arts:
        body += "<p>Nog geen artikelen in deze rubriek — kom morgen terug.</p>"
    return page(seo_title, seo_desc, path, body, nav_on=nav_on)


def memes_page(memes: list[dict]) -> str:
    items = "".join(f'<a class="memebox" href="/memes/{m["date"]}/"><img src="{m["img"]}" alt="{E(m.get("alt", ""))}" loading="lazy" width="1080" height="1080"></a>' for m in memes)
    body = f'<section class="block"><h1>AI-memes over ChatGPT en AI</h1><p class="meta" style="max-width:640px">Elke ochtend een nieuwe. Herkenbaar voor iedereen die met ChatGPT werkt. Delen mag, met bronvermelding.</p><div class="grid" style="margin-top:22px">{items}</div></section>'
    return page("AI-memes: elke dag een nieuwe ChatGPT-meme", "Grappige AI- en ChatGPT-memes in het Nederlands, elke dag een nieuwe. Herkenbaar voor iedereen die met AI werkt. Delen mag.", "/memes/", body, nav_on="memes")


def meme_page(m: dict, memes: list[dict]) -> str:
    others = [x for x in memes if x["date"] != m["date"]][:6]
    body = (f'<article class="post"><span class="kicker">AI-meme van de dag</span><h1>{E(m["top"])} — {E(m["bottom"])}</h1>'
            f'<div class="meta">{nl_date(m["date"])}</div><div class="memebox" style="margin:18px 0"><img src="{m["img"]}" alt="{E(m.get("alt", ""))}" width="1080" height="1080"></div>'
            f'<p class="meta">Deel de link of sla de afbeelding op. {" ".join("#" + E(h.strip("#")) for h in m.get("hashtags", []))}</p>'
            + (f'<h2>English version</h2><div class="memebox" style="margin:18px 0;max-width:540px"><img src="{m["img_en"]}" alt="{E(m.get("alt_en", ""))}" width="1080" height="1080"></div>' if m.get("top_en") else "")
            + f'<div class="grid">{"".join(f"<a class=memebox href=/memes/{x['date']}/><img src={x['img']} alt=\"\" loading=lazy width=1080 height=1080></a>" for x in others)}</div></article>')
    return page(f"AI-meme: {m['top']}"[:58], (f"AI-meme van {nl_date(m['date'])}: {m['top']} {m['bottom']}. " + (m.get("alt") or ""))[:155].rsplit(" ", 1)[0], f"/memes/{m['date']}/", body, m["img"], nav_on="memes")


def prompts_page(prompts: list[dict]) -> str:
    items = "".join(f'<a href="{p["path"]}"><img src="/img/prompts/{p["date"]}.png" alt="" loading="lazy" width="1200" height="630"><div><strong>{E(p["title"])}</strong><br><span>{E(p.get("situation", ""))}</span><div class="d">{nl_date(p["date"])}</div></div></a>' for p in prompts)
    body = f'<section class="block"><h1>ChatGPT-prompts: elke dag een nieuwe</h1><p class="meta" style="max-width:640px">Elke dag één ChatGPT-prompt die je direct kunt gebruiken. Kopiëren, invullen, klaar.</p><div class="list" style="margin-top:22px">{items}</div></section>'
    return page("ChatGPT-prompts in het Nederlands (elke dag nieuw)", "Gratis Nederlandse ChatGPT-prompts om direct te kopiëren: elke dag een nieuwe prompt voor werk, studie en thuis, met uitleg en tip.", "/prompts/", body, nav_on="prompts")


def prompt_page(p: dict, prompts: list[dict]) -> str:
    others = [x for x in prompts if x["date"] != p["date"]][:6]
    body = (f'<article class="post"><span class="kicker">Prompt van de dag</span><h1>{E(p["title"])}</h1><div class="meta">{nl_date(p["date"])}</div>'
            f'{prompt_box(p)}'
            f'<section class="block"><h2>Meer prompts</h2><div class="more">{"".join(f"<a href={x['path']}>{E(x['title'])}</a>" for x in others)}</div></section></article>')
    return page(f"ChatGPT-prompt: {p['title']}", (f"ChatGPT-prompt om te kopiëren: {p['title']}. " + p.get("situation", ""))[:155].rsplit(" ", 1)[0], p["path"], body, f"/img/prompts/{p['date']}.png", nav_on="prompts")


def about() -> str:
    body = f"""<article class="post prose"><h1>Over {E(SITE['name'])}</h1>
<p class="intro">{E(SITE['name'])} is een onafhankelijke Nederlandse nieuws- en informatiesite over ChatGPT en andere AI. De site wordt volledig door AI gemaakt: van het kiezen van het nieuws tot het schrijven, de beelden en het publiceren.</p>
<h2>Hoe werkt het?</h2>
<p>Meerdere keren per dag leest onze software de nieuwsfeeds van onder meer OpenAI, Google, Anthropic-partners, The Verge, TechCrunch, Ars Technica, Tweakers, NU.nl en de Autoriteit Persoonsgegevens. Verhalen die door meerdere bronnen worden gemeld krijgen voorrang. Een taalmodel schrijft daarna een <strong>origineel Nederlands artikel</strong> op basis van uitsluitend die bronnen, met een aparte alinea over wat het nieuws voor Nederland betekent.</p>
<p>Elk artikel gaat door een automatische kwaliteitspoort: lengte, Nederlands, geen zinnen overgenomen uit bronnen, geen cijfers die niet in de bronnen staan, geen dubbele onderwerpen. Haalt een artikel de poort niet, dan verschijnt het niet. Gevoelige onderwerpen (rechtszaken, overlijden, misbruik, verkiezingen, medisch advies) publiceren we <strong>niet</strong> automatisch, omdat er geen menselijke eindredactie is.</p>
<h2>Transparantie (EU AI-verordening, artikel 50)</h2>
<p>Alle teksten en beelden op deze site zijn door AI gegenereerd en niet door een mens geredigeerd. Dat staat bij elk artikel. Onder elk nieuwsartikel staan de bronnen waarop het is gebaseerd, met link. Zie je een fout? Mail <a href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>; correcties worden bij de volgende run verwerkt.</p>
<h2>Onafhankelijk</h2>
<p>{E(SITE['domain'])} is niet verbonden aan OpenAI, Google, Anthropic, Microsoft of een andere AI-aanbieder. ChatGPT is een merk van OpenAI. Wij beschrijven, vergelijken en leggen uit; we verkopen geen AI-producten. De enige commerciële uiting is het duidelijk gemarkeerde blok over AI-training van de uitgever.</p>
<h2>Uitgever</h2>
<p>Deze site wordt uitgegeven door Adsvantage (Nederland). Contact: <a href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>.</p>
</article>"""
    return page("Over deze site", "Hoe chatgpthelp.nl werkt: een volledig door AI gemaakte nieuwssite over ChatGPT en AI, met bronnen en zonder menselijke eindredactie.", "/over/", body)


def maxim_page(arts: list[dict]) -> str:
    import json as _json
    from .config import CONTENT
    p = _json.loads((CONTENT / "persona" / "maxim.json").read_text(encoding="utf-8"))
    beliefs = "".join(f"<li>{E(b)}</li>" for b in p["beliefs"])
    tools = "".join(f"<li><strong>{E(x['tool'])}</strong>: {E(x['status'])}. {E(x['opinion'][0].upper() + x['opinion'][1:])}.</li>" for x in p["tools_used"])
    mine = [a for a in arts if a.get("kind") in KIND_LABEL][:12]
    body = f"""<article class="post prose"><span class="kicker">Columnist</span><h1>Maxim</h1>
{author_box()}
<p class="intro">{E(p['short_bio'])}</p>
<h2>Waar hij voor staat</h2><ul>{beliefs}</ul>
<h2>Tools die hij zelf gebruikt</h2><ul>{tools}</ul>
<h2>Hoe deze columns ontstaan</h2>
<p>De columns, praktijkverhalen, reviews en de korte "Maxims take" onder nieuwsartikelen worden door AI geschreven in de stem van Maxim. Het model krijgt zijn opvattingen, de tools die hij echt gebruikt en een verzameling praktijklessen uit zijn werk met Google Ads, Shopify, tracking en AI-automatisering. Cijfers in een column moeten letterlijk uit die lessen of uit het nieuws komen; een automatische poort keurt teksten met andere cijfers af. Klanten zijn altijd geanonimiseerd.</p>
<p>Maxim leest niet elke tekst vooraf. Zie je een fout, mail <a href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>.</p>
{f'<h2>Recent van Maxim</h2><div class="grid">{"".join(card(a) for a in mine)}</div>' if mine else ''}
</article>"""
    ld = [{"@context": "https://schema.org", "@type": "ProfilePage", "mainEntity": {"@type": "Person", "name": "Maxim",
           "jobTitle": "Oprichter Adsvantage", "worksFor": {"@type": "Organization", "name": "Adsvantage", "url": "https://adsvantage.nl"},
           "url": SITE["url"] + "/maxim/"}}]
    return page("Maxim: columnist over AI, Google Ads en Shopify", "Wie is Maxim, waar staat hij voor en hoe ontstaan zijn columns over AI, Google Ads en Shopify op ChatGPT Help.", "/maxim/", body, ldjson=ld, nav_on="mening")


def privacy() -> str:
    body = f"""<article class="post prose"><h1>Privacy</h1>
<p class="intro">Kort: alleen analytische cookies, geen advertentiecookies, geen profilering.</p>
<p>We gebruiken Google Analytics 4 om te zien welke artikelen gelezen worden. Daarvoor plaatst Google Analytics analytische cookies (_ga, _ga_*) die tot 14 maanden bewaard blijven. Je IP-adres wordt geanonimiseerd, Google-signalen en advertentiepersonalisatie staan uit, en we delen geen gegevens met Google voor andere doeleinden. Er worden geen advertentie- of trackingcookies van derden geplaatst. Wil je niet gemeten worden, dan kun je cookies blokkeren in je browser of de <a href="https://tools.google.com/dlpage/gaoptout" rel="noopener" target="_blank">Google Analytics opt-out</a> gebruiken.</p>
<p>Geen advertentienetwerken, geen profilering. De site wordt gehost op GitHub Pages; GitHub kan voor de werking van de dienst tijdelijk IP-adressen in serverlogs bewaren (zie het privacybeleid van GitHub). Lettertypen worden geladen via Google Fonts; daarbij ziet Google je IP-adres. Verder verwerken we geen persoonsgegevens, tenzij je ons zelf mailt.</p>
<p>De knop "Kopieer prompt" werkt volledig in je browser. Links naar externe sites (bronnen, sponsor) vallen onder het beleid van die sites.</p>
<p>Vragen: <a href="mailto:{E(SITE['email'])}">{E(SITE['email'])}</a>.</p></article>"""
    return page("Privacy", "Geen cookies, geen tracking. Zo gaat chatgpthelp.nl met je gegevens om.", "/privacy/", body)


def feed(arts: list[dict]) -> str:
    items = "".join(f"""<item><title>{E(a['title'])}</title><link>{SITE['url']}{a['path']}</link><guid>{SITE['url']}{a['path']}</guid>
<pubDate>{rfc822(a['published'])}</pubDate><description>{E(a['meta'])}</description><category>{E(CATEGORIES[a['category']][0])}</category>
<enclosure url="{SITE['url']}{a['og']}" type="image/png" length="0"/></item>""" for a in arts[:40])
    return f"""<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel><title>{E(SITE['name'])}</title><link>{SITE['url']}</link><description>{E(SITE['tagline'])}</description><language>nl</language><atom:link href="{SITE['url']}/feed.xml" rel="self" type="application/rss+xml"/>{items}</channel></rss>"""


def sitemaps(arts, memes, prompts):
    urls = [("/", 1.0, "hourly")] + [(f"/{s}/", 0.8, "daily") for s in CATEGORIES] + [("/prompts/", 0.7, "daily"), ("/memes/", 0.6, "daily"), ("/over/", 0.3, "monthly"), ("/maxim/", 0.5, "weekly"), ("/privacy/", 0.1, "yearly")]
    urls += [(a["path"], 0.7, "weekly") for a in arts] + [(p["path"], 0.5, "monthly") for p in prompts] + [(f"/memes/{m['date']}/", 0.3, "monthly") for m in memes]
    sm = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        f"<url><loc>{SITE['url']}{u}</loc><priority>{p}</priority><changefreq>{c}</changefreq></url>" for u, p, c in urls) + "</urlset>"
    cutoff = (datetime.now() - timedelta(hours=48)).isoformat()
    recent = [a for a in arts if a["published"] >= cutoff and a.get("kind") == "news"][:100]
    news = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">'
            + "".join(f"<url><loc>{SITE['url']}{a['path']}</loc><news:news><news:publication><news:name>{E(SITE['name'])}</news:name><news:language>nl</news:language></news:publication>"
                      f"<news:publication_date>{a['published']}:00+02:00</news:publication_date><news:title>{E(a['title'])}</news:title></news:news></url>" for a in recent) + "</urlset>")
    return sm, news


def write(path: str, content: str) -> None:
    p = DIST / path.lstrip("/")
    if path.endswith("/"):
        p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def build() -> int:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    arts, memes, prompts = load_articles(), load_memes(), load_prompts()
    shutil.copy(ASSETS / "style.css", DIST / "style.css")
    (DIST / "img").mkdir()
    images.logo_png(DIST / "img" / "logo.png")
    images.logo_png(DIST / "img" / "favicon.png", 64)
    images.og_card(SITE["tagline"], SITE["name"], DIST / "img" / "og-default.png", "default")
    for a in arts:
        label = {"column": "Column · Maxim", "practice": "Uit de praktijk · Maxim", "review": "Review · Maxim"}.get(a.get("kind"), CATEGORIES[a["category"]][0])
        images.og_card(a["title"], label, DIST / a["og"].lstrip("/"), a["slug"])
    for m in memes:
        images.meme_card(m["top"], m["bottom"], DIST / m["img"].lstrip("/"), m["date"])
        if m.get("top_en"):
            images.meme_card(m["top_en"], m["bottom_en"], DIST / m["img_en"].lstrip("/"), m["date"] + "en", "AI MEME OF THE DAY")
    for p in prompts:
        images.prompt_card(p["title"], p["prompt"], DIST / "img" / "prompts" / f"{p['date']}.png")
    n = 0
    write("/", home(arts, memes, prompts)); n += 1
    for a in arts:
        write(a["path"], article_page(a, arts)); n += 1
    for slug, (name, desc) in CATEGORIES.items():
        write(f"/{slug}/", listing(name, desc, f"/{slug}/", [a for a in arts if a["category"] == slug], slug)); n += 1
    write("/memes/", memes_page(memes)); n += 1
    for m in memes:
        write(f"/memes/{m['date']}/", meme_page(m, memes)); n += 1
    write("/prompts/", prompts_page(prompts)); n += 1
    for p in prompts:
        write(p["path"], prompt_page(p, prompts)); n += 1
    write("/over/", about()); write("/privacy/", privacy()); write("/maxim/", maxim_page(arts)); n += 3
    write("/404.html", page("Pagina niet gevonden", "Deze pagina bestaat niet.", "/404.html", '<article class="post"><h1>Pagina niet gevonden</h1><p>Ga naar de <a href="/">voorpagina</a>.</p></article>'))
    write("/feed.xml", feed(arts))
    sm, ns = sitemaps(arts, memes, prompts)
    write("/sitemap.xml", sm); write("/news-sitemap.xml", ns)
    write("/robots.txt", f"User-agent: *\nAllow: /\nSitemap: {SITE['url']}/sitemap.xml\nSitemap: {SITE['url']}/news-sitemap.xml\n")
    write("/CNAME", SITE["domain"] + "\n")
    (DIST / ".nojekyll").write_text("")
    return n
