from app.models import Account
from app.risk.rules import recipient_story


def acc(**kw):
    a = Account(owner_name="X", bank="Kaspi", card_mask="•• 4417", card_key="kaspi:4417",
                is_external=kw.pop("is_external", True))
    a.features, a.flags = kw.pop("features", {}), kw.pop("flags", {})
    return a


def test_family_rejection_is_told_first():
    ru, _ = recipient_story(acc(flags={"confirmed_drop": True}, features={"bcc_senders": 9, "stranger_share": 1}))
    assert "отклонила семья" in ru


def test_strangers_are_counted_in_words():
    ru, _ = recipient_story(acc(features={"bcc_senders": 9, "stranger_share": 1.0, "under_call_share": 0.5}))
    assert ru == "На эту карту переводили 9 незнакомых владельцу человек, 50% — во время телефонного звонка"


def test_few_strangers_say_nothing():
    assert recipient_story(acc(features={"bcc_senders": 2, "stranger_share": 1.0})) is None
