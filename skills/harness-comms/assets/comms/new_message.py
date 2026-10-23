#!/usr/bin/env python3
# harness-comms: generated file. Re-run `harness_comms.py sync` to refresh it; delete this line to own it.
"""Create one correctly named, correctly headed comms/ message and print its path.

The filename timestamp comes from the real clock in the project timezone (comms/config.json), so no
party ever has to guess or round one. `acknowledged: false` is added when the recipient is the gated
party. The body gets the protocol's section headings, left for you to fill in.

Usage:
  python3 comms/new_message.py --from code --to chat --type answer --re <request-id> --slug labels-done
  python3 comms/new_message.py --from chat --to code --type request --slug rerun-eval

--status defaults to `open` for a request and `done` for an answer or note.
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

COMMS = Path(__file__).resolve().parent
SECTIONS = {
    "request": ["## Ask", "## Context", "## Expected output"],
    "answer": ["## Answer", "## Context"],
    "note": ["## Answer", "## Context"],
}


def now_in(tz_name):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name))
    except Exception:  # no tz database (e.g. Windows without tzdata): fall back to the machine clock
        print(f"warning: timezone {tz_name!r} unavailable; using this machine's local clock",
              file=sys.stderr)
        return datetime.now().astimezone()


def main():
    cfg = json.loads((COMMS / "config.json").read_text(encoding="utf-8"))
    parties = cfg.get("parties") or []
    gated = cfg.get("gated_party")
    tz_name = (cfg.get("harness-comms") or {}).get("timezone", "UTC")

    ap = argparse.ArgumentParser(description="Create a comms/ message file.")
    ap.add_argument("--from", dest="sender", required=True, choices=parties)
    ap.add_argument("--to", dest="recipient", required=True, choices=parties)
    ap.add_argument("--type", dest="kind", required=True, choices=sorted(SECTIONS))
    ap.add_argument("--re", dest="re_id", help="id of the message this answers, or none")
    ap.add_argument("--slug", required=True, help="a few words, lowercase-hyphenated")
    ap.add_argument("--status", choices=["open", "done"])
    args = ap.parse_args()

    slug = re.sub(r"[^a-z0-9]+", "-", args.slug.lower()).strip("-")
    if not slug:
        sys.exit("--slug must contain letters or digits.")
    if args.re_id is None:
        if args.kind != "request":
            print("warning: an answer or note usually sets --re to the request's id", file=sys.stderr)
        args.re_id = "none"
    status = args.status or ("open" if args.kind == "request" else "done")

    stamp = now_in(tz_name).strftime("%Y-%m-%d_%H%M")
    msg_id = f"{stamp}_{args.sender}_{slug}"
    path = COMMS / f"to_{args.recipient}" / f"{msg_id}.md"
    if path.exists():
        sys.exit(f"{path} already exists; pick a different --slug.")

    header = [
        "---",
        f"id: {msg_id}",
        f"from: {args.sender}",
        f"to: {args.recipient}",
        f"re: {args.re_id}",
        f"type: {args.kind}",
        f"status: {status}",
    ]
    if args.recipient == gated:
        header.append("acknowledged: false")
    header.append("---")
    body = "\n\n\n".join(SECTIONS[args.kind])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(header) + "\n\n" + body + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
