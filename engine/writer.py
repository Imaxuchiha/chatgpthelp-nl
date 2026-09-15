"""Alle schrijfopdrachten aan DeepSeek. De LLM levert alléén proza als JSON; structuur,
bronnen, datums en HTML komen deterministisch uit de code.

Redactieregels (staan in de systeemprompt): origineel Nederlands, nooit vertalen of kopiëren,
alleen feiten uit de aangeleverde bronnen, geen verzonnen cijfers, nuchter, concreet, jij-vorm.
"""
from __future__ import annotations

import json

from .config import CATEGORIES, SITE
from .llm import ask_json

CATS = ", ".join(f"{k} ({v[0]})" for k, v in CATEGORIES.items())

STYLE = f"""Je bent de redactie van {SITE['name']} ({SITE['domain']}), een Nederlandse nieuws- en
informatiesite over ChatGPT en AI voor gewone mensen en professionals in Nederland.

Schrijfregels (hard):
- Schrijf ORIGINEEL Nederlands. Nooit vertalen, nooit zinnen overnemen. Max 8 woorden achter elkaar
  gelijk aan een bron.
- Gebruik ALLEEN feiten die in de aangeleverde bronnen staan. Verzin geen cijfers, citaten, namen of
  data. Weet je iets niet: zeg dat het nog niet bekend is.
- Toon: nuchter, helder, concreet, licht informeel, jij-vorm. Korte zinnen. Geen hype, geen clichés
  ("revolutionair", "baanbrekend", "in de snel veranderende wereld", "kortom", "in dit artikel").
- Vertaal het nieuws naar Nederland: wat betekent dit voor iemand in Nederland (prijs in euro's,
  beschikbaarheid in NL/EU, wetgeving, werk).
- Amerikaanse termen uitleggen. Merknamen correct: ChatGPT, OpenAI, Claude, Gemini, Copilot.
- Nederlandse spelling (Groene Boekje), geen Engelse woorden waar een Nederlands woord bestaat.
- Titels: concreet en informatief, geen clickbait, geen vraag als het antwoord één woord is, max 70 tekens.
Categorieën: {CATS}.
Antwoord ALTIJD met één JSON-object, zonder tekst eromheen."""

ARTICLE_SCHEMA = """{
 "title": "string, max 70 tekens",
 "meta": "string, 70-155 tekens, zin die de kern samenvat",
 "category": "een van de categorie-slugs",
 "tags": ["3-6 korte tags in kleine letters"],
 "intro": "1 alinea van 2-4 zinnen: wat is er gebeurd en waarom telt het",
 "takeaways": ["3-4 kernpunten, elk 1 zin, met concrete feiten"],
 "sections": [ {"heading": "kop zonder nummering", "body": "2-4 alinea's, gescheiden door \\n\\n"} ],
 "nl_angle": "1 alinea: wat betekent dit concreet voor mensen of bedrijven in Nederland",
 "faq": [ {"q": "vraag die een lezer zou googelen", "a": "antwoord van 1-3 zinnen"} ]
}"""


def _sources_block(items: list[dict]) -> str:
    out = []
    for i, it in enumerate(items, 1):
        out.append(f"[Bron {i}] {it['source']} ({it['lang']}) — {it['published'][:10]}\nTitel: {it['title']}\nSamenvatting: {it['summary']}\nURL: {it['url']}")
    return "\n\n".join(out)


def write_news(story: dict, today: str) -> dict:
    items = story["items"][:5]
    user = f"""Datum vandaag: {today}.
Schrijf een nieuwsartikel van 400-700 woorden op basis van uitsluitend deze bronnen:

{_sources_block(items)}

Eisen: 3-5 secties, 3 FAQ-vragen, en de sectie "nl_angle" is verplicht. Verwijs in de tekst naar
bronnen als "volgens OpenAI" of "meldt The Verge" (geen URL's in de tekst).
Schema:
{ARTICLE_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.55, max_tokens=3200)


def write_evergreen(seed: dict, today: str) -> dict:
    user = f"""Datum vandaag: {today}.
Schrijf een praktisch uitleg-artikel (600-1000 woorden) over: "{seed['topic']}".
Doelgroep: {seed.get('audience', 'Nederlandse beginners en gevorderden')}.
Zoekintentie: {seed.get('intent', 'hoe doe ik dit / wat is dit')}.
Je hebt geen bronnen; gebruik alleen algemeen bekende, stabiele kennis over ChatGPT en AI. Noem GEEN
prijzen, versienummers of datums die kunnen veranderen, tenzij je ze markeert als "op het moment van
schrijven". Geef concrete stappen en minimaal één voorbeeldprompt (in een sectie, letterlijk tussen
aanhalingstekens).
Eisen: 4-6 secties, 3-4 FAQ-vragen, categorie meestal "uitleg" of "tools". "nl_angle" mag kort.
Schema:
{ARTICLE_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.6, max_tokens=3800)


def write_week(articles: list[dict], week_label: str, today: str) -> dict:
    lijst = "\n".join(f"- {a['title']} ({a['date']}): {a['meta']}" for a in articles)
    user = f"""Datum vandaag: {today}. Schrijf het weekoverzicht "{week_label}" (400-650 woorden) op basis
van uitsluitend deze artikelen die deze week op de site verschenen:

{lijst}

Structuur: intro met de rode draad van de week, 3-5 secties (elk over 1-2 nieuwsitems, met de
belangrijkste feiten), takeaways = de 4 dingen die je moet onthouden, 2 FAQ. Categorie "nieuws".
Schema:
{ARTICLE_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.5, max_tokens=3000)


def write_meme(recent_titles: list[str], today: str, previous: list[str]) -> dict:
    prev = "\n".join(f"- {p}" for p in previous[-30:]) or "- (nog geen)"
    user = f"""Datum vandaag: {today}. Bedenk de "AI-meme van de dag": één herkenbare, grappige
observatie over leven en werken met ChatGPT/AI. Lever hem in TWEE talen: een Nederlandse versie en een
Engelse versie die in het Engels óók echt grappig is (zelfde idee, geen letterlijke vertaling; Engelse
versie mag een andere woordgrap gebruiken). Format per taal = tweedelige tekstmeme: situatie (max 70
tekens) en punchline (max 80 tekens). Droog, herkenbaar, nooit kwetsend, geen echte personen, geen
merk-bashen, geen politiek. Mag inhaken op het nieuws van vandaag:
{chr(10).join('- ' + t for t in recent_titles[:6])}

Deze memes bestaan al (maak iets anders):
{prev}

Antwoord: {{"top": "NL situatie", "bottom": "NL punchline", "alt": "NL beschrijving in 1 zin", "hashtags": ["3 NL tags"],
"top_en": "EN situation", "bottom_en": "EN punchline", "alt_en": "EN one-sentence description", "hashtags_en": ["3 EN tags"]}}"""
    return ask_json(STYLE, user, temperature=0.95, max_tokens=700)


def write_prompt_of_day(today: str, previous: list[str]) -> dict:
    prev = "\n".join(f"- {p}" for p in previous[-60:]) or "- (nog geen)"
    user = f"""Datum vandaag: {today}. Schrijf de "Prompt van de dag": één direct bruikbare ChatGPT-prompt
in het Nederlands voor een concrete situatie in werk, studie of thuis. Kies iets nuttigs dat mensen
niet zelf zouden bedenken (rol + context + gewenste output + voorbeeld).

Eerdere prompts (kies een ANDER onderwerp):
{prev}

Antwoord: {{"title": "korte naam van de prompt (max 55 tekens)", "situation": "1-2 zinnen: wanneer gebruik je dit",
"prompt": "de volledige prompt, 60-160 woorden, met [PLACEHOLDERS] in blokhaken waar de lezer iets invult",
"tip": "1 zin: hoe maak je hem nog beter", "tags": ["2-4 tags"]}}"""
    return ask_json(STYLE, user, temperature=0.85, max_tokens=700)


def social_caption(art: dict) -> str:
    """Korte tekst voor Bluesky (max 280 tekens) — geen LLM nodig."""
    t = art["title"]
    m = art["meta"]
    text = f"{t}\n\n{m}"
    return text[:250]


# ----------------------------------------------------------------------------- Maxim ----
# Maxim (15-09-2026): columns in zijn stem, met geanonimiseerde praktijkcijfers uit zijn werk.
# Sterker model voor persona-content (volgt de anekdote-regel veel beter dan flash); ~3 stukken/week.
PERSONA_MODEL = "deepseek-v4-pro"
COLUMN_SCHEMA = """{
 "title": "pakkende maar eerlijke kop, max 70 tekens, mag een stelling zijn",
 "meta": "70-155 tekens: zijn standpunt in één zin",
 "category": "mening",
 "tags": ["3-6 tags"],
 "intro": "openingsalinea: meteen zijn standpunt, geen aanloop",
 "takeaways": ["3 kernpunten van zijn betoog, elk 1 zin"],
 "sections": [ {"heading": "tussenkop", "body": "2-4 alinea's, gescheiden door \\n\\n"} ],
 "nl_angle": "wat moet een Nederlandse ondernemer of lezer hier nu mee: 1 alinea, concreet",
 "faq": [ {"q": "vraag", "a": "antwoord in 1-3 zinnen"} ],
 "lessons_used": ["id's van de praktijklessen die je gebruikte, of lege lijst"]
}"""

COLUMN_RULES = """Schrijfregels voor deze column (hard):
- Ik-vorm als het personage, in zijn stem. Duidelijk standpunt; geen 'enerzijds-anderzijds'.
- Onderbouw met zijn praktijk: 1 tot 3 van de aangeleverde praktijklessen, cijfers LETTERLIJK.
  Verzin geen andere cijfers, klanten, tests of ervaringen. Past geen les? Dan zonder cijfers.
- Klanten altijd anoniem ('een klant', 'een webshop'). Nooit naam, stad, merk of niche die herkenbaar is.
- Eigen ervaring alleen met tools uit zijn lijst. Andere tools: alleen op basis van het nieuws.
- Nooit interne of niet-publieke kennis over Google of andere bedrijven. Een mening over Gemini of andere
  Google-AI mag, maar alleen op basis van publieke informatie en het nieuws, zonder eigen gebruik te claimen.
- GEEN VERZONNEN ANEKDOTES. Elk concreet voorval (een klant, een test, een tijdsduur, 'een keer liet ik...')
  moet letterlijk uit een praktijkles of het nieuws komen. Verder alleen algemene mening en uitleg.
- Menselijk: geen gedachtestreepjes, NOOIT de constructie 'Dat is geen X, dat is Y' of 'geen X, maar Y',
  niet eindigen met een vraag, alinea's niet allemaal even lang, mag toegeven wat niet werkte.
- Geen financieel, juridisch of medisch advies."""


def write_column(persona_brief: str, lessons_text: str, news_block: str, today: str) -> dict:
    user = f"""Datum vandaag: {today}.
{persona_brief}

Schrijf een opiniecolumn (550-850 woorden) van dit personage over het AI-nieuws hieronder. Kies het
onderwerp waar hij het meest over te zeggen heeft en koppel het aan zijn eigen praktijk.

NIEUWS (feiten alleen hieruit):
{news_block}

PRAKTIJKLESSEN (cijfers alleen hieruit):
{lessons_text}

{COLUMN_RULES}
Eisen: 3-5 secties, 2 FAQ. Schema:
{COLUMN_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.75, max_tokens=3600, model=PERSONA_MODEL)


def write_practice(persona_brief: str, lesson: dict, extra_lessons: str, today: str) -> dict:
    user = f"""Datum vandaag: {today}.
{persona_brief}

Schrijf een column "Uit de praktijk" (550-850 woorden) van dit personage rond deze ene les uit zijn werk:
wat er gebeurde, waarom het fout of goed ging, wat AI of automatisering ermee te maken had, en wat de
lezer er morgen mee moet doen (stappen of checklist).

HOOFDLES (cijfers letterlijk):
[Les {lesson['id']}] {lesson['text']}

AANVULLENDE LESSEN (hooguit 1 gebruiken):
{extra_lessons}

{COLUMN_RULES}
Eisen: 3-5 secties, 3 FAQ. Schema:
{COLUMN_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.7, max_tokens=3600, model=PERSONA_MODEL)


def write_review(persona_brief: str, tool: dict, lessons_text: str, today: str) -> dict:
    user = f"""Datum vandaag: {today}.
{persona_brief}

Schrijf een eerlijke review (600-900 woorden) van dit personage over een tool die hij zelf gebruikt:
TOOL: {tool['tool']} ({tool['status']}); waarvoor: {tool['use']}; zijn oordeel: {tool['opinion']}

Opbouw: waarvoor hij het gebruikt, wat goed is, wat tegenvalt, voor wie wel en niet, eindoordeel in woorden.
Alleen op basis van bovenstaande gegevens en de praktijklessen; geen prijzen, versienummers of functies
waarvan je niet zeker bent. Geen sterren of cijferscore verzinnen.

PRAKTIJKLESSEN (cijfers alleen hieruit):
{lessons_text}

{COLUMN_RULES}
Eisen: 4-5 secties, 3 FAQ. Categorie "mening". Schema:
{COLUMN_SCHEMA}"""
    return ask_json(STYLE, user, temperature=0.65, max_tokens=3800, model=PERSONA_MODEL)


def write_take(persona_brief: str, art: dict, lessons_text: str, focus: str = "") -> str:
    focus_line = (f"INVALSHOEK VOOR DEZE TAKE (gebruik deze opvatting, niet kosten tenzij dit over kosten gaat): {focus}\n"
                  if focus else "")
    user = f"""{persona_brief}

{focus_line}Begin NIET met 'Ik snap' of 'Ik geloof best'. Varieer je opening.

Schrijf "Maxims take" onder dit nieuwsartikel: 2 tot 3 zinnen, ik-vorm, zijn eerlijke mening, nuchter en
een beetje brutaal. Reageer op DIT nieuws. Gebruik alleen een praktijkles als die over precies hetzelfde
onderwerp gaat; bij twijfel géén praktijkvoorbeeld en géén cijfers. Liever een scherpe mening zonder
voorbeeld dan een voorbeeld dat er met de haren bij gesleept is. Geen vraag als slotzin, geen gedachtestreepjes.

ARTIKEL: {art['title']} ({art['meta']})
{art.get('intro', '')}

PRAKTIJKLESSEN:
{lessons_text}

{COLUMN_RULES}
Antwoord: {{"take": "..."}}"""
    return (ask_json(STYLE, user, temperature=0.8, max_tokens=300).get("take") or "").strip()


VERIFY_SYSTEM = """Je bent een strenge feitencontroleur. Je krijgt een tekst die in de ik-vorm namens een
personage is geschreven, plus ALLE toegestane feiten over dat personage (profiel, tools, praktijklessen) en
het nieuws. Zoek elke bewering waarin het personage iets concreets over ZICHZELF of zijn werk claimt
(een voorval, een klant, een test, een tijdsduur, een aantal, een eerdere werkwijze, iets wat hij 'een keer'
deed) dat NIET letterlijk of vrijwel letterlijk uit de toegestane feiten volgt. Algemene meningen, adviezen
en uitleg zijn toegestaan en tel je NIET mee. Antwoord ALTIJD met JSON."""


def verify_persona(text: str, allowed: str) -> list[str]:
    user = f"""TOEGESTANE FEITEN:
{allowed}

TE CONTROLEREN TEKST:
{text}

Antwoord: {{"onderbouwd": true/false, "verzonnen": ["letterlijke zin uit de tekst die een niet-onderbouwde persoonlijke claim bevat", "..."]}}"""
    r = ask_json(VERIFY_SYSTEM, user, temperature=0.1, max_tokens=900, model=PERSONA_MODEL)
    return [x for x in (r.get("verzonnen") or []) if isinstance(x, str) and x.strip()]


def revise_persona(art: dict, problems: list[str]) -> dict:
    user = f"""Hieronder een column als JSON. Deze zinnen bevatten verzonnen persoonlijke claims die niet
kloppen en MOETEN eruit of worden herschreven tot een algemene mening zonder persoonlijk voorval:
{chr(10).join('- ' + p for p in problems)}

Pas ALLEEN die zinnen aan; laat de rest, de cijfers uit praktijklessen en de structuur staan. Houd dezelfde
JSON-velden. Geen gedachtestreepjes, geen 'Dat is geen X, dat is Y'.

JSON:
{json.dumps(art, ensure_ascii=False)}"""
    return ask_json(STYLE, user, temperature=0.3, max_tokens=4200, model=PERSONA_MODEL)
