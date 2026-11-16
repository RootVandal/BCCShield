"""Layer 1: weighted RU/KZ fraud phrases with normalisation, crude stemming and fuzzy matching."""
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

CATEGORY_WEIGHTS = {
    "impersonation": 0.35,
    "safe_account": 0.45,
    "credentials": 0.40,
    "loan_pressure": 0.35,
    "remote_access": 0.40,
    "urgency_secrecy": 0.15,
    "transfer_request": 0.20,
}

CATEGORY_LABELS = {
    "impersonation": {"ru": "Представляется банком/полицией", "kk": "Банк/полиция атынан сөйлейді"},
    "safe_account": {"ru": "«Безопасный счёт»", "kk": "«Қауіпсіз шот»"},
    "credentials": {"ru": "Просит коды/данные карты", "kk": "Кодтар мен карта деректерін сұрайды"},
    "loan_pressure": {"ru": "Давление кредитом", "kk": "Несиемен қысым"},
    "remote_access": {"ru": "Удалённый доступ", "kk": "Қашықтан қол жеткізу"},
    "urgency_secrecy": {"ru": "Срочность и секретность", "kk": "Асығыстық және құпиялылық"},
    "transfer_request": {"ru": "Просьба перевести/снять деньги", "kk": "Ақша аудару/шешу өтініші"},
}

# (phrase, category, weight override or None)
PHRASES: list[tuple[str, str, float | None]] = [
    # impersonation
    ("служба безопасности", "impersonation", None),
    ("сотрудник банка", "impersonation", None),
    ("отдел безопасности банка", "impersonation", None),
    ("национальный банк", "impersonation", None),
    ("нацбанк", "impersonation", None),
    ("финмониторинг", "impersonation", None),
    ("агентство по финансовому мониторингу", "impersonation", None),
    ("полиция", "impersonation", 0.25),
    ("следователь", "impersonation", 0.3),
    ("кнб", "impersonation", 0.3),
    ("служба поддержки банка", "impersonation", 0.3),
    ("қауіпсіздік қызметі", "impersonation", None),
    ("банк қызметкері", "impersonation", None),
    ("ұлттық банк", "impersonation", None),
    ("қаржы мониторингі", "impersonation", None),
    ("полиция қызметкері", "impersonation", 0.3),
    # safe_account
    ("безопасный счет", "safe_account", None),
    ("резервный счет", "safe_account", None),
    ("защищенный счет", "safe_account", None),
    ("специальный счет", "safe_account", 0.35),
    ("ячейка центробанка", "safe_account", None),
    ("перевести на безопасную карту", "safe_account", None),
    ("қауіпсіз шот", "safe_account", None),
    ("қорғалған шот", "safe_account", None),
    ("резервтік шот", "safe_account", None),
    # credentials
    ("продиктуйте код", "credentials", None),
    ("код из смс", "credentials", None),
    ("смс код", "credentials", None),
    ("назовите cvv", "credentials", None),
    ("три цифры на обороте", "credentials", None),
    ("срок действия карты", "credentials", 0.3),
    ("кодты айтыңыз", "credentials", None),
    ("смс кодты", "credentials", None),
    ("картаның артындағы үш сан", "credentials", None),
    # loan_pressure
    ("на вас оформляют кредит", "loan_pressure", None),
    ("оформлена заявка на кредит", "loan_pressure", None),
    ("оформите встречный кредит", "loan_pressure", None),
    ("отменить заявку на кредит", "loan_pressure", None),
    ("погасить мошеннический кредит", "loan_pressure", None),
    ("несие рәсімделіп жатыр", "loan_pressure", None),
    ("сіздің атыңызға несие", "loan_pressure", None),
    ("қарсы несие рәсімдеңіз", "loan_pressure", None),
    # remote_access
    ("скачайте anydesk", "remote_access", None),
    ("anydesk", "remote_access", None),
    ("rustdesk", "remote_access", None),
    ("установите приложение", "remote_access", 0.3),
    ("демонстрация экрана", "remote_access", None),
    ("қосымшаны орнатыңыз", "remote_access", 0.3),
    ("экранды көрсетіңіз", "remote_access", None),
    # urgency_secrecy
    ("срочно", "urgency_secrecy", None),
    ("никому не говорите", "urgency_secrecy", 0.25),
    ("не кладите трубку", "urgency_secrecy", 0.25),
    ("тайна следствия", "urgency_secrecy", 0.3),
    ("уголовная ответственность", "urgency_secrecy", 0.25),
    ("ешкімге айтпаңыз", "urgency_secrecy", 0.25),
    ("тұтқаны қоймаңыз", "urgency_secrecy", 0.25),
    ("тез арада", "urgency_secrecy", None),
    ("шұғыл", "urgency_secrecy", None),
    # transfer_request
    ("переведите", "transfer_request", None),
    ("снимите наличные", "transfer_request", 0.25),
    ("через терминал", "transfer_request", 0.25),
    ("внесите на карту", "transfer_request", 0.2),
    ("аударыңыз", "transfer_request", None),
    ("қолма-қол ақша шешіңіз", "transfer_request", 0.25),
]

# category combinations that make the call almost certainly a scam
COMBOS: list[tuple[set[str], float]] = [
    ({"impersonation", "safe_account", "transfer_request"}, 0.96),
    ({"impersonation", "safe_account"}, 0.88),
    ({"impersonation", "credentials"}, 0.85),
    ({"impersonation", "remote_access"}, 0.85),
    ({"impersonation", "loan_pressure"}, 0.72),
    ({"loan_pressure", "transfer_request"}, 0.70),
    ({"safe_account", "transfer_request"}, 0.85),
]

_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)
STEM_LEN = 6


def normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = text.replace("смс-", "смс ").replace("sms", "смс")
    return " ".join(_WORD_RE.findall(text))


def stem(word: str) -> str:
    return word[:STEM_LEN]


def stem_text(text: str) -> str:
    return " ".join(stem(w) for w in normalize(text).split())


@dataclass
class Phrase:
    text: str
    category: str
    weight: float
    stemmed: str


LEXICON = [
    Phrase(p, c, w if w is not None else CATEGORY_WEIGHTS[c], stem_text(p)) for p, c, w in PHRASES
]


@dataclass
class Match:
    phrase: str
    category: str
    weight: float
    score: float


def find_matches(text: str, threshold: int = 88) -> list[Match]:
    stemmed = stem_text(text)
    if not stemmed:
        return []
    tokens = set(stemmed.split())
    found: list[Match] = []
    for ph in LEXICON:
        if ph.stemmed in stemmed and (len(ph.stemmed) >= 6 or ph.stemmed in tokens):
            found.append(Match(ph.text, ph.category, ph.weight, 100.0))
            continue
        if len(ph.stemmed) < 8:  # short phrases: exact only, fuzzy gives false positives
            continue
        score = fuzz.partial_ratio(ph.stemmed, stemmed)
        if score >= threshold:
            found.append(Match(ph.text, ph.category, ph.weight, score))
    return found


def keyword_score(categories: dict[str, float]) -> float:
    """categories: category -> max weight seen during the call."""
    prob_safe = 1.0
    for w in categories.values():
        prob_safe *= 1 - w
    score = 1 - prob_safe
    cats = set(categories)
    for combo, floor in COMBOS:
        if combo <= cats:
            score = max(score, floor)
    return round(min(score, 0.99), 3)


def highlight(text: str, matches: list[Match]) -> list[dict]:
    """Split original text into segments, marking words that belong to matched phrases."""
    stems = set()
    for m in matches:
        stems.update(stem_text(m.phrase).split())
    segments, pos = [], 0
    for m in _WORD_RE.finditer(text):
        if m.start() > pos:
            segments.append({"t": text[pos:m.start()], "hit": False})
        w = stem(normalize(m.group()))
        hit = bool(w) and any(w == s or (len(s) >= 4 and fuzz.ratio(w, s) >= 83) for s in stems)
        segments.append({"t": m.group(), "hit": hit})
        pos = m.end()
    if pos < len(text):
        segments.append({"t": text[pos:], "hit": False})
    return segments
