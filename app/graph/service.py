"""Graph views for the analyst UI (vis-network friendly)."""
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.graph.scoring import DROP_THRESHOLD
from app.models import Account, Client, Transfer

EXPAND_MIN_RISK = 40


def _edges(db: Session) -> dict[tuple[int, int], dict]:
    agg: dict[tuple[int, int], dict] = {}
    for t in db.query(Transfer).filter(Transfer.status.in_(["completed", "rejected", "pending_relative", "cooling",
                                                            "blocked"]), Transfer.kind == "transfer"):
        e = agg.setdefault((t.from_account_id, t.to_account_id), {"count": 0, "amount": 0.0, "status": "completed"})
        e["count"] += 1
        e["amount"] += t.amount
        if t.status != "completed":
            e["status"] = t.status
    return agg


def node_view(a: Account, client_names: dict[int, str]) -> dict:
    fl = a.flags or {}
    return {
        "id": a.id, "label": f"{a.bank} {a.card_mask}" if a.is_external else (a.owner_name.split()[0] + f" {a.card_mask}"),
        "owner": a.owner_name, "bank": a.bank, "card": a.card_mask, "external": a.is_external, "kind": a.kind,
        "risk": a.risk_score, "community": (a.features or {}).get("community"),
        "client": client_names.get(a.client_id) if a.client_id else None,
        "confirmed": bool((a.features or {}).get("confirmed")), "frozen": bool(fl.get("frozen")),
        "antifraud": bool(fl.get("antifraud")), "victim": bool(fl.get("gt_victim")),
        "gt_drop": bool(fl.get("gt_drop")), "decoy": fl.get("decoy"),
    }


def graph_view(db: Session, min_risk: float = 40) -> dict:
    accounts = {a.id: a for a in db.query(Account).all()}
    names = {c.id: c.name for c in db.query(Client).all()}
    edges = _edges(db)
    core = {aid for aid, a in accounts.items() if a.risk_score >= min_risk}
    # live operations the shield stopped are always shown (e.g. Saule -> Kaspi 4417)
    flagged = db.query(Transfer).filter(Transfer.synthetic.is_(False), Transfer.status != "completed",
                                      Transfer.kind == "transfer").all()
    core |= {t.to_account_id for t in flagged}
    keep_edges = {k: v for k, v in edges.items()
                  if (k[0] in core or k[1] in core) and (accounts[k[0]].risk_score >= EXPAND_MIN_RISK
                                                         or accounts[k[1]].risk_score >= EXPAND_MIN_RISK
                                                         or v["status"] != "completed" or min_risk == 0)}
    if min_risk > 0:  # don't drag every merchant's customer base in
        keep_edges = {k: v for k, v in keep_edges.items()
                      if accounts[k[0]].kind not in ("merchant", "employer") and accounts[k[1]].kind != "employer"}
    ids = core | {a for k in keep_edges for a in k}
    return {
        "nodes": [node_view(accounts[i], names) for i in ids],
        "edges": [{"id": f"{a}-{b}", "from": a, "to": b, **v} for (a, b), v in keep_edges.items()],
    }


def chain(db: Session, start: int, hops: int = 3) -> dict:
    accounts = {a.id: a for a in db.query(Account).all()}
    edges = _edges(db)
    out_adj, in_adj = defaultdict(set), defaultdict(set)
    for a, b in edges:
        out_adj[a].add(b)
        in_adj[b].add(a)
    nodes, used = {start}, set()
    for adj, forward in ((out_adj, True), (in_adj, False)):
        q, seen = deque([(start, 0)]), {start}
        while q:
            n, d = q.popleft()
            if d >= hops or (n != start and accounts[n].risk_score < EXPAND_MIN_RISK):
                continue
            for m in adj[n]:
                if accounts[m].kind in ("merchant", "employer"):
                    continue
                used.add(f"{n}-{m}" if forward else f"{m}-{n}")
                nodes.add(m)
                if m not in seen:
                    seen.add(m)
                    q.append((m, d + 1))
    return {"start": start, "nodes": sorted(nodes), "edges": sorted(used)}


def account_detail(db: Session, aid: int) -> dict:
    a = db.get(Account, aid)
    names = {c.id: c.name for c in db.query(Client).all()}
    inc = db.query(Transfer).filter_by(to_account_id=aid).order_by(Transfer.created_at.desc()).limit(8).all()
    out = db.query(Transfer).filter_by(from_account_id=aid).order_by(Transfer.created_at.desc()).limit(8).all()

    def row(t, other):
        o = db.get(Account, other)
        return {"id": t.id, "amount": t.amount, "at": t.created_at, "status": t.status,
                "other": f"{o.bank} {o.card_mask}", "other_name": o.owner_name,
                "call": bool((t.context or {}).get("call_active"))}
    return {**node_view(a, names), "features": a.features, "flags": a.flags,
            "is_dropper": a.risk_score >= DROP_THRESHOLD,
            "incoming": [row(t, t.from_account_id) for t in inc], "outgoing": [row(t, t.to_account_id) for t in out],
            "chain": chain(db, aid)}
