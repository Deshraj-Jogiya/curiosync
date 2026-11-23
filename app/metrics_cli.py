"""Record how posts did. Run from the CurioSync folder:

    python -m app.metrics_cli import <export.xlsx|csv> [--measured YYYY-MM-DD]   LinkedIn's analytics export (Analytics > Export)
    python -m app.metrics_cli add <post date> <impressions> [--reactions N] [--comments N] [--reposts N] [--measured YYYY-MM-DD]
    python -m app.metrics_cli due                                                  posts 7-10 days old still to be read
    python -m app.metrics_cli outcome --profile-viewers-90d N --search-appearances-week N --followers N --post-impressions-7d N
                                      [--recruiter-messages-week N] [--interview-invites-week N]   weekly dashboard snapshot
    python -m app.metrics_cli report                                               each post against the account's recent median
"""

import argparse
import json
from datetime import date

from app.services import post_metrics as pm


def _history() -> list[dict]:
    with open("data/post_history.json", encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="metrics_cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    imp = sub.add_parser("import")
    imp.add_argument("path")
    imp.add_argument("--measured", default=str(date.today()))
    add = sub.add_parser("add")
    add.add_argument("post_date")
    add.add_argument("impressions", type=int)
    for k in ("reactions", "comments", "reposts"):
        add.add_argument(f"--{k}", type=int)
    add.add_argument("--measured", default=str(date.today()))
    sub.add_parser("due")
    oc = sub.add_parser("outcome")
    for k in pm.OUTCOME_FIELDS:
        oc.add_argument("--" + k.replace("_", "-"), type=int)
    oc.add_argument("--measured", default=str(date.today()))
    sub.add_parser("report")
    a = p.parse_args(argv)

    history, rows = _history(), pm.load()
    if a.cmd == "import":
        n, notes = pm.import_export(a.path, history, rows, date.fromisoformat(a.measured))
        pm.save(rows)
        print(f"recorded {n} posts")
        for note in notes:
            print(" ", note)
        return 0 if n else 1
    if a.cmd == "add":
        post = pm.match_post(history, date.fromisoformat(a.post_date))
        if post is None:
            print(f"no post on {a.post_date} in post_history.json")
            return 1
        row = pm.record(rows, post, date.fromisoformat(a.measured), a.impressions, a.reactions, a.comments, a.reposts)
        pm.save(rows)
        print(f"recorded {row}")
        return 0
    if a.cmd == "outcome":
        out = pm.load(pm.OUTCOMES_PATH)
        row = pm.record_outcome(out, date.fromisoformat(a.measured), **{k: getattr(a, k) for k in pm.OUTCOME_FIELDS})
        pm.save(out, pm.OUTCOMES_PATH)
        print(f"recorded {row}")
        return 0
    if a.cmd == "due":
        for h in pm.due_for_measurement(rows, history, date.today()):
            print(h["date"], h.get("subject"))
        return 0
    for r in pm.relative_reach(rows, history):
        print(f"{r['date']}  {str(r['seven_day'] or '-'):>5}  x{r['ratio'] or '-':<5} {r['media'] or '-':<9} {r['subject']}")
    from app.services.post_factors import balance

    for note in balance(history):
        print("not comparable yet:", note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
