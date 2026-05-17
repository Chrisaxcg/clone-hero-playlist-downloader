import re
from thefuzz import fuzz

_NOISE_PATTERNS = [
    r"\(feat\..*?\)", r"\(ft\..*?\)", r"\(with .*?\)",
    r"\(remaster.*?\)", r"\(live.*?\)", r"\(acoustic.*?\)",
    r"\(radio edit\)", r"\(official.*?\)", r"\(audio.*?\)",
    r"\[.*?\]", r" - single$", r" - ep$", r" - album version$",
    r" \(explicit\)", r" \(clean\)",
]


def normalize(text: str) -> str:
    text = text.lower()
    for pat in _NOISE_PATTERNS:
        text = re.sub(pat, "", text, flags=re.IGNORECASE)
    # quitar caracteres no alfanuméricos excepto espacios
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def score_match(q_artist: str, q_title: str, r_artist: str, r_title: str) -> int:
    title_score = fuzz.token_sort_ratio(normalize(q_title), normalize(r_title))
    artist_score = fuzz.token_sort_ratio(normalize(q_artist), normalize(r_artist))
    return int(title_score * 0.6 + artist_score * 0.4)


def confidence_label(score: int) -> str:
    if score >= 90:
        return "high"
    if score >= 75:
        return "medium"
    return "low"
