#!/usr/bin/env python3
"""Regenerate demo/fixtures/d1_*.json (deterministic; fake data, no real voters).

    python3 demo/fixtures/gen_d1_fixtures.py

Output is shaped exactly like `wrangler d1 execute --remote --json`: a list with one
element per statement, rows under ["results"].
"""
from __future__ import annotations

import base64
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
NS = uuid.UUID("5e1f0a77-7c64-4a3b-9d0e-3b2f6c1a9e10")
rng = random.Random(20261013)

GROUP_ID = "7f3a9c1e-5b24-4d86-9a0e-c1d2e3f4a5b6"
GROUP_CODE = GROUP_ID.replace("-", "")[:10].upper()  # same rule as migration 0004
BASE = datetime(2026, 10, 13, 16, 41, 7)  # 10:41 CDMX, group created before the talk

QUESTIONS = [
    # (id, code, question, options)
    ("0b8c4e52-91d3-4a67-8f10-2c5d7a9e3b41", "K7M2QX", "¿Cuál describe mejor tu rol?",
     ["Negocio", "Ingeniería", "Datos y analítica", "Liderazgo", "Otro"]),
    ("5d1e7a90-3c28-4f5b-b6a4-8e0f12d9c7a3", "P4TH9R", "En los últimos 7 días, ¿usaste IA para trabajar con datos?",
     ["Sí", "No"]),
    ("a92f6d13-7e40-4c8a-95b1-4d3e0c8f6a27", "W5N8ZB", "¿Le darías a un agente permiso de actuar en producción?",
     ["Sí", "Sí, con aprobación humana", "No"]),
]
# P1 and P2 are created within the same second on purpose: the order must fall back to id.
POLL_CREATED = [BASE + timedelta(seconds=6), BASE + timedelta(seconds=6), BASE + timedelta(seconds=7)]
OPENED = BASE + timedelta(minutes=19, seconds=30)  # opened on stage at ~11:00


def ts(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M:%S")


def wrap(rows: list[dict]) -> list[dict]:
    return [{"results": rows, "success": True,
             "meta": {"served_by": "v3-prod", "duration": 0.31, "changes": 0, "rows_read": len(rows),
                      "rows_written": 0, "size_after": 163840, "changed_db": False}}]


def vhash(n: int) -> str:  # fake 43-char base64url, like sha256 digests without padding
    return base64.urlsafe_b64encode(hashlib.sha256(f"fake-browser-{n}".encode()).digest()).decode().rstrip("=")


group = [{"id": GROUP_ID, "code": GROUP_CODE, "title": "Snowflake World Tour CDMX · Agentes en producción",
          "created_at": ts(BASE)}]
polls, options = [], []
opt_ids: dict[str, dict[str, str]] = {}
for i, (pid, code, question, labels) in enumerate(QUESTIONS):
    polls.append({"id": pid, "group_id": GROUP_ID, "code": code, "question": question, "status": "open",
                  "created_at": ts(POLL_CREATED[i]), "opened_at": ts(OPENED), "closed_at": None})
    opt_ids[pid] = {}
    for pos, label in enumerate(labels):
        oid = str(uuid.uuid5(NS, f"{pid}:{label}"))
        opt_ids[pid][label] = oid
        options.append({"id": oid, "poll_id": pid, "label": label, "position": pos})

# ---- browsers: (role weight) and P3 tendency per role; some skip questions ----
ROLES = ["Negocio"] * 8 + ["Ingeniería"] * 11 + ["Datos y analítica"] * 13 + ["Liderazgo"] * 5 + ["Otro"] * 3
P3 = {  # P(Sí), P(Sí con aprobación), P(No)
    "Negocio": (0.20, 0.45, 0.35), "Ingeniería": (0.10, 0.45, 0.45),
    "Datos y analítica": (0.30, 0.45, 0.25), "Liderazgo": (0.20, 0.60, 0.20), "Otro": (0.33, 0.33, 0.34),
}
P3_LABELS = ["Sí", "Sí, con aprobación humana", "No"]
rng.shuffle(ROLES)
skip_p1 = {7, 19, 31}          # browsers that never answered P1
skip_p3 = {2, 5, 11, 23, 29, 36}  # ...never answered P3
skip_p2 = {13, 27}
only_p1 = {38}                 # joined late, answered just P1
votes = []
t0 = BASE + timedelta(minutes=20, seconds=10)  # first phones at ~11:01
for n, role in enumerate(ROLES):
    start = t0 + timedelta(seconds=n * rng.uniform(8, 14) + rng.uniform(0, 4))
    answers = {}
    if n not in skip_p1:
        answers[0] = role
    if n not in skip_p2 and n not in only_p1:
        answers[1] = rng.choices(["Sí", "No"], weights=[0.72, 0.28])[0]
    if n not in skip_p3 and n not in only_p1:
        answers[2] = rng.choices(P3_LABELS, weights=P3[role])[0]
    t = start
    for qi in sorted(answers):
        pid = QUESTIONS[qi][0]
        votes.append({"id": str(uuid.uuid5(NS, f"vote:{n}:{pid}")), "poll_id": pid,
                      "option_id": opt_ids[pid][answers[qi]], "voter_hash": vhash(n), "created_at": ts(t)})
        t += timedelta(seconds=rng.randint(4, 15))
votes.sort(key=lambda v: (v["created_at"], v["id"]))

for name, rows in [("d1_group", group), ("d1_polls", polls), ("d1_options", options), ("d1_votes", votes)]:
    (OUT / f"{name}.json").write_text(json.dumps(wrap(rows), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"group {GROUP_CODE} · {len(polls)} polls · {len(options)} options · {len(votes)} votes · "
      f"{len(ROLES)} browsers")
