"""Tests voor de stijlpoort in de redactie (gate.stijl_check, de meting en de regels in de opdracht).
Zonder netwerk. Draaien vanuit de repo: python tests/test_stijl.py
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import config, gate, writer  # noqa: E402

fails, n = [], 0


def ok(c, m):
    global n
    n += 1
    if not c:
        fails.append(m)


GOED = {
    "title": "OpenAI brengt agenten naar ChatGPT Plus",
    "meta": "OpenAI zet agenten aan voor ChatGPT Plus. Wat het kan, wat het kost en wanneer het in Nederland komt.",
    "category": "nieuws", "slug": "openai-agenten-plus",
    "intro": "OpenAI zet agenten aan voor ChatGPT Plus. Dat meldt het bedrijf deze week. Je merkt het meteen.",
    "sections": [
        {"heading": "Wat de agent doet", "body": "De agent voert taken uit in je browser. Hij vult formulieren in en zoekt "
                                                 "informatie op. Je kijkt mee en kunt hem stoppen."},
        {"heading": "Wanneer in Nederland", "body": "OpenAI noemt geen datum voor Nederland. Dat is nog niet bekend. "
                                                     "Houd je account in de gaten."},
    ],
    "takeaways": ["Agenten komen naar ChatGPT Plus.", "Een datum voor Nederland is er nog niet."],
    "nl_angle": "Voor Nederland telt vooral de AVG. Bedrijven willen weten waar de data blijft.",
    "faq": [{"q": "Kost het extra?", "a": "OpenAI noemt geen extra prijs. Het zit in Plus."}],
}
ok(gate.stijl_check(GOED) == [], f"een artikel dat de algemene stijlregels haalt: {gate.stijl_check(GOED)}")
streep = dict(GOED, intro=GOED["intro"] + " Snel — en klaar.")
ok([c for c, _m in gate.stijl_check(streep)] == ["S1"], "een gedachtestreepje is een rode stijlregel")
ok("S5" in [c for c, _m in gate.stijl_check(dict(GOED, nl_angle="Het is niet duur maar goedkoop."))], "'niet X maar Y'")
ok("S4" in [c for c, _m in gate.stijl_check(dict(GOED, nl_angle="Dit is een naadloze ervaring."))], "holle woorden")
ok(not any(c in ("S15", "S16", "S17") for c, _m in gate.stijl_check(dict(GOED, title="Agenten: wat ze kunnen"))),
   "geen eisen voor eigen blogs bij nieuws (dubbele punt in de titel, ik/wij-zin, concreet)")

# ---------------------------------------------------------------- meten tegenover blokkeren
with tempfile.TemporaryDirectory() as t:
    gate.STIJL_LOG = Path(t) / "stijl_log.json"
    config.STIJLPOORT = "meten"
    fouten = gate.check_article(dict(streep), "", [], "evergreen")
    ok(not any(f.startswith("stijlpoort") for f in fouten), f"meten: de stijlpoort houdt niets tegen: {fouten}")
    log = json.loads(gate.STIJL_LOG.read_text(encoding="utf-8"))
    ok(len(log) == 1 and log[0]["rood"] == ["S1"] and log[0]["slug"] == "openai-agenten-plus" and log[0]["kind"] == "evergreen"
       and log[0]["stand"] == "meten" and log[0]["andere_fouten"] == len(fouten), f"meten: de meting staat in het logboek: {log}")
    config.STIJLPOORT = "blokkeren"
    fouten_b = gate.check_article(dict(streep), "", [], "evergreen")
    ok([f for f in fouten_b if f.startswith("stijlpoort")] and fouten_b[:len(fouten)] == fouten,
       f"blokkeren: elke rode stijlregel is een poortfout, de andere fouten blijven gelijk: {fouten_b}")
    log = json.loads(gate.STIJL_LOG.read_text(encoding="utf-8"))
    ok(len(log) == 2 and log[1]["andere_fouten"] == len(fouten) and log[1]["stand"] == "blokkeren",
       "ook bij blokkeren telt 'andere fouten' alleen de andere")
    config.STIJLPOORT = "meten"
    gate.STIJL_LOG.write_text(json.dumps([{"x": i} for i in range(gate.STIJL_LOG_MAX)]), encoding="utf-8")
    gate.check_article(dict(GOED), "", [], "evergreen")
    ok(len(json.loads(gate.STIJL_LOG.read_text(encoding="utf-8"))) == gate.STIJL_LOG_MAX, "het logboek groeit niet onbeperkt")
    gate.STIJL_LOG = Path(t) / "bestaat-niet" / "stijl_log.json"
    ok(isinstance(gate.check_article(dict(GOED), "", [], "evergreen"), list), "een mislukte meting houdt niets tegen")

# ---------------------------------------------------------------- de regels in de opdracht
ok(writer.STIJLREGELS in writer.STYLE, "de stijlregels staan in de systeemopdracht van elke schrijfopdracht")
ok(all(t.rstrip("*") in writer.STYLE for t in writer.St.HOL), "elk hol woord van de poort staat letterlijk in de opdracht")
ok(str(writer.St.MAX_GEMIDDELD) in writer.STIJLREGELS and str(writer.St.KORTE_ZIN) in writer.STIJLREGELS, "de grenzen komen uit de poort")
ok("ik- of wij" not in writer.STIJLREGELS.lower(), "geen eis van een ik- of wij-zin bij nieuws")
ok(writer.STYLE.rstrip().endswith("zonder tekst eromheen."), "de opdracht eindigt nog steeds met de JSON-regel")

print(f"\n{n} checks, {len(fails)} mislukt")
for f_ in fails:
    print("  FOUT:", f_)
sys.exit(1 if fails else 0)
