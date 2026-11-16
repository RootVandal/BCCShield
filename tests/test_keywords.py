from app.call_guard.keywords import LEXICON, find_matches, keyword_score


def cats(text):
    return {m.category for m in find_matches(text)}


def test_lexicon_size():
    assert len(LEXICON) >= 40


def test_russian_phrases():
    assert "impersonation" in cats("Здравствуйте, вас беспокоит служба безопасности банка")
    assert "safe_account" in cats("переведите деньги на безопасный счёт")
    assert "credentials" in cats("продиктуйте код из смс")
    assert "remote_access" in cats("скачайте AnyDesk, я помогу")


def test_kazakh_phrases():
    assert "impersonation" in cats("Сізді банктің қауіпсіздік қызметі мазалап тұр")
    assert "safe_account" in cats("ақшаны қауіпсіз шотқа аударыңыз")
    assert "loan_pressure" in cats("сіздің атыңызға несие рәсімделіп жатыр")
    assert "urgency_secrecy" in cats("ешкімге айтпаңыз")


def test_typos_and_inflections():
    assert "impersonation" in cats("служба безопастности")
    assert "safe_account" in cats("на безопасного счета")
    assert "credentials" in cats("смс-код скажите")


def test_neutral_text_has_no_matches():
    assert not find_matches("Напоминаем, у вас завтра приём у терапевта в десять тридцать")
    assert not find_matches("Курьер будет через двадцать минут, какой подъезд?")


def test_combos_raise_score():
    low = keyword_score({"transfer_request": 0.2})
    high = keyword_score({"impersonation": 0.35, "safe_account": 0.45, "transfer_request": 0.2})
    assert low < 0.4
    assert high >= 0.9
