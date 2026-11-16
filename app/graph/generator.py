"""Deterministic synthetic bank: normal clients, merchants, salaries and 3 embedded drop networks."""
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Account, Client, TrustedContact, Transfer
from app.security import new_link_code

FIRST = ["Арман", "Ерлан", "Дамир", "Санжар", "Нурсултан", "Асхат", "Олжас", "Жандос", "Руслан", "Ильяс",
         "Айгерим", "Динара", "Жанна", "Асель", "Мадина", "Камила", "Алия", "Гульмира", "Сабина", "Томирис",
         "Максим", "Андрей", "Ольга", "Елена", "Сергей", "Наталья", "Тимур", "Азамат", "Бекзат", "Аружан"]
LAST = ["Абенов", "Бекова", "Сериков", "Жумабаева", "Касымов", "Нурланова", "Ospanов", "Сагинтаев", "Ким",
        "Иванов", "Петрова", "Тулегенов", "Ахметжанова", "Есенов", "Байжанова", "Муканов", "Смагулова",
        "Утепов", "Кенжебаева", "Рахимов"]
LAST = [n.replace("Ospanов", "Оспанов") for n in LAST]
MERCHANTS = ["ТОО «Magnum Cash&Carry»", "ИП «Аптека Здоровье»", "АО «Алматы Су»", "ТОО «АлматыЭнергоСбыт»",
             "ИП «Кофейня Daily»", "ТОО «Small»", "ИП «Ремонт обуви»", "ТОО «Технодом»", "АО «Казахтелеком»",
             "ТОО «Sulpak»", "ИП «Фрукты-овощи»", "ТОО «Galmart»", "ТОО «Арбуз»", "ИП «Стоматология Smile»",
             "ТОО «Chocofood»", "ИП «Цветы»", "ТОО «Meloman»", "АО «Air Astana»", "ТОО «Kinopark»", "ИП «Такси Алем»"]
EMPLOYERS = ["АО «КазМунайГаз»", "ТОО «Kolesa Group»", "КГУ «Школа-гимназия №25»", "ТОО «Glovo KZ»",
             "АО «Казпочта»", "ГКП «Городская поликлиника №5»"]
EXT_BANKS = ["Kaspi", "Halyk", "Freedom", "Jusan", "Forte"]

DEMO_CLIENTS = [
    # name, age, phone, balance, card last4
    ("Сауле Ахметова", 67, "+77015551201", 2_300_000, "3381"),
    ("Айдар Ахметов", 38, "+77015551202", 640_000, "7720"),
    ("Ерлан Нурланов", 45, "+77015551203", 910_000, "1044"),
    ("Динара Касымова", 33, "+77015551204", 420_000, "5530"),
    ("Нурлан Сейткали", 52, "+77015551205", 1_250_000, "6612"),
    ("Асель Жумабаева", 29, "+77015551206", 180_000, "2207"),
    ("Бауыржан Оспанов", 61, "+77015551207", 760_000, "9145"),
    ("Гульнара Ибраева", 70, "+77015551208", 530_000, "4058"),
    ("Тимур Ким", 41, "+77015551209", 1_040_000, "8836"),
]

# Cards the demo scenario relies on (external, part of drop networks)
SCAM_CARD = ("Kaspi", "4417")        # main scenario recipient
SIGNAL_CARD = ("Freedom", "5512")    # "incoming Antifraud-centre signal" target


def mask(last4: str) -> str:
    return f"•• {last4}"


class _Gen:
    def __init__(self, db: Session, seed: int, now: datetime):
        self.db, self.rng, self.now = db, random.Random(seed), now
        self.start = now - timedelta(days=30)
        self.used_last4: set[str] = set()
        self.transfers: list[Transfer] = []

    def last4(self) -> str:
        while True:
            x = f"{self.rng.randint(1000, 9999)}"
            if x not in self.used_last4:
                self.used_last4.add(x)
                return x

    def account(self, owner, bank="BCC", kind="person", external=False, last4=None, age_days=None,
                client_id=None, flags=None) -> Account:
        last4 = last4 or self.last4()
        self.used_last4.add(last4)
        age_days = age_days if age_days is not None else self.rng.randint(300, 3600)
        a = Account(client_id=client_id, owner_name=owner, bank=bank, card_mask=mask(last4),
                    card_key=f"{bank.lower()}:{last4}", kind=kind, is_external=external,
                    opened_at=self.now - timedelta(days=age_days), flags=flags or {})
        self.db.add(a)
        return a

    def person_name(self) -> str:
        first, last = self.rng.choice(FIRST), self.rng.choice(LAST)
        female = first in FIRST[10:20] or first in ("Ольга", "Елена", "Наталья", "Аружан")
        if female and not last.endswith("а"):
            last += "а"
        if not female and last.endswith("ва"):
            last = last[:-1]
        return f"{first} {last}"

    def t(self, a: Account, b: Account, amount: float, when: datetime, **ctx):
        self.transfers.append(Transfer(from_account_id=a.id, to_account_id=b.id, amount=round(amount, -2),
                                       created_at=when, status="completed", synthetic=True, context=ctx))

    def rand_time(self, days_from=0.0, days_to=30.0) -> datetime:
        return self.start + timedelta(seconds=self.rng.uniform(days_from * 86400, days_to * 86400))


def generate(db: Session, seed: int = 42, now: datetime | None = None) -> dict:
    g = _Gen(db, seed, now or datetime.now())
    rng = g.rng

    clients, client_acc = [], []
    for name, age, phone, balance, l4 in DEMO_CLIENTS:
        c = Client(name=name, age=age, phone=phone, balance=balance, language="ru")
        db.add(c)
        db.flush()
        clients.append(c)
        client_acc.append(g.account(name, last4=l4, client_id=c.id))
    saule, aidar = clients[0], clients[1]
    db.add(TrustedContact(client_id=saule.id, name="Айдар", relation="сын", phone=aidar.phone,
                          link_code=new_link_code("SAULE"), amount_threshold=100_000))

    persons = [g.account(g.person_name()) for _ in range(300)]
    externals = [g.account(g.person_name(), bank=rng.choice(EXT_BANKS), external=True) for _ in range(60)]
    merchants = [g.account(m, kind="merchant", age_days=rng.randint(700, 4000)) for m in MERCHANTS]
    suppliers = [g.account(f"Поставщик {i + 1}", bank=rng.choice(EXT_BANKS), kind="merchant", external=True)
                 for i in range(5)]
    employers = [g.account(e, kind="employer", age_days=rng.randint(2000, 5000)) for e in EMPLOYERS]
    pension = g.account("НАО «Правительство для граждан» (пенсия)", kind="employer", age_days=5000)
    db.flush()

    # --- normal life -------------------------------------------------------------------------------
    everyone = persons + client_acc[2:]
    for p in everyone:
        if rng.random() < 0.7:
            g.t(rng.choice(employers), p, rng.uniform(250_000, 700_000), g.rand_time(1, 28), kind="salary")
        friends = rng.sample(persons + client_acc[2:], rng.randint(2, 4))
        friends += rng.sample(externals, 1) if rng.random() < 0.4 else []
        for f in friends:
            if f is p:
                continue
            for _ in range(rng.randint(1, 3)):
                g.t(p, f, rng.uniform(3_000, 60_000), g.rand_time(), kind="p2p")
            if rng.random() < 0.55:
                for _ in range(rng.randint(1, 2)):
                    g.t(f, p, rng.uniform(3_000, 50_000), g.rand_time(), kind="p2p")
        for _ in range(rng.randint(3, 9)):
            g.t(p, rng.choice(merchants), rng.uniform(2_000, 40_000), g.rand_time(), kind="payment")
    for m in merchants:  # weekly payout to supplier
        for week in range(4):
            g.t(m, rng.choice(suppliers), rng.uniform(200_000, 900_000), g.rand_time(week * 7 + 5, week * 7 + 7),
                kind="payout")

    # legit "fast transit" look-alikes: group collections forwarded to a shop (realistic false positives)
    decoys = [g.account(g.person_name(), age_days=rng.randint(5, 40), flags={"decoy": "сбор денег на подарок"})
              for _ in range(4)]
    db.flush()
    for org in decoys:
        day = rng.uniform(3, 26)
        last = g.start
        for f in rng.sample(persons, rng.randint(4, 6)):
            last = max(last, g.rand_time(day, day + 0.5))
            g.t(f, org, rng.uniform(5_000, 20_000), last, kind="p2p")
        g.t(org, rng.choice(merchants), 70_000, last + timedelta(minutes=rng.uniform(15, 60)), kind="payment")

    # Saule & Aidar: a calm, repetitive history (so "transfer to son" stays low risk)
    s_acc, a_acc = client_acc[0], client_acc[1]
    g.t(pension, s_acc, 148_000, g.start + timedelta(days=5, hours=10), kind="pension")
    g.t(pension, s_acc, 148_000, g.start + timedelta(days=28, hours=10), kind="pension")
    for d, amt in ((3, 30_000), (9, 50_000), (16, 25_000), (22, 60_000), (27, 40_000)):
        g.t(s_acc, a_acc, amt, g.start + timedelta(days=d, hours=13), kind="p2p")
    g.t(a_acc, s_acc, 20_000, g.start + timedelta(days=12, hours=19), kind="p2p")
    for d in (2, 6, 11, 15, 19, 24, 29):
        g.t(s_acc, rng.choice(merchants[:5]), rng.uniform(4_000, 18_000), g.start + timedelta(days=d, hours=11),
            kind="payment")
    g.t(rng.choice(employers), a_acc, 520_000, g.start + timedelta(days=10, hours=9), kind="salary")
    for d in (4, 14, 25):
        g.t(a_acc, rng.choice(merchants), rng.uniform(5_000, 30_000), g.start + timedelta(days=d, hours=18),
            kind="payment")

    # --- drop networks -----------------------------------------------------------------------------
    cash = g.account("Наличные (банкоматы)", bank="ATM", kind="cash", external=True, last4="0000", age_days=5000)
    victim_pool = [p for p in persons]
    rng.shuffle(victim_pool)
    networks = [
        {"name": "Сеть A «безопасный счёт»", "victims": 12, "l1": 3, "l2": 1,
         "ext_l1": SCAM_CARD, "ext_direct": 4, "cashout": [("Halyk", None)], "complaint": True},
        {"name": "Сеть B «встречный кредит»", "victims": 12, "l1": 4, "l2": 2,
         "ext_l1": SIGNAL_CARD, "ext_direct": 3, "cashout": [("Kaspi", None), ("Jusan", None)], "complaint": True,
         "extra_victims": [client_acc[7]]},
        {"name": "Сеть C «инвестиции» (без жалоб)", "victims": 10, "l1": 3, "l2": 1,
         "ext_l1": None, "ext_direct": 0, "cashout": [("Kaspi", None), ("Forte", None)], "complaint": False},
    ]
    summary = []
    for ni, net in enumerate(networks):
        tag = {"network": ni + 1}
        gt = {"gt_drop": True, **tag}
        l1 = [g.account(g.person_name(), age_days=rng.randint(4, 20), flags=dict(gt)) for _ in range(net["l1"])]
        l2 = [g.account(g.person_name(), age_days=rng.randint(4, 25), flags=dict(gt)) for _ in range(net["l2"])]
        outs = [g.account(g.person_name(), bank=b, external=True, last4=l4, age_days=rng.randint(10, 60),
                          flags=dict(gt)) for b, l4 in net["cashout"]]
        ext_l1 = None
        if net["ext_l1"]:
            b, l4 = net["ext_l1"]
            ext_l1 = g.account(g.person_name(), bank=b, external=True, last4=l4, age_days=30, flags=dict(gt))
            outs.append(ext_l1)
        if net["complaint"]:
            l1[0].flags = {**l1[0].flags, "complaints": 1}
        db.flush()

        victims = [victim_pool.pop() for _ in range(net["victims"])] + net.get("extra_victims", [])
        for v in victims:
            v.flags = {**(v.flags or {}), "gt_victim": True, **tag}
        for vi, v in enumerate(victims):
            when = g.rand_time(3, 29)
            amount = rng.uniform(300_000, 2_500_000)
            call = rng.random() < 0.65
            direct = ext_l1 is not None and (vi < net["ext_direct"] or v in net.get("extra_victims", []))
            if direct:
                g.t(v, ext_l1, amount, when, kind="victim", call_active=call)
                continue
            d1 = l1[(vi - (net["ext_direct"] if ext_l1 else 0)) % len(l1)]
            g.t(v, d1, amount, when, kind="victim", call_active=call)
            t1 = when + timedelta(minutes=rng.uniform(1, 10))
            d2 = rng.choice(l2)
            g.t(d1, d2, amount * rng.uniform(0.95, 0.98), t1, kind="drop")
            t2 = t1 + timedelta(minutes=rng.uniform(2, 12))
            rest = amount * 0.93
            targets = rng.sample(outs + [cash], 2)
            share = rng.uniform(0.4, 0.7)
            g.t(d2, targets[0], rest * share, t2, kind="cashout")
            g.t(d2, targets[1], rest * (1 - share), t2 + timedelta(minutes=rng.uniform(1, 6)), kind="cashout")
        summary.append({"name": net["name"], "victims": len(victims), "droppers": len(l1) + len(l2) + len(outs)})

    db.flush()
    db.add_all(g.transfers)
    db.commit()
    return {"accounts": db.query(Account).count(), "transfers": len(g.transfers), "networks": summary}
