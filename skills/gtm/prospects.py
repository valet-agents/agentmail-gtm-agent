"""
CSV-backed prospect tracker.

Vendored from agentmail-to/agentmail-gtm-agent (MIT). The upstream's
`load_all`, `update_prospect`, `find_by_thread`, `queued_prospects`,
`followups_due`, and `log_action` helpers are preserved. The Valet
port adds:

  - A `--csv <path>` flag so the working CSV path is configurable
    (the upstream hard-codes `prospects.csv` next to the script).
  - An argparse `__main__` block exposing `queued`, `due`, `update`,
    and `log` subcommands. The Valet agent shells out to this script
    instead of importing it, so the CLI surface IS the integration.
  - The COLUMNS list matches the slot schema documented in
    `valet.yaml` (email, first_name, company, hook, status,
    sent_at, followup_at, replied_at, classification, thread_id).

prospects.csv columns (header row required):
  email, first_name, company, hook, status, sent_at,
  followup_at, replied_at, classification, thread_id

The agent picks up rows where `status` is empty or 'queued' on
its next heartbeat. Update via `update` subcommand. Append actions
to gtm_log.csv via the `log` subcommand.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PROSPECTS_FILE = Path("prospects.csv")
DEFAULT_LOG_FILE = Path("gtm_log.csv")

COLUMNS = [
    "email", "first_name", "company", "hook",
    "status", "sent_at", "followup_at",
    "replied_at", "classification", "thread_id",
]

LOG_COLUMNS = [
    "timestamp_utc", "action", "prospect_email", "classification",
    "thread_id", "note",
]


# --- prospects --------------------------------------------------------------


def load_all(csv_path: Path = DEFAULT_PROSPECTS_FILE) -> list[dict]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        return [_normalize(r) for r in csv.DictReader(f)]


def _normalize(row: dict) -> dict:
    """Ensure all expected columns exist, defaulting to empty string."""
    return {col: (row.get(col) or "").strip() for col in COLUMNS}


def save_all(rows: list[dict], csv_path: Path = DEFAULT_PROSPECTS_FILE) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLUMNS})


def update_prospect(email: str, csv_path: Path = DEFAULT_PROSPECTS_FILE,
                    **fields) -> dict | None:
    rows = load_all(csv_path)
    target = None
    for r in rows:
        if r["email"].lower() == email.lower():
            r.update(fields)
            target = r
            break
    if target:
        save_all(rows, csv_path)
    return target


def find_by_thread(thread_id: str,
                   csv_path: Path = DEFAULT_PROSPECTS_FILE) -> dict | None:
    for r in load_all(csv_path):
        if r["thread_id"] == thread_id:
            return r
    return None


def queued_prospects(csv_path: Path = DEFAULT_PROSPECTS_FILE) -> list[dict]:
    return [r for r in load_all(csv_path) if r["status"] in ("", "queued")]


def followups_due(after_hours: int,
                  csv_path: Path = DEFAULT_PROSPECTS_FILE) -> list[dict]:
    """Prospects who got a first touch >N hours ago and haven't been followed up
    or replied. Returns rows where status == 'sent'."""
    cutoff = datetime.now(timezone.utc).timestamp() - after_hours * 3600
    out = []
    for r in load_all(csv_path):
        if r["status"] != "sent":
            continue
        if not r["sent_at"]:
            continue
        try:
            ts = datetime.fromisoformat(r["sent_at"]).timestamp()
        except Exception:
            continue
        if ts <= cutoff:
            out.append(r)
    return out


# --- log --------------------------------------------------------------------


def _ensure_log_header(log_path: Path = DEFAULT_LOG_FILE) -> None:
    if not log_path.exists() or log_path.stat().st_size == 0:
        with log_path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(LOG_COLUMNS)


def log_action(*, action: str, prospect_email: str, classification: str = "",
               thread_id: str = "", note: str = "",
               log_path: Path = DEFAULT_LOG_FILE) -> None:
    _ensure_log_header(log_path)
    row = [
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        action,
        prospect_email,
        classification,
        thread_id,
        note.replace("\n", " ")[:500],
    ]
    with log_path.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)


# --- CLI --------------------------------------------------------------------


def _cli() -> int:
    p = argparse.ArgumentParser(
        prog="prospects",
        description="CSV-backed prospect tracker for the AgentMail GTM agent.",
    )
    p.add_argument("--csv", default=str(DEFAULT_PROSPECTS_FILE),
                   help="Path to prospects.csv (default: ./prospects.csv).")
    p.add_argument("--log-csv", default=str(DEFAULT_LOG_FILE),
                   help="Path to gtm_log.csv (default: ./gtm_log.csv).")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("queued", help="List prospects with status empty or 'queued'.")

    due = sub.add_parser("due", help="List prospects whose first-touch is past --hours.")
    due.add_argument("--hours", type=int, default=96)

    upd = sub.add_parser("update", help="Update one prospect row by email.")
    upd.add_argument("--email", required=True)
    upd.add_argument("--field", action="append", default=[],
                     help="key=value (repeatable).")

    log = sub.add_parser("log", help="Append a row to gtm_log.csv.")
    log.add_argument("--action", required=True)
    log.add_argument("--email", required=True)
    log.add_argument("--classification", default="")
    log.add_argument("--thread", default="")
    log.add_argument("--note", default="")

    args = p.parse_args()
    csv_path = Path(args.csv)
    log_path = Path(args.log_csv)

    if args.cmd == "queued":
        rows = queued_prospects(csv_path)
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "due":
        rows = followups_due(args.hours, csv_path)
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "update":
        fields: dict[str, str] = {}
        for kv in args.field:
            if "=" not in kv:
                print(f"bad --field {kv!r}, expected key=value", file=sys.stderr)
                return 2
            k, v = kv.split("=", 1)
            fields[k.strip()] = v.strip()
        result = update_prospect(args.email, csv_path, **fields)
        if result is None:
            print(f"no prospect with email {args.email!r}", file=sys.stderr)
            return 1
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.cmd == "log":
        log_action(
            action=args.action,
            prospect_email=args.email,
            classification=args.classification,
            thread_id=args.thread,
            note=args.note,
            log_path=log_path,
        )
        return 0

    p.error(f"unknown command {args.cmd!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli())
