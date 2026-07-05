"""
Albert OS — Planner Engine
Spek: 27_AI_CORE_BIBLE.md

Keerulised päringud lahutatakse sammudeks enne AI-le saatmist.
Planner ei täida samme ise — see koostab täitmisplaani,
mida JarvisDirector järjestikku/paralleelselt täidab.
"""

# ── Keeruliste päringute mustrid ──────────────────────────────────────────────
# Iga muster: (keyword_list, step_list)
COMPLEX_PATTERNS = [
    # BMW diagnostika
    (
        ["bmw", "бмв", "ремонт bmw", "repair bmw", "bmw rike", "bmw viga"],
        [
            "Kogu sümptomid: mis häält/käitumist märgatakse",
            "Otsi mälust varasemad BMW probleemid ja lahendused",
            "Analüüsi pilt kui saadaval (mootor, armatuurlaud, viga kood)",
            "Otsi dokumentatsioonist (BMW ISTA, veakoodid, tehniline info)",
            "Koosta remondiplaan koos osanimekirja ja tööjärjestusega",
        ],
    ),
    # Paadi diagnostika
    (
        ["paat", "лодк", "boat", "jaht", "мотор лодк", "marine"],
        [
            "Kogu sümptomid: mootor, elektroonika, navigatsioon",
            "Otsi mälust varasemad paadi hooldus- ja remondikanded",
            "Analüüsi pilt kui saadaval",
            "Kontrolli ilmateavet ja merevoogusid kui asjakohane",
            "Koosta ohutu tegutsemisplaan",
        ],
    ),
    # Ehitus/remont
    (
        ["ehitus", "remont", "строительств", "ремонт дом", "construction", "build"],
        [
            "Täpsusta töö maht ja asukohaga seotud nõuded",
            "Otsi mälust varasemad ehitusprojekti kanded",
            "Loe vajalikud materjalid ja tööriistad",
            "Koosta tööde järjestus koos ajahinnangutega",
            "Too välja ohutuspunktid ja load mis võivad kellida",
        ],
    ),
    # Reisimine
    (
        ["reisi", "trip", "travel", "поездк", "путешестви", "lend", "flight"],
        [
            "Uuri sihtkohta: ilm, sündmused, transpordiühendused",
            "Koosta marsruut koos ajahinnangutega",
            "Kontrolli dokumente: pass, viisa, kindlustus",
            "Lisa kalenderisse",
        ],
    ),
    # Uurimistöö / raport
    (
        ["researchi", "uuri", "raport", "report", "analyse", "analüüsi kõik",
         "исследова", "подготов отчёт"],
        [
            "Defineeri uurimisküsimus",
            "Otsi olemasolevad allikad ja mälukanded",
            "Kogu uued andmed veebist (Perplexity)",
            "Võrdle ja kontrollita allikad",
            "Kirjuta struktureeritud kokkuvõte",
        ],
    ),
    # Koodiülesanne
    (
        ["implement", "implementeeri", "реализуй", "create system", "loo süsteem",
         "build feature", "refactor", "refaktori"],
        [
            "Analüüsi nõudeid ja olemasolevat koodi",
            "Plaani arhitektuur: moodulid, liidesed, andmevoog",
            "Implementeeri samm-sammult",
            "Testi äärmuslikke juhtumeid",
            "Dokumenteeri muutused",
        ],
    ),
]

# Lävi: mitu märksõna peab kattuma et loetaks keeruliseks
_COMPLEX_THRESHOLD = 1


def is_complex_request(prompt: str, intent: str) -> bool:
    """Tagastab True kui päring on piisavalt keeruline et planeerimist vajada."""
    # Lühikesed päringud pole kunagi keerulised
    if len((prompt or "").split()) < 5:
        return False
    # Teatud intentid on alati komplekssed
    if intent in ("bmw_diagnostics", "boat_diagnostics", "construction", "research"):
        return True
    # Mustrite kontroll
    p = (prompt or "").lower()
    for keywords, _ in COMPLEX_PATTERNS:
        if sum(1 for kw in keywords if kw in p) >= _COMPLEX_THRESHOLD:
            return True
    return False


def build_plan(prompt: str, intent: str) -> list[str]:
    """
    Tagastab sammude nimekirja keerulise päringu jaoks.
    Sammud lisatakse süsteemsesse prompti kontekstina.
    """
    p = (prompt or "").lower()

    # Leia parim mustri vaste
    for keywords, steps in COMPLEX_PATTERNS:
        if any(kw in p for kw in keywords):
            return steps

    # Üldine plaan tundmatute keeruliste päringute jaoks
    return [
        "Täpsusta eesmärk ja kontekst",
        "Otsi olemasolev informatsioon mälust",
        "Leia vajalik lisainformatsioon",
        "Koosta struktureeritud vastus",
    ]


def format_plan_for_prompt(steps: list[str]) -> str:
    """Formaadi plaan süsteemprompti lisamiseks."""
    lines = ["Execute this request step by step:"]
    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")
    lines.append("Address each step concisely. Combine steps where sensible.")
    return "\n".join(lines)
