#!/usr/bin/env python3
# harness-comms: generated file. Re-run `harness_comms.py sync` to refresh it; delete this line to own it.
"""Deterministic comms/ archiver: no model calls, no judgement calls.

Reads comms/config.json for the parties and the gated party (the one that must acknowledge a message
before it may be archived, usually the claude.ai chat).

  --as <party>  sweep only your own inbox, comms/to_<party>/, on `status: done`. This is what a party
                runs at the end of a check-in, so it never archives a message out of someone else's
                inbox before that party has read it.
  --gated       also sweep the gated party's inbox, but only messages with `status: done` AND
                `acknowledged: true` (only the gated party sets that, after reading). Safe on every
                run. `--chat` is accepted as an alias.
  (no --as)     sweep every non-gated inbox on `status: done` (older behaviour, kept for compatibility).
  --dry-run     print what would move; change nothing.

Each archived file moves to archive/<YYYY-MM>/ (month from the filename's date prefix) and one line is
appended to archive/INDEX.md. Never overwrites an existing archive file. Run from anywhere; paths
resolve from this file's own location.

Usage: python3 comms/archive_sweep.py --as <party> [--gated] [--dry-run]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

COMMS = Path(__file__).resolve().parent
HEADER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$", re.MULTILINE)
MONTH_RE = re.compile(r"^(\d{4}-\d{2})-\d{2}_\d{4}_")


def load_config():
    path = COMMS / "config.json"
    if not path.is_file():
        sys.exit(f"Missing {path}. Run harness_comms.py init first.")
    cfg = json.loads(path.read_text(encoding="utf-8"))
    parties = cfg.get("parties") or []
    gated = cfg.get("gated_party")
    if gated and gated not in parties:
        sys.exit(f"gated_party {gated!r} is not in parties {parties!r}.")
    return parties, gated


def parse(path):
    m = HEADER_RE.match(path.read_text(encoding="utf-8"))
    if not m:
        return None
    header, body = m.group(1), m.group(2)
    fields = {k: v.split("#", 1)[0].strip() for k, v in FIELD_RE.findall(header)}
    summary = ""
    for heading in ("## Answer", "## Ask", "## Note"):
        i = body.find(heading)
        if i != -1:
            after = body[i + len(heading):].strip().splitlines()
            summary = next((line.strip() for line in after if line.strip() and not line.startswith("#")), "")
            break
    return fields, summary[:140].replace("|", "/")


def main():
    ap = argparse.ArgumentParser(description="Archive finished comms/ messages.")
    ap.add_argument("--as", dest="party", help="your own party name; sweep only comms/to_<party>/")
    ap.add_argument("--gated", "--chat", action="store_true",
                    help="also sweep the gated inbox (status: done AND acknowledged: true)")
    ap.add_argument("--dry-run", action="store_true", help="show what would move, change nothing")
    args = ap.parse_args()

    parties, gated = load_config()
    if args.party:
        if args.party not in parties:
            sys.exit(f"Unknown party {args.party!r}; config.json lists {parties!r}.")
        inboxes = [] if args.party == gated else [args.party]
    else:
        inboxes = [p for p in parties if p != gated]
    if args.gated and gated:
        inboxes.append(gated)

    archive = COMMS / "archive"
    moved, skipped = [], []
    for party in inboxes:
        d = COMMS / f"to_{party}"
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            parsed = parse(f)
            if not parsed:
                continue
            fields, summary = parsed
            if fields.get("status", "") != "done":
                continue
            if party == gated and fields.get("acknowledged", "").lower() != "true":
                continue
            m = MONTH_RE.match(f.name)
            dest = archive / (m.group(1) if m else "unsorted") / f.name
            if dest.exists():
                skipped.append(f)
                continue
            moved.append((f, dest, fields, summary))

    for f in skipped:
        print(f"skip (already archived under that name): {f.relative_to(COMMS)}", file=sys.stderr)
    if not moved:
        print("Nothing to archive.")
        return 0

    for src, dest, _, _ in moved:
        print(f"{'[dry-run] ' if args.dry_run else ''}{src.relative_to(COMMS)} -> {dest.relative_to(COMMS)}")
        if not args.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dest)

    if not args.dry_run:
        index_path = archive / "INDEX.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as idx:
            for _, dest, fields, summary in moved:
                idx.write(
                    f"- {fields.get('id', dest.stem)} | {fields.get('from', '?')} -> "
                    f"{fields.get('to', '?')} | {summary} | `{dest.relative_to(COMMS).as_posix()}`\n"
                )
        print(f"Archived {len(moved)} file(s); archive/INDEX.md updated "
              f"({datetime.now().isoformat(timespec='seconds')}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
