#!/usr/bin/env python3
"""seo_stijl — de stijlpoort: leest een tekst als standaard AI-tekst, of als een mens die iets te zeggen heeft?

Wens van Maxim (03-10-2026): alles met ziel geschreven, ook de blogs; geen standaard AI-stijl. "Ziel"
is niet te meten, maar wat een tekst als AI verraadt wel: gedachtestreepjes, holle woorden, de
constructie "niet X maar Y", drieslagen, zinnen die allemaal even lang zijn, alinea's die steeds
hetzelfde beginnen, een slot dat samenvat, en bij een artikel: geen persoon en niets concreets.
Deze poort telt dat, zonder taalmodel. Wat hij afkeurt wordt niet gepubliceerd; of een tekst die
erdoor komt ook echt goed is, bepaalt de blindtest uit het plan.

De regels komen uit knowledge/schrijfregels-website.md (§0 en §6) en het plan (fase 3). De woorden
waar de poort op afkeurt staan hier als letterlijke lijst; ze horen ook letterlijk als verbodenlijst
in de opdracht aan de schrijver (les van 21-09: een poort waar de schrijver niets van weet, keurt
alleen maar af).

Alleen de standaardbibliotheek, zodat het bestand naast elke schrijfmotor kan staan.
Niveaus als in site_verify.py: 1 = rood (afkeur), 2 = oranje (opmerking).

Gebruik (vanuit de repo-root):
    py scripts/seo_stijl.py artikel.md                 # Markdown met front matter (title, h1) of platte tekst
    py scripts/seo_stijl.py tekst.txt --soort landingspagina
"""
import argparse
import re
import statistics
import sys
from pathlib import Path

ROOD, ORANJE = 1, 2
SOORTEN = ("artikel", "landingspagina", "vraagpagina", "sectie")
MAX_GEMIDDELD = 15              # woorden per zin, gemiddeld
MIN_SPREIDING = 5.0             # standaardafwijking van de zinslengte, in woorden
KORTE_ZIN = 6                   # een zin van hooguit zes woorden
VENSTER_KORT = 150              # per 150 woorden minstens één korte zin
DRIESLAG_PER = 300              # hooguit één drieslag per 300 woorden
MAX_ZINNEN_ALINEA = 3

# Holle woorden en zinsdelen. Letterlijk, in kleine letters; een sterretje staat voor de rest van het woord.
HOL = (
    "naadloos", "naadloze", "ontdek", "transform*", "op maat", "hoogwaardig*", "passie", "jouw partner in",
    "uw partner in", "in de wereld van", "of je nu", "of u nu", "niet alleen", "laten we", "duik in", "duiken we",
    "in een tijd waarin", "ultieme", "unieke ervaring", "in de huidige digitale wereld", "game changer", "gamechanger",
    "revolutionair*", "cruciaal", "cruciale", "essentieel", "essentiële", "het is belangrijk om", "in dit artikel",
    "in deze blog", "in dit blog", "hieronder lees je", "lees verder", "in een notendop", "de sleutel tot",
    "naar een hoger niveau", "next level", "state of the art", "baanbrekend*", "toonaangevend*", "innovatieve oplossing*",
    "ontzorgen", "van a tot z", "klaar om", "bij ons staat", "geloven we", "wij geloven", "in het huidige landschap",
    "digitale landschap", "snel veranderende", "steeds veranderende", "het is geen geheim", "zoals je ziet",
    "zoals gezegd", "zoals eerder genoemd", "al met al", "kortom", "samengevat", "samenvattend", "concluderend",
    "tot slot", "afsluitend", "het is duidelijk dat", "vergeet niet", "aarzel niet", "wacht niet langer", "neem vandaag nog",
    "ervaar het zelf", "ongeëvenaard*", "eindeloze mogelijkheden", "de kracht van", "ontgrendel*", "til je",
)
OPENERS = ("daarnaast", "bovendien", "kortom", "tot slot", "al met al", "daarbij", "tevens", "verder", "ook", "tenslotte",
           "ten slotte", "daarom")
SLOTWOORDEN = ("kortom", "samengevat", "samenvattend", "al met al", "tot slot", "concluderend", "conclusie", "kort gezegd",
               "in het kort", "om af te sluiten", "afsluitend", "ten slotte", "tenslotte", "hopelijk")
# Na "maar" begint met deze woorden een nieuwe bijzin ("ik adviseer hem niet, maar hij bestaat"); dat is
# gewoon Nederlands. Zonder zo'n woord is het de correctie-constructie "niet X maar Y".
NIEUWE_BIJZIN = ("hij", "zij", "ze", "het", "dat", "dit", "die", "ik", "je", "jij", "we", "wij", "u", "er", "dan", "wel",
                 "ook", "als", "daar", "hier", "nu", "soms", "vaak", "meestal")
PERSOON = re.compile(r"\b(ik|wij|we|mijn|mij|onze|ons)\b", re.I)
AFKORTINGEN = ("bijv.", "bv.", "o.a.", "d.w.z.", "ca.", "nr.", "evt.", "incl.", "excl.", "max.", "min.", "t.o.v.", "o.m.",
               "etc.", "enz.", "resp.", "i.p.v.", "m.b.t.", "t.a.v.", "z.s.m.", "n.v.t.", "a.u.b.", "dr.", "mr.", "ing.", "drs.")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿\U0001F1E6-\U0001F1FF]")


def woorden(tekst):
    """De woorden van een tekst. Een getal als 7,5 of 2.000 is één woord, 'e-bike' en 'da's' ook."""
    return re.findall(r"\d+(?:[.,]\d+)*|[0-9A-Za-zÀ-ÿ]+(?:['’\-][0-9A-Za-zÀ-ÿ]+)*", tekst or "")


def zinnen(tekst):
    """Splitst in zinnen. Afkortingen en getallen met een punt breken een zin niet."""
    t = " ".join((tekst or "").split())
    for a in AFKORTINGEN:
        # alleen als los woord: "ing." is een afkorting, het eind van "voorbereiding." niet
        t = re.sub(r"(?<![0-9A-Za-zÀ-ÿ])" + re.escape(a), a.replace(".", "․"), t, flags=re.I)
    t = re.sub(r"(?<=\d)\.(?=\d)", "․", t)
    delen = re.split(r"(?<=[.!?])[\"'”’)]*\s+(?=[\"'“‘(]?[A-ZÀ-Þ0-9])", t)
    return [d.replace("․", ".").strip() for d in delen if d.strip()]


def _hol_patroon(term):
    stam = re.escape(term.rstrip("*"))
    return re.compile(r"(?<![0-9A-Za-zÀ-ÿ])" + stam + (r"[0-9A-Za-zÀ-ÿ]*" if term.endswith("*") else r"(?![0-9A-Za-zÀ-ÿ])"), re.I)


_HOL = [(t, _hol_patroon(t)) for t in HOL]


def holle_woorden(tekst):
    """De holle woorden en zinsdelen die in de tekst staan (elk één keer)."""
    return [t.rstrip("*") for t, p in _HOL if p.search(tekst or "")]


def niet_maar(zin):
    """Staat hier de correctie-constructie "niet X maar Y" (of "geen X maar Y")?"""
    for m in re.finditer(r"\b(?:niet|geen)\b([^.!?;:]{1,90}?)\bmaar\b\s*(\w+)?", zin, re.I):
        na = (m.group(2) or "").lower()
        if na in NIEUWE_BIJZIN:
            continue
        return True
    return False


def drieslagen(tekst):
    """Opsommingen van precies drie ("snel, betrouwbaar en voordelig")."""
    stuk = r"[0-9A-Za-zÀ-ÿ'’\-]+(?: [0-9A-Za-zÀ-ÿ'’\-]+){0,2}"
    patroon = re.compile(r"(?<![,;] )\b(" + stuk + r"), (" + stuk + r"),? en (" + stuk + r")\b", re.I)
    return [m.group(0) for m in patroon.finditer(tekst or "")]


def _concreet(alinea):
    """Staat er iets concreets in: een getal, of een naam (hoofdletterwoord dat geen zin opent)?"""
    if re.search(r"\d", alinea):
        return True
    for z in zinnen(alinea):
        if re.search(r"(?<=\w[ ,;:(])[A-ZÀ-Þ][0-9A-Za-zÀ-ÿ]+", z[1:]):
            return True
    return False


def toets(alineas, soort="artikel", title="", h1="", koppen=()):
    """Toetst een tekst. `alineas` is een lijst alinea's (platte tekst), `koppen` de tussenkoppen.

    Geeft {"ok": geen rood, "bevindingen": [(ernst, code, melding)], "cijfers": {...}}.
    """
    if soort not in SOORTEN:
        raise ValueError(f"onbekende soort: {soort}")
    alineas = [" ".join(str(a).split()) for a in alineas if str(a).strip()]
    alles = " ".join([title, h1, *koppen, *alineas])
    b = []

    def meld(ernst, code, tekst):
        b.append((ernst, code, tekst))

    zin_lijst = [z for a in alineas for z in zinnen(a)]
    lengtes = [len(woorden(z)) for z in zin_lijst]
    n_woorden = sum(lengtes)
    cijfers = {"woorden": n_woorden, "zinnen": len(zin_lijst), "alineas": len(alineas),
               "gemiddeld": round(n_woorden / len(zin_lijst), 1) if zin_lijst else 0.0,
               "spreiding": round(statistics.pstdev(lengtes), 1) if len(lengtes) > 1 else 0.0}
    if not alineas:
        return {"ok": False, "bevindingen": [(ROOD, "S0", "Geen tekst.")], "cijfers": cijfers}

    # ---- tekens
    if "—" in alles or re.search(r"\s[–-]\s", alles):
        meld(ROOD, "S1", "Gedachtestreepje. Gebruik een punt, komma of dubbele punt.")
    if "!" in " ".join(alineas):
        meld(ROOD, "S2", "Uitroepteken in de lopende tekst.")
    if EMOJI.search(alles):
        meld(ROOD, "S3", "Emoji in de tekst.")

    # ---- holle woorden
    hol = holle_woorden(alles)
    if hol:
        meld(ROOD, "S4", "Holle woorden: " + ", ".join(hol[:8]) + ".")

    # ---- niet X maar Y
    fout = [z for z in zin_lijst if niet_maar(z)]
    if fout:
        meld(ROOD, "S5", f"'Niet X maar Y' ({len(fout)} keer). Zeg wat het wél is: \"{fout[0][:90]}\"")

    # ---- drieslagen
    ds = drieslagen(" ".join(alineas))
    toegestaan = max(1, n_woorden // DRIESLAG_PER)
    if len(ds) > toegestaan:
        meld(ROOD, "S6", f"{len(ds)} drieslagen op {n_woorden} woorden (hooguit {toegestaan}): \"{ds[0][:70]}\"")

    # ---- zinslengte
    if zin_lijst and cijfers["gemiddeld"] > MAX_GEMIDDELD:
        meld(ROOD, "S7", f"Gemiddeld {cijfers['gemiddeld']} woorden per zin; hooguit {MAX_GEMIDDELD}.")
    # Alleen bij langere zinnen: een tekst van korte zinnen (gemiddeld tot 10 woorden) heeft vanzelf een kleine
    # spreiding en is daarmee niet eentonig; daar waakt S10 tegen vier even lange zinnen op rij.
    if len(lengtes) >= 8 and cijfers["gemiddeld"] > 10 and cijfers["spreiding"] < MIN_SPREIDING:
        meld(ROOD, "S8", f"De zinnen zijn te gelijk van lengte (spreiding {cijfers['spreiding']}, minstens {MIN_SPREIDING}).")
    sinds_kort = 0
    for n_ in lengtes:
        if n_ <= KORTE_ZIN:
            sinds_kort = 0
        else:
            sinds_kort += n_
            if sinds_kort > VENSTER_KORT:
                meld(ROOD, "S9", f"Meer dan {VENSTER_KORT} woorden achter elkaar zonder één korte zin (hooguit {KORTE_ZIN} woorden).")
                break
    for i in range(len(lengtes) - 3):
        vier = lengtes[i:i + 4]
        if min(vier) > KORTE_ZIN and max(vier) - min(vier) <= 2:
            meld(ROOD, "S10", f"Vier zinnen op rij van bijna dezelfde lengte ({', '.join(map(str, vier))} woorden).")
            break

    # ---- alinea's
    begin = [" ".join(w.lower() for w in woorden(a)[:2]) for a in alineas]
    for i in range(1, len(begin)):
        if begin[i] and begin[i] == begin[i - 1]:
            meld(ROOD, "S11", f"Twee alinea's achter elkaar beginnen met \"{begin[i]}\".")
            break
    openers = [a for a in alineas if any(re.match(re.escape(o) + r"\b", a, re.I) for o in OPENERS)]
    if len(openers) > 1:
        meld(ROOD, "S12", f"{len(openers)} alinea's openen met een voegwoord als 'daarnaast' of 'bovendien' (hooguit één).")
    if len(alineas) >= 3:
        slot = alineas[-1].lower()
        if any(re.match(re.escape(s) + r"\b", slot) for s in SLOTWOORDEN):
            meld(ROOD, "S13", "De laatste alinea vat samen. Eindig met het laatste nieuwe punt, of met wat de lezer nu kan doen.")
    lang = [a for a in alineas if len(zinnen(a)) > MAX_ZINNEN_ALINEA]
    if lang:
        meld(ORANJE, "S14", f"{len(lang)} alinea('s) met meer dan {MAX_ZINNEN_ALINEA} zinnen.")

    # ---- alleen artikelen: een persoon en iets concreets
    if soort == "artikel":
        if ":" in (title or "") or ":" in (h1 or ""):
            meld(ROOD, "S15", "Dubbele punt in de title of h1 van een artikel.")
        personen = [z for z in zin_lijst if PERSOON.search(z)]
        if len(personen) < 2:
            meld(ROOD, "S16", "Geen persoon in het artikel: er staat geen ik- of wij-zin in. Zonder eigen ervaring of standpunt "
                              "is het een naslagwerk.")
        vaag = [a for a in alineas if len(woorden(a)) >= 25 and not _concreet(a)]
        if alineas and len(vaag) * 3 > len(alineas):
            meld(ROOD, "S17", f"{len(vaag)} van de {len(alineas)} alinea's bevatten niets concreets (getal, naam, plaats, datum).")
        elif vaag:
            meld(ORANJE, "S17", f"{len(vaag)} alinea('s) zonder iets concreets.")
    b.sort(key=lambda x: (x[0], int(x[1][1:])))
    return {"ok": not any(e == ROOD for e, _c, _m in b), "bevindingen": b, "cijfers": cijfers}


def uit_markdown(md):
    """(title, h1, koppen, alineas) uit Markdown met optionele front matter. Opsommingen tellen als alinea."""
    tekst = (md or "").replace("\r\n", "\n")
    title = h1 = lead = ""
    m = re.match(r"^---\n(.*?)\n---\n", tekst, re.S)
    if m:
        for regel in m.group(1).split("\n"):
            k, _, v = regel.partition(":")
            v = v.strip().strip('"').strip("'")
            if k.strip() == "title":
                title = v
            elif k.strip() == "h1":
                h1 = v
            elif k.strip() == "lead":
                lead = v
        tekst = (lead + "\n\n" if lead else "") + tekst[m.end():]        # de inleiding is de eerste alinea
    koppen, alineas = [], []
    for blok in re.split(r"\n\s*\n", tekst):
        blok = blok.strip()
        if not blok:
            continue
        if blok.startswith("#"):
            regels = blok.split("\n")
            kop = regels[0].lstrip("#").strip()
            if regels[0].startswith("# ") and not h1:
                h1 = kop
            else:
                koppen.append(kop)
            blok = "\n".join(regels[1:]).strip()
            if not blok:
                continue
        schoon = re.sub(r"^\s*[-*]\s+", "", blok, flags=re.M)
        schoon = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", schoon)
        schoon = re.sub(r"[*_`]", "", schoon)
        alineas.append(" ".join(schoon.split()))
    return title, h1, koppen, alineas


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Stijlpoort: geen standaard AI-stijl")
    ap.add_argument("bestand")
    ap.add_argument("--soort", default="artikel", choices=SOORTEN)
    a = ap.parse_args()
    title, h1, koppen, alineas = uit_markdown(Path(a.bestand).read_text(encoding="utf-8"))
    r = toets(alineas, a.soort, title, h1, koppen)
    c = r["cijfers"]
    print(f"{a.bestand}: {c['woorden']} woorden, {c['zinnen']} zinnen, gemiddeld {c['gemiddeld']} per zin, spreiding {c['spreiding']}")
    for ernst, code, tekst in r["bevindingen"]:
        print(f"   {'ROOD  ' if ernst == ROOD else 'ORANJE'} {code}  {tekst}")
    print("OORDEEL:", "GROEN" if r["ok"] else "AFGEKEURD")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
