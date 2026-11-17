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
    "telecom_pretext": 0.20,
    "drop_accusation": 0.35,
    "cash_courier": 0.40,
    "relative_in_trouble": 0.35,
}

CATEGORY_LABELS = {
    "impersonation": {"ru": "Представляется банком/полицией", "kk": "Банк/полиция атынан сөйлейді"},
    "safe_account": {"ru": "«Безопасный счёт»", "kk": "«Қауіпсіз шот»"},
    "credentials": {"ru": "Просит коды/данные карты", "kk": "Кодтар мен карта деректерін сұрайды"},
    "loan_pressure": {"ru": "Давление кредитом", "kk": "Несиемен қысым"},
    "remote_access": {"ru": "Удалённый доступ", "kk": "Қашықтан қол жеткізу"},
    "urgency_secrecy": {"ru": "Срочность и секретность", "kk": "Асығыстық және құпиялылық"},
    "transfer_request": {"ru": "Просьба перевести/снять деньги", "kk": "Ақша аудару/шешу өтініші"},
    "telecom_pretext": {"ru": "Легенда оператора связи", "kk": "Байланыс операторының аңызы"},
    "drop_accusation": {"ru": "Обвинение в дропперстве", "kk": "Дропперлік деп айыптау"},
    "cash_courier": {"ru": "Наличные курьеру / валюта", "kk": "Қолма-қол ақша курьерге / валюта"},
    "relative_in_trouble": {"ru": "«Родственник в беде»", "kk": "«Туысқан қиын жағдайда»"},
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
    # impersonation: agencies named in the 2026 multi-stage calls
    ("киберполиция", "impersonation", 0.3),
    ("афм", "impersonation", 0.3),
    ("сотрудник egov", "impersonation", 0.3),
    ("электронное правительство", "impersonation", 0.25),
    ("киберполиция қызметкері", "impersonation", 0.3),
    # loan_pressure: loans "being taken out" and lifting the credit self-ban
    ("на вас оформляют займы", "loan_pressure", None),
    ("снимите запрет на кредиты", "loan_pressure", None),
    ("отключите стоп кредит", "loan_pressure", None),
    # telecom_pretext: "your SIM expires", contract renewal, SMS-bombing "antispam"
    ("срок действия сим-карты", "telecom_pretext", None),
    ("срок действия sim-карты", "telecom_pretext", None),
    ("сим-карта истекает", "telecom_pretext", None),
    ("продление договора", "telecom_pretext", None),
    ("номер будет заблокирован", "telecom_pretext", None),
    ("оператор сотовой связи", "telecom_pretext", 0.15),
    ("смс атака", "telecom_pretext", None),
    ("услуга антиспам", "telecom_pretext", None),
    ("сим-картаның мерзімі", "telecom_pretext", None),
    ("нөміріңіз бұғатталады", "telecom_pretext", None),
    # drop_accusation: "you are a money mule, a criminal case is opened"
    ("дроппер", "drop_accusation", None),
    ("уголовное дело", "drop_accusation", 0.3),
    ("соучастие", "drop_accusation", 0.3),
    ("соучастник", "drop_accusation", 0.3),
    ("вы проходите как", "drop_accusation", 0.3),
    ("қылмыстық іс", "drop_accusation", 0.3),
    # cash_courier: cash to a courier "for safekeeping", buying currency, a cover story for the teller
    ("передайте курьеру", "cash_courier", None),
    ("курьер заберет", "cash_courier", None),
    ("на хранение", "cash_courier", 0.3),
    ("купите доллары", "cash_courier", None),
    ("купите валюту", "cash_courier", None),
    ("снимите все деньги", "cash_courier", None),
    ("снимите с депозита", "cash_courier", 0.35),
    ("кассиру скажите", "cash_courier", None),
    ("скажите кассиру", "cash_courier", None),
    ("курьерге беріңіз", "cash_courier", None),
    ("доллар сатып алыңыз", "cash_courier", None),
    # relative_in_trouble: a "relative" calling from someone else's number after an accident
    ("попал в аварию", "relative_in_trouble", None),
    ("попал в дтп", "relative_in_trouble", None),
    ("сбил человека", "relative_in_trouble", None),
    ("меня задержали", "relative_in_trouble", None),
    ("с чужого номера", "relative_in_trouble", None),
    ("телефон разбился", "relative_in_trouble", 0.25),
    ("решить вопрос на месте", "relative_in_trouble", None),
    ("карта следователя", "relative_in_trouble", None),
    ("апатқа түстім", "relative_in_trouble", None),
    ("бөтен нөмірден", "relative_in_trouble", None),
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
    ({"telecom_pretext", "credentials"}, 0.75),  # operators never ask for SMS codes
    ({"impersonation", "drop_accusation"}, 0.70),
    ({"drop_accusation", "transfer_request"}, 0.80),
    ({"drop_accusation", "cash_courier"}, 0.90),
    ({"impersonation", "cash_courier"}, 0.88),
    ({"relative_in_trouble", "transfer_request"}, 0.82),
    ({"relative_in_trouble", "urgency_secrecy", "transfer_request"}, 0.90),
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
