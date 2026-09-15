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
        "ChatGPT Help is een onafhankelijke Nederlandse nieuws- en informatiesite over ChatGPT, "
        "Claude, Gemini en andere AI. Elke dag het belangrijkste AI-nieuws, praktische uitleg, "
        "een prompt van de dag en een meme van de dag. De site wordt volledig door AI gemaakt; "
        "bronnen staan altijd onder elk artikel."
    ),
    "email": "redactie@chatgpthelp.nl",
    "founded": "2026",
    "lang": "nl",
    "twitter": "",
    "bluesky": "https://bsky.app/profile/chatgpthelp.nl",
    # Meting: GA4 (eigen adsvantage-account) achter Cookiekompas-consent (Maxims eigen CMP).
    "ga4": "G-68TBRXKHX0",
    "cookiekompas_id": os.getenv("COOKIEKOMPAS_ID", ""),
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
}

# RSS-bronnen: naam, url, taal, gewicht (hoger = eerder gekozen), betrouwbaar (primaire bron?)
SOURCES = [
    {"name": "OpenAI", "url": "https://openai.com/news/rss.xml", "lang": "en", "weight": 1.6, "primary": True},
    {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml", "lang": "en", "weight": 1.2, "primary": True},
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

# Relevantie: een item moet minstens één van deze termen bevatten (titel+samenvatting).
AI_TERMS = [
    "chatgpt", "openai", "gpt-", "gpt5", "gpt6", "sora", "dall-e", "dall·e", "claude", "anthropic",
    "gemini", "deepmind", "copilot", "llm", "large language", "taalmodel", "kunstmatige intelligentie",
    "artificial intelligence", " ai ", "ai-", "ai ", "generatieve", "generative", "midjourney",
    "stable diffusion", "perplexity", "mistral", "deepseek", "meta ai", "llama", "grok", "xai",
    "nvidia", "machine learning", "neural", "agent", "chatbot", "ai act", "ai-wet", "algoritme",
]
# Termen die wél 'ai' bevatten maar niets met AI te maken hebben — uitsluiten.
NOISE_TERMS = ["aida", "airbnb", "air fryer", "airfryer", "airpods", "aircraft", "airline", "mail", "rail", "hair"]

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
    "als ai-taalmodel", "als een ai", "ik kan niet", "laten we eens kijken", "in conclusie",
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
