"""Conservative, deterministic claim checks for Gemini Web drafts.

This is deliberately not an LLM judge. It separates exact quote matching from
lexical/relational support and unit-aware numeric checks. Ambiguous paraphrases
remain ``partial``; hard contradictions or unsupported material are rejected.
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

VERIFICATION_METHOD = "deterministic_lexical_numeric_v1"

_STOP = frozenset("""
 a an the of in on at to for from by with and or but is are was were be been being
 this that these those it its as into around over under about approximately approx yaklasik
 bir ve veya ama ile icin de da olan olarak gibi kadar sonra once ise bu su o her un
 kendi tam birinde kadar daha cok en ancak ise diye tarafindan uzerinde icinde
 planet world source claims claim fact about
 """.split())

# Small bilingual vocabulary for relations that occur in the project's
# encyclopedia-based facts. Unknown paraphrases are not promoted to verified.
_ALIASES = {
    "rotation": {"rotation", "rotations", "rotate", "rotates", "rotating", "spin", "spins", "spinning", "donus", "donusu", "donusunu", "doner", "donerken", "ekseni", "ekseninde", "eksenindeki"},
    "orbit": {"orbit", "orbits", "orbital", "yörünge", "yorunge", "yorungesi", "yorungesinde", "yorungesindeki", "yörüngesi", "yörüngesinde", "tur", "turu", "turunu", "turunda"},
    "complete": {"complete", "completes", "completed", "completing", "takes", "lasts", "surer", "surer", "suruyor", "tamamla", "tamamlar", "tamamladigi", "bitirir", "surer"},
    "sun": {"sun", "solar", "gunes", "gunesi", "gunesin", "gunes cevresinde"},
    "earth": {"earth", "terrestrial", "dunya", "dunyada", "dunyasi", "dunya gunu", "dunya gununde"},
    "day": {"day", "days", "daily", "gun", "gunu", "gununde", "gunluk"},
    "year": {"year", "years", "annual", "yil", "yili", "yilinda", "yillik"},
    "atmosphere": {"atmosphere", "atmospheric", "atmosfer", "atmosferi", "atmosferinde"},
    "heat": {"heat", "heating", "ısı", "isi", "isiyi", "sicaklik", "sicakligi"},
    "trap": {"trap", "traps", "trapped", "retain", "retains", "haps", "hapseder", "hapseder", "tutar"},
    "surface": {"surface", "surfaces", "yuzey", "yuzeyi", "yuzeyinde"},
    "distance": {"distance", "distant", "away", "uzaklik", "uzak", "uzaginda", "mesafe"},
    "speed": {"speed", "velocity", "hiz", "hizla", "saatte"},
    "height": {"height", "tall", "high", "yukseklik", "yuksek", "boyunda"},
    "depth": {"depth", "deep", "derinlik", "derin"},
    "mass": {"mass", "weight", "kitle", "kutle", "agirlik", "agir"},
    "diameter": {"diameter", "cap", "capinda"},
    "eruption": {"eruption", "erupted", "volcanic", "patlama", "patladi", "yanardag", "yanardagi"},
    "discover": {"discover", "discovered", "found", "find", "kesfedildi", "bulundu", "kesfetti"},
    "cause": {"cause", "caused", "because", "due", "neden", "sebep", "yuzunden", "sonucunda"},
}
_ALIAS_TO_CANON = {alias: canonical for canonical, aliases in _ALIASES.items() for alias in aliases}

_RELATION_GROUPS = {
    "rotation": _ALIASES["rotation"], "orbit": _ALIASES["orbit"],
    "duration": _ALIASES["day"] | _ALIASES["year"],
    "distance": _ALIASES["distance"], "speed": _ALIASES["speed"],
    "height": _ALIASES["height"], "depth": _ALIASES["depth"],
    "mass": _ALIASES["mass"], "diameter": _ALIASES["diameter"],
    "eruption": _ALIASES["eruption"],
}

_NEGATIONS = frozenset({"not", "never", "no", "without", "neither", "degil", "yok", "hic", "olmaz", "olmadı", "olmadi", "asla"})

_TR_NUM = {
    "sifir": 0, "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5,
    "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
    "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50, "altmis": 60,
    "yetmis": 70, "seksen": 80, "doksan": 90,
}
_EN_NUM = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_NUM_WORDS = set(_TR_NUM) | set(_EN_NUM) | {"yuz", "hundred", "bin", "thousand", "million", "milyon", "billion", "milyar", "and", "ve"}

# Unit aliases map to dimension and canonical-unit multiplier.
_UNIT_DEFS: tuple[tuple[frozenset[str], str, Decimal, str], ...] = (
    (frozenset({"km h", "km hour", "km hours", "kilometer per hour", "kilometers per hour", "kilometre per hour", "kilometres per hour", "km per hour", "km saat", "km saatte", "km h"}), "speed_kmh", Decimal("1"), "km/h"),
    (frozenset({"m s", "meter per second", "meters per second", "metre per second", "metres per second", "m per second"}), "speed_kmh", Decimal("3.6"), "km/h"),
    (frozenset({"mph", "mile per hour", "miles per hour", "mile hour", "miles hour"}), "speed_kmh", Decimal("1.609344"), "km/h"),
    (frozenset({"km", "kilometer", "kilometers", "kilometre", "kilometres"}), "length_km", Decimal("1"), "km"),
    (frozenset({"m", "meter", "meters", "metre", "metres"}), "length_km", Decimal("0.001"), "km"),
    (frozenset({"cm", "centimeter", "centimeters", "centimetre", "centimetres"}), "length_km", Decimal("0.00001"), "km"),
    (frozenset({"mile", "miles"}), "length_km", Decimal("1.609344"), "km"),
    (frozenset({"light year", "light years", "isik yili", "isik yil"}), "length_ly", Decimal("1"), "ly"),
    (frozenset({"day", "days", "gun", "gunu", "gununde", "gunluk", "gunudur"}), "duration_days", Decimal("1"), "day"),
    (frozenset({"hour", "hours", "hr", "hrs", "saat", "saati", "saatte"}), "duration_days", Decimal(1) / Decimal(24), "day"),
    (frozenset({"minute", "minutes", "min", "mins", "dakika", "dakikada"}), "duration_days", Decimal(1) / Decimal(1440), "day"),
    (frozenset({"second", "seconds", "sec", "secs", "saniye", "saniyede"}), "duration_days", Decimal(1) / Decimal(86400), "day"),
    (frozenset({"year", "years", "yil", "yili", "yilinda", "yillik"}), "duration_days", Decimal("365.2425"), "day"),
    (frozenset({"kg", "kilogram", "kilograms", "kilogramme", "kilogrammes"}), "mass_kg", Decimal("1"), "kg"),
    (frozenset({"g", "gram", "grams", "gramme", "grammes"}), "mass_kg", Decimal("0.001"), "kg"),
    (frozenset({"ton", "tons", "tonne", "tonnes", "ton"}), "mass_kg", Decimal("1000"), "kg"),
    (frozenset({"percent", "percentage", "yuzde", "%"}), "percent", Decimal("1"), "%"),
    (frozenset({"celsius", "centigrade", "c"}), "temperature_c", Decimal("1"), "C"),
    (frozenset({"fahrenheit", "f"}), "temperature_f", Decimal("1"), "F"),
)

_YEAR_MIN, _YEAR_MAX = Decimal(1000), Decimal(2199)


def normalize_text(text: str) -> str:
    text = str(text or "").replace("İ", "i").replace("I", "ı").casefold()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).replace("ı", "i")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+(?:[.,]\d+)*|%", normalize_text(text))


def _stem(token: str) -> str:
    # Conservative Turkish inflection stripping; leaves a minimum 4-char stem.
    for suffix in sorted((
        "larindan", "lerinden", "larindaki", "lerindeki", "larindan", "lerinden",
        "larinin", "lerinin", "larina", "lerine", "lardan", "lerden", "larin",
        "lerin", "larina", "lerine", "indaki", "indeki", "undan", "unden",
        "sinin", "sunun", "daki", "deki", "lari", "leri", "inin", "unun",
        "lar", "ler", "dan", "den", "tan", "ten", "nin", "nun", "nın",
        "nin", "yla", "yle", "yla", "yı", "yi", "yu", "yü", "ina", "ine",
        "inda", "inde", "unda", "unde", "i", "ı", "u", "ü", "a", "e",
    ), key=len, reverse=True):
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            token = token[:-len(suffix)]
            break
    for alias, canonical in _ALIAS_TO_CANON.items():
        if len(alias) >= 4 and token.startswith(alias) and len(token) - len(alias) <= 5:
            token = canonical
            break
    return token


def _canonical_terms(text: str) -> set[str]:
    result: set[str] = set()
    for raw in _tokens(text):
        if raw.isdigit() or re.fullmatch(r"\d+(?:[.,]\d+)*", raw):
            continue
        term = _stem(raw)
        term = _ALIAS_TO_CANON.get(term, _ALIAS_TO_CANON.get(raw, term))
        if term and term not in _STOP and raw not in _STOP and raw not in _NUM_WORDS and len(term) > 1:
            result.add(term)
    return result


def _parse_decimal(token: str) -> Decimal | None:
    value = token.replace(" ", "")
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        tail = value.rsplit(",", 1)[1]
        value = value.replace(",", ".") if len(tail) <= 2 else value.replace(",", "")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _parse_word_number(tokens: list[str], start: int) -> tuple[Decimal, int] | None:
    total = 0
    group = 0
    saw = False
    i = start
    while i < len(tokens) and i - start < 9:
        word = tokens[i]
        if word in {"and", "ve"} and saw:
            i += 1
            continue
        if word in _TR_NUM:
            group += _TR_NUM[word]
            saw = True
        elif word in _EN_NUM:
            value = _EN_NUM[word]
            if value >= 20 and group and group < 10:
                group += value
            elif value < 20 and group >= 20:
                group += value
            else:
                group += value
            saw = True
        elif word in {"yuz", "hundred"}:
            group = (group or 1) * 100
            saw = True
        elif word in {"bin", "thousand"}:
            total += (group or 1) * 1000
            group = 0
            saw = True
        elif word in {"million", "milyon"}:
            total += (group or 1) * 1_000_000
            group = 0
            saw = True
        elif word in {"billion", "milyar"}:
            total += (group or 1) * 1_000_000_000
            group = 0
            saw = True
        else:
            break
        i += 1
    if not saw:
        return None
    return Decimal(total + group), i


def _unit_for(tokens: list[str], end: int, value: Decimal, start: int) -> tuple[str, Decimal, str]:
    following = tokens[end:end + 5]
    preceding = tokens[max(0, start - 2):start]
    if "%" in following or "percent" in following or "percentage" in following or "yuzde" in preceding:
        return "percent", Decimal(1), "%"
    qualifiers = {"earth", "dunya", "solar", "sidereal", "lunar", "metric", "mean", "average", "long", "short"}
    offsets = (1, 0) if following and following[0] in qualifiers else (0,)
    for offset in offsets:
        tail = following[offset:]
        for length in (3, 2, 1):
            if len(tail) < length:
                continue
            phrase = " ".join(tail[:length])
            for aliases, dimension, factor, unit in _UNIT_DEFS:
                if phrase in aliases:
                    return dimension, factor, unit
    # A bare four-digit year is a date, not a dimensionless scalar.
    if _YEAR_MIN <= value <= _YEAR_MAX:
        return "year", Decimal(1), "year"
    # Numeric counts bind to the following lexical noun so 3 hearts != 3 days.
    if following and following[0] not in _STOP and following[0] not in _NUM_WORDS:
        noun = _ALIAS_TO_CANON.get(_stem(following[0]), _stem(following[0]))
        return f"count:{noun}", Decimal(1), noun
    return "scalar", Decimal(1), ""


def extract_numeric_facts(text: str) -> list[dict[str, Any]]:
    tokens = _tokens(text)
    facts: list[dict[str, Any]] = []
    occupied: set[int] = set()
    for i, token in enumerate(tokens):
        if re.fullmatch(r"\d+(?:[.,]\d+)*", token):
            value = _parse_decimal(token)
            if value is None:
                continue
            dimension, factor, unit = _unit_for(tokens, i + 1, value, i)
            facts.append({"value": str(value * factor), "dimension": dimension, "unit": unit})
            occupied.add(i)
    i = 0
    while i < len(tokens):
        if i in occupied or tokens[i] not in _NUM_WORDS:
            i += 1
            continue
        parsed = _parse_word_number(tokens, i)
        if not parsed:
            i += 1
            continue
        value, end = parsed
        # Avoid treating every Turkish indefinite article as a numeric fact.
        following = tokens[end:end + 4]
        has_unit = any(
            " ".join(following[:n]) in aliases
            for n in (1, 2, 3) if len(following) >= n
            for aliases, _dimension, _factor, _unit in _UNIT_DEFS
        )
        has_count_noun = bool(following and following[0] not in _STOP and following[0] not in _NUM_WORDS)
        if value == 1 and not (has_unit or has_count_noun):
            i = max(i + 1, end)
            continue
        dimension, factor, unit = _unit_for(tokens, end, value, i)
        facts.append({"value": str(value * factor), "dimension": dimension, "unit": unit})
        occupied.update(range(i, end))
        i = end
    # Stable de-duplication catches the same number parsed in adjacent forms.
    unique: list[dict[str, Any]] = []
    for fact in facts:
        if fact not in unique:
            unique.append(fact)
    return unique


def _same_quantity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["dimension"] != right["dimension"]:
        return False
    try:
        a, b = Decimal(left["value"]), Decimal(right["value"])
    except InvalidOperation:
        return False
    tolerance = max(abs(a), abs(b), Decimal(1)) * Decimal("0.000001")
    return abs(a - b) <= tolerance


def _relation_groups(text: str) -> set[str]:
    tokens = set(_tokens(text))
    result = set()
    for group, aliases in _RELATION_GROUPS.items():
        if any(_stem(t) in aliases or t in aliases for t in tokens):
            result.add(group)
    return result


def assess_claim(
    claim: str,
    evidence_quote: str,
    source_text: str,
    *,
    source_available: bool = True,
) -> dict[str, Any]:
    """Return independent quote and semantic-support results for one claim."""
    if not source_available or not isinstance(source_text, str) or not source_text.strip():
        return {
            "quote_match": None,
            "semantic_support": "unavailable",
            "reason_codes": ["source_unavailable"],
            "numeric_checks": [],
            "lexical_coverage": 0.0,
            "verification_method": VERIFICATION_METHOD,
        }
    quote = str(evidence_quote or "").strip()
    quote_match = bool(quote and quote in source_text)
    reasons: list[str] = []
    if not quote_match:
        reasons.append("quote_not_found")
        return {
            "quote_match": False,
            "semantic_support": "rejected",
            "reason_codes": reasons,
            "numeric_checks": [],
            "lexical_coverage": 0.0,
            "verification_method": VERIFICATION_METHOD,
        }

    claim_numbers = extract_numeric_facts(claim)
    quote_numbers = extract_numeric_facts(quote)
    numeric_checks = []
    numeric_mismatch = False
    for claimed in claim_numbers:
        matches = [quoted for quoted in quote_numbers if _same_quantity(claimed, quoted)]
        ok = bool(matches)
        numeric_checks.append({
            "claim_value": claimed["value"],
            "dimension": claimed["dimension"],
            "unit": claimed["unit"],
            "matched": ok,
        })
        if not ok:
            numeric_mismatch = True
    if numeric_mismatch:
        reasons.append("numeric_value_or_unit_mismatch")

    claim_terms = _canonical_terms(claim)
    quote_terms = _canonical_terms(quote)
    source_entities_text = " ".join(re.findall(r"\b[A-ZÇĞİÖŞÜ][\wÇĞİÖŞÜçğıöşü'-]*", source_text))
    source_entity_terms = _canonical_terms(source_entities_text)
    # Antecedent subjects may appear immediately before the exact evidence sentence.
    coverage = len(claim_terms & (quote_terms | source_entity_terms)) / max(1, len(claim_terms))
    claim_relations = _relation_groups(claim)
    quote_relations = _relation_groups(quote)
    claim_predicates = claim_relations - {"duration"}
    quote_predicates = quote_relations - {"duration"}
    relation_mismatch = bool(claim_predicates and not (claim_predicates & quote_predicates)) or bool(
        claim_relations == {"duration"} and quote_relations and "duration" not in quote_relations
    )
    if relation_mismatch:
        reasons.append("relation_mismatch")

    claim_negative = bool(set(_tokens(claim)) & _NEGATIONS)
    quote_negative = bool(set(_tokens(quote)) & _NEGATIONS)
    negation_mismatch = claim_negative != quote_negative
    if negation_mismatch:
        reasons.append("negation_mismatch")

    if coverage < 0.25:
        reasons.append("low_lexical_support")
    elif coverage < 0.8:
        reasons.append("ambiguous_lexical_support")
    if not claim_relations:
        reasons.append("semantic_relation_not_covered")

    if numeric_mismatch or relation_mismatch or negation_mismatch or coverage < 0.25:
        support = "rejected"
    elif coverage >= 0.8 and not reasons:
        support = "verified"
    else:
        support = "partial"
    return {
        "quote_match": True,
        "semantic_support": support,
        "reason_codes": reasons,
        "numeric_checks": numeric_checks,
        "lexical_coverage": round(coverage, 4),
        "verification_method": VERIFICATION_METHOD,
    }
