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
