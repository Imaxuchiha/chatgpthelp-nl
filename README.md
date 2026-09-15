# chatgpthelp.nl — autonome AI-nieuwsredactie

Nederlandse nieuws- en informatiesite over ChatGPT en AI die volledig door software wordt gemaakt en
gepubliceerd. Geen mens in de lus.

## Hoe het werkt
1. **GitHub Actions** (`.github/workflows/daily.yml`) draait 3x per dag (07:20 / 13:40 / 18:10 NL).
2. `engine/fetch.py` leest ~14 RSS-bronnen, filtert op AI-relevantie, clustert tot verhalen en
   slaat alles wat al bekeken is over (`content/ledger.json`).
3. `engine/writer.py` laat DeepSeek (`deepseek-flash`, denken uit) een **origineel Nederlands**
   artikel schrijven op basis van alleen de bronnen; de ochtendrun schrijft ook meme + prompt van de
   dag, woensdag een uitleg-artikel (`content/evergreen_seeds.json`), zondag het weekoverzicht.
4. `engine/gate.py` keurt: lengte, titel/meta, Nederlands, geen kopieerrun (≥12 woorden), geen
   onbekende getallen, geen clichés, geen dubbel onderwerp. Faalt = niet publiceren.
   Gevoelige onderwerpen (`HIGH_RISK_TERMS` in `engine/config.py`) worden nooit automatisch gepubliceerd.
5. `engine/render.py` bouwt de statische site (`dist/`), incl. OG-kaarten en meme-beelden via Pillow,
   RSS, sitemap + news-sitemap, JSON-LD, AI-label op elke pagina (EU AI Act art. 50).
6. Publiceren naar GitHub Pages; DNS `chatgpthelp.nl` → Pages.
7. Elke run stuurt één regel naar Slack (ook bij "0 nieuws"): stilte = motor kapot.

## Lokaal
```
pip install -r requirements.txt
set DEEPSEEK_API_KEY=...
python -m engine.run dry      # bronnen bekijken
python -m engine.run run      # editie schrijven (FORCE_MORNING=1 forceert meme/prompt)
python -m engine.run build    # dist/ bouwen
```

## Secrets (repo → Settings → Secrets → Actions)
`DEEPSEEK_API_KEY` (verplicht) · `SLACK_WEBHOOK_URL` (aanbevolen) · `BSKY_HANDLE` + `BSKY_APP_PASSWORD` (optioneel, Bluesky).

## Kosten
DeepSeek ≈ $0,04 per run → < €4/maand. Hosting, build en beelden: €0.
