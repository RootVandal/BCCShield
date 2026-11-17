"""Per-account dropper features, explainable weighted score, risk propagation and metrics."""
import math
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

import community as community_louvain
import networkx as nx
from sqlalchemy.orm import Session

from app.models import Account, AntifraudSignal, Transfer

DROP_THRESHOLD = 60
LINKED_THRESHOLD = 50
PROPAGATION_DECAY = 0.6
PROPAGATION_STEPS = 3
PROPAGATION_BASE = 35

BCC_WEIGHTS = {  # feature -> (weight, label)
    "senders": (0.14, "Много уникальных отправителей за 7 дней"),
    "stranger": (0.14, "Входящие от незнакомых (без взаимных переводов)"),
    "dwell": (0.24, "Быстрый вывод после поступления"),
    "transit": (0.22, "Транзит: входящее уходит дальше в течение суток"),
    "young": (0.08, "Новый счёт"),
    "under_call": (0.12, "Входящие от клиентов «под звонком»"),
    "pagerank": (0.06, "Высокая центральность в графе (PageRank)"),
}
EXT_WEIGHTS = {
    "bcc_senders": (0.25, "Переводы от многих клиентов БЦК"),
    "stranger": (0.15, "Отправители не связаны с получателем"),
    "under_call": (0.20, "Переводы клиентов «под звонком»"),
    "from_risky": (0.40, "Деньги приходят со счетов-дропперов"),
}


def _uniq_in_window(events: list[tuple[datetime, int]], window: timedelta) -> int:
    events = sorted(events)
    best, j = 0, 0
    for i in range(len(events)):
        while events[i][0] - events[j][0] > window:
            j += 1
        best = max(best, len({s for _, s in events[j:i + 1]}))
    return best


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute(db: Session) -> dict:
    now = datetime.now()
    accounts = {a.id: a for a in db.query(Account).all()}
    transfers = db.query(Transfer).filter(Transfer.status == "completed", Transfer.kind == "transfer").all()
    confirmed_ids = {s.account_id for s in db.query(AntifraudSignal).all()}

    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    pairs = set()
    G = nx.DiGraph()
    G.add_nodes_from(accounts)
    for t in transfers:
        incoming[t.to_account_id].append(t)
        outgoing[t.from_account_id].append(t)
        pairs.add((t.from_account_id, t.to_account_id))
        w = G.get_edge_data(t.from_account_id, t.to_account_id, {}).get("weight", 0)
        G.add_edge(t.from_account_id, t.to_account_id, weight=w + t.amount)

    pr = nx.pagerank(G, weight="weight") if G.number_of_edges() else {}
    pr_sorted = sorted(pr.values())
    pr_pct = {k: (sum(1 for x in pr_sorted if x <= v) / len(pr_sorted)) for k, v in pr.items()} if pr else {}
    partition = community_louvain.best_partition(G.to_undirected(), random_state=42) if G.number_of_edges() else {}

    base: dict[int, float] = {}
    feats: dict[int, dict] = {}

    def bcc_features(aid: int) -> dict:
        inc, out = incoming[aid], outgoing[aid]
        a = accounts[aid]
        in_sum = sum(t.amount for t in inc)
        out_sum = sum(t.amount for t in out)
        senders = {t.from_account_id for t in inc}
        strangers = [t for t in inc if (aid, t.from_account_id) not in pairs]
        dwell = []
        in_times = sorted(t.created_at for t in inc)
        for t in out:
            prev = [x for x in in_times if x <= t.created_at]
            if prev:
                dwell.append((t.created_at - prev[-1]).total_seconds() / 60)
        med_dwell = median(dwell) if dwell else None
        # transit: share of incoming money that leaves within 24h of arriving
        out_sorted = sorted(out, key=lambda t: t.created_at)
        passed = 0.0
        for t in inc:
            window_out = sum(o.amount for o in out_sorted
                             if t.created_at <= o.created_at <= t.created_at + timedelta(hours=24))
            passed += min(t.amount, window_out)
        age_days = (now - a.opened_at).days
        under_call = [t for t in inc if (t.context or {}).get("call_active")]
        raw = {
            "uniq_senders_24h": _uniq_in_window([(t.created_at, t.from_account_id) for t in inc], timedelta(hours=24)),
            "uniq_senders_7d": _uniq_in_window([(t.created_at, t.from_account_id) for t in inc], timedelta(days=7)),
            "stranger_share": round(len(strangers) / len(inc), 2) if inc else 0,
            "median_dwell_min": round(med_dwell, 1) if med_dwell is not None else None,
            "transit_ratio": round(passed / in_sum, 2) if in_sum else 0,
            "account_age_days": age_days,
            "under_call_share": round(len(under_call) / len(inc), 2) if inc else 0,
            "complaints": int((a.flags or {}).get("complaints", 0)),
            "pagerank_pct": round(pr_pct.get(aid, 0), 2),
            "community": partition.get(aid),
            "in_sum": round(in_sum), "out_sum": round(out_sum), "in_count": len(inc), "out_count": len(out),
        }
        norm = {
            "senders": _clip(raw["uniq_senders_7d"] / 6),
            "stranger": raw["stranger_share"],
            "dwell": _clip(1 - math.log10(max(med_dwell, 10) / 10) / math.log10(144)) if med_dwell is not None else 0,
            "transit": _clip(raw["transit_ratio"]),
            "young": 1.0 if age_days < 30 else 0.5 if age_days < 90 else 0.0,
            "under_call": raw["under_call_share"],
            "pagerank": _clip((raw["pagerank_pct"] - 0.5) * 2),
        }
        gate = 1.0 if len(inc) >= 2 else 0.6 if inc else 0.0
        return {"raw": raw, "norm": norm, "gate": gate}

    for aid, a in accounts.items():
        if a.is_external:
            continue
        f = bcc_features(aid)
        contrib = {k: round(100 * w * f["norm"][k] * f["gate"], 1) for k, (w, _) in BCC_WEIGHTS.items()}
        score = sum(contrib.values())
        if a.kind in ("merchant", "employer"):
            score *= 0.4
            f["raw"]["note"] = "Юрлицо/ТОО: понижающий коэффициент"
        base[aid] = score
        feats[aid] = {**f["raw"], "contrib": contrib}

    for aid, a in accounts.items():  # externals use what BCC clients send them
        if not a.is_external:
            continue
        inc = incoming[aid]
        bcc_inc = [t for t in inc if not accounts[t.from_account_id].is_external]
        senders = {t.from_account_id for t in bcc_inc}
        amt = sum(t.amount for t in bcc_inc) or 1
        risky_amt = sum(t.amount for t in bcc_inc if base.get(t.from_account_id, 0) >= DROP_THRESHOLD)
        raw = {
            "bcc_senders": len(senders),
            "stranger_share": round(sum(1 for t in bcc_inc if (aid, t.from_account_id) not in pairs) / len(bcc_inc), 2)
            if bcc_inc else 0,
            "under_call_share": round(sum(1 for t in bcc_inc if (t.context or {}).get("call_active")) / len(bcc_inc), 2)
            if bcc_inc else 0,
            "from_risky_share": round(risky_amt / amt, 2),
            "complaints": int((a.flags or {}).get("complaints", 0)),
            "community": partition.get(aid),
            "in_sum": round(sum(t.amount for t in inc)), "in_count": len(inc),
        }
        norm = {"bcc_senders": _clip(len(senders) / 5), "stranger": raw["stranger_share"],
                "under_call": raw["under_call_share"], "from_risky": raw["from_risky_share"]}
        gate = 1.0 if raw["from_risky_share"] > 0.3 else _clip(len(senders) / 3)
        contrib = {k: round(100 * w * norm[k] * gate, 1) for k, (w, _) in EXT_WEIGHTS.items()}
        score = sum(contrib.values())
        if a.kind in ("merchant", "cash"):
            score *= 0.4
        base[aid] = score
        feats[aid] = {**raw, "contrib": contrib}

    # confirmed droppers: complaints, relative rejections, Antifraud-centre signals, analyst marks
    confirmed = set()
    for aid, a in accounts.items():
        fl = a.flags or {}
        if fl.get("complaints") or fl.get("confirmed_drop") or fl.get("antifraud") or aid in confirmed_ids:
            if a.kind != "cash":
                confirmed.add(aid)
    final = dict(base)
    for aid in confirmed:
        final[aid] = max(final[aid] + 40, 85)
    boosts = defaultdict(float)
    for src in confirmed:
        frontier, seen = {src}, {src}
        for step in range(1, PROPAGATION_STEPS + 1):
            nxt = set()
            for n in frontier:
                for m in G.successors(n):
                    if m not in seen:
                        seen.add(m)
                        nxt.add(m)
            for m in nxt:
                boosts[m] = max(boosts[m], PROPAGATION_BASE * PROPAGATION_DECAY ** (step - 1))
            frontier = nxt
    for aid, b in boosts.items():
        if accounts[aid].kind != "cash":
            final[aid] += b
            feats[aid]["propagated"] = round(b, 1)

    for aid, a in accounts.items():
        a.risk_score = round(min(final.get(aid, 0), 99), 1)
        f = feats.get(aid, {})
        f["confirmed"] = aid in confirmed
        f["reasons"] = explain(a, f)
        a.features = f
    db.commit()
    return metrics(db)


def explain(a: Account, f: dict) -> list[str]:
    weights = EXT_WEIGHTS if a.is_external else BCC_WEIGHTS
    top = sorted(f.get("contrib", {}).items(), key=lambda kv: -kv[1])
    out = [f"{weights[k][1]} (+{v:.0f})" for k, v in top if v >= 4][:4]
    fl = a.flags or {}
    if fl.get("complaints"):
        out.insert(0, "Есть жалобы клиентов")
    if fl.get("confirmed_drop"):
        out.insert(0, "Перевод на счёт отклонён доверенным лицом")
    if fl.get("antifraud"):
        out.insert(0, "Сигнал Национального Антифрод-центра")
    if f.get("propagated"):
        out.append(f"Связан с подтверждённым дроппером по цепочке (+{f['propagated']:.0f})")
    return out


def metrics(db: Session) -> dict:
    accs = [a for a in db.query(Account).all() if a.kind != "cash"]
    tp = sum(1 for a in accs if a.risk_score >= DROP_THRESHOLD and (a.flags or {}).get("gt_drop"))
    fp = sum(1 for a in accs if a.risk_score >= DROP_THRESHOLD and not (a.flags or {}).get("gt_drop"))
    fn = sum(1 for a in accs if a.risk_score < DROP_THRESHOLD and (a.flags or {}).get("gt_drop"))
    return {
        "droppers_found": tp + fp,
        "precision": round(tp / (tp + fp), 2) if tp + fp else 0,
        "recall": round(tp / (tp + fn), 2) if tp + fn else 0,
        "tp": tp, "fp": fp, "fn": fn,
    }
