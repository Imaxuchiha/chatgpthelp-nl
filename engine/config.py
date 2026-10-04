"""Centrale configuratie voor chatgpthelp.nl — merk, bronnen, categorieën, poorten.

Alles wat de redactie-AI mag en niet mag staat hier, niet verspreid over de code.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
ARTICLES = CONTENT / "articles"
MEMES = CONTENT / "memes"
PROMPTS = CONTENT / "prompts"
LEDGER = CONTENT / "ledger.json"
SEEDS = CONTENT / "evergreen_seeds.json"
ASSETS = ROOT / "assets"
FONTS = ASSETS / "fonts"
DIST = ROOT / "dist"

SITE = {
    "name": "ChatGPT Help",
    "domain": "chatgpthelp.nl",
    "url": "https://chatgpthelp.nl",
    "tagline": "Dagelijks AI-nieuws, uitleg en prompts — in gewoon Nederlands.",
    "description": (
        "ChatGPT Help is een Nederlandse nieuws- en informatiesite van Adsvantage over ChatGPT, "
        "Claude, Gemini en andere AI. Elke dag het belangrijkste AI-nieuws, praktische uitleg, "
        "een prompt van de dag en een meme van de dag. De site wordt volledig door AI gemaakt; "
        "bronnen staan altijd onder elk artikel."
    ),
    "email": "redactie@chatgpthelp.nl",
    "founded": "2026",
    "lang": "nl",
    "twitter": "",
    "bluesky": "https://bsky.app/profile/chatgpthelp.nl",
    # Meting: GA4 met analytics-cookies zonder banner (bewuste keuze Maxim 15-09); ads-opslag/signalen uit.
    "ga4": "G-68TBRXKHX0",
    # IndexNow (Bing, Yandex, Seznam; Bing voedt ook ChatGPT- en Copilot-zoeken). Sleutel is publiek by design:
    # hij staat als /<sleutel>.txt op de site. Google doet niet mee; die leest de sitemap.
    "indexnow_key": "d51e395866d5710100206fceebc473f9",
    # Enige commerciële link (kostenbewust, geen ads): AI-training van Maxim.
    "sponsor": {
        "label": "AI-training voor je team",
        "text": "Wil je dat je collega's ChatGPT écht goed gebruiken? Bekijk AI-training op locatie.",
        "url": "https://aitrainingoplocatie.nl/?utm_source=chatgpthelp&utm_medium=site&utm_campaign=sponsorblok",
    },
}

# Categorieën: slug -> (naam, omschrijving)
CATEGORIES = {
    "nieuws": ("Nieuws", "Het laatste AI-nieuws uit Nederland en de wereld."),
    "chatgpt": ("ChatGPT", "Alles over ChatGPT en OpenAI: updates, functies, abonnementen."),
    "tools": ("AI-tools", "Claude, Gemini, Copilot, Midjourney en andere AI-tools vergeleken en uitgelegd."),
    "uitleg": ("Uitleg", "Stap-voor-stap uitleg: zo gebruik je AI in werk en privé."),
    "bedrijven": ("Bedrijven", "AI op de werkvloer: wat betekent het voor Nederlandse bedrijven?"),
    "beleid": ("Beleid & wet", "EU AI Act, privacy, toezicht en politiek rond AI."),
    "mening": ("Maxims mening", "Columns, praktijkverhalen en eerlijke reviews van Maxim, ondernemer en performance-marketeer."),
}

# Onderwerp-hubs: de schrijf-AI kiest bijna altijd "nieuws" als rubriek (127 van 135 op 29-09), waardoor
# /chatgpt/ en /tools/ leeg bleven. Deze rubrieken tonen daarom ook elk artikel dat over het onderwerp
# gaat (titel, meta, tags, zoekwoord), ongeacht zijn eigen rubriek. Vullen zichzelf bij elke build.
HUB_MATCH = {
    "chatgpt": r"\b(chat ?gpt|openai|gpt[- ]?\d[\w.]*|sora|sam altman)\b",
    "tools": r"\b(claude|anthropic|gemini|copilot|midjourney|perplexity|mistral|deepseek|llama|grok|notebooklm|meta ai|muse ai)\b",
}

# RSS-bronnen: naam, url, taal, gewicht (hoger = eerder gekozen), betrouwbaar (primaire bron?)
SOURCES = [
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "lang": "en", "weight": 1.6, "primary": True, "ai_feed": True},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "lang": "en", "weight": 1.2, "primary": True, "ai_feed": True},
    {"name": "Google (The Keyword)", "url": "https://blog.google/technology/ai/rss/", "lang": "en", "weight": 1.2, "primary": True},
    {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml", "lang": "en", "weight": 0.6, "primary": True},
    {"name": "The Verge", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "lang": "en", "weight": 1.3, "primary": False},
    {"name": "TechCrunch", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "lang": "en", "weight": 1.3, "primary": False},
    {"name": "Ars Technica", "url": "https://arstechnica.com/ai/feed/", "lang": "en", "weight": 1.2, "primary": False},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "lang": "en", "weight": 1.0, "primary": False},
    {"name": "Tweakers", "url": "https://feeds.feedburner.com/tweakers/mixed", "lang": "nl", "weight": 1.5, "primary": False},
    {"name": "NU.nl Tech", "url": "https://www.nu.nl/rss/Tech", "lang": "nl", "weight": 1.5, "primary": False},
    {"name": "Bright", "url": "https://www.bright.nl/rss", "lang": "nl", "weight": 1.2, "primary": False},
    {"name": "Autoriteit Persoonsgegevens", "url": "https://www.autoriteitpersoonsgegevens.nl/rss", "lang": "nl", "weight": 1.1, "primary": True},
]

# Relevantie. Bronnen met "ai_feed": True (de AI-labs zelf) gaan altijd door; de AI-rubrieken van Verge, Ars e.d. niet,
# want die bevatten ook koelkast- en datacenternieuws. Voor alle andere moet de TITEL een AI-term bevatten, of de
# samenvatting er minstens twee. Hele woorden, geen substrings: de oude lijst ("agent", "ai ", "nvidia") liet op
# 27 en 29-09 twee Kia EV2-autotests en een Odido-hack (FBI-agenten) door als AI-nieuws.
AI_PATTERN = (
    r"\b(chat ?gpt|openai|gpt-?\d[\w.]*|sora|dall-?e|claude|anthropic|gemini|deepmind|copilot|llms?|"
    r"large language models?|taalmodel\w*|kunstmatige intelligentie|artificial intelligence|a\.?i\.?|"
    r"ai-\w+|\w+-ai|generatiev\w*|generative|midjourney|stable diffusion|perplexity|mistral|deepseek|"
    r"meta ai|llama|grok|xai|machine learning|neura\w+ netw\w*|chatbots?|ai act|ai-wet|"
    r"ai[- ]agents?|ai[- ]agenten|agentic|coding agents?|codex|deepfakes?|algoritm\w*|superintelligen\w*|agi)\b"
)
AI_MIN_SUMMARY_HITS = 2

# Gevoelige onderwerpen: zonder menselijke eindredactie NIET automatisch publiceren.
HIGH_RISK_TERMS = [
    "zelfmoord", "suicide", "suïcide", "overleden", "dood", "death", "died", "killed",
    "rechtszaak", "lawsuit", "aangeklaagd", "sued", "arrest", "arrested", "veroordeeld",
    "misbruik", "abuse", "seksueel", "sexual", "csam", "kinderporno", "terrorist", "terreur",
    "verkrachting", "rape", "moord", "murder", "wapen", "weapon", "oorlog", "war ",
    "verkiezing", "election", "trump", "poetin", "putin", "israël", "gaza", "hamas",
    "medisch advies", "diagnose", "kanker", "cancer", "zwanger",
    "fraude", "fraud", "oplichting", "scam",
]

# Verboden frasen in de output (hol, hype, AI-clichés).
FORBIDDEN_PHRASES = [
    "in de snel veranderende wereld", "in het huidige digitale tijdperk", "het is belangrijk om op te merken",
    "revolutionair", "baanbrekend", "game-changer", "gamechanger", "delve", "duik in",
    "als ai-taalmodel", "als een ai-taalmodel", "ik kan niet", "laten we eens kijken", "in conclusie",
    "concluderend", "kortom,", "ontketen", "naadloos", "in dit artikel",
]

# Engelse lekkage: als te veel van deze woorden in de NL-tekst staan, faalt de poort.
ENGLISH_MARKERS = [" the ", " and ", " with ", " that ", " this ", " which ", " for ", " from ", " are ", " will "]

LIMITS = {
    "max_item_age_hours": 72,
    "articles_per_run": int(os.getenv("ARTICLES_PER_RUN", "3")),
    "min_words": 380,
    "max_words": 900,
    "title_max": 75,
    "meta_min": 60,
    "meta_max": 158,
    "dedupe_jaccard": 0.42,
    "max_copied_run": 12,  # max aaneengesloten woorden gelijk aan een bron
}

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")

# De stijlpoort (gate.stijl_check): "meten" legt per artikel vast welke stijlregels het breekt (content/stijl_log.json)
# en houdt niets tegen; "blokkeren" maakt elke rode stijlregel een poortfout. Begonnen op "meten" (04-10-2026): van
# de 192 bestaande artikelen haalden er 2 de regels, dus eerst zien of de schrijver ze met de regels in de opdracht haalt.
STIJLPOORT = os.getenv("STIJLPOORT", "meten")
