#!/usr/bin/env python3
"""harness-comms: scaffold, extend and audit a file-based comms/ channel between AI harnesses.

Subcommands
  init        write comms/config.json for a new set of parties, then sync
  add-party   add one party to an existing comms/ setup, then sync
  sync        (re)generate every derived file from comms/config.json
  validate    check comms/ structure and every message header
  status      summarise open, unacknowledged and sweep-ready messages per inbox

Python 3.9+ standard library only. Every subcommand prints a JSON report to stdout (and writes it to
--output if given). init, add-party and sync stop with exit code 2, writing nothing, if they would
change a file this tool did not generate; rerun with --on-conflict skip|overwrite once the user agrees.
"""
import argparse
import io
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets" / "comms"

MARK = "harness-comms: generated file"
MD_MARK = f"<!-- {MARK}. Edit comms/config.json and run sync to change it; delete this line to own it. -->"
BLOCK_START = "<!-- harness-comms:start -->"
BLOCK_END = "<!-- harness-comms:end -->"
CHAT_DIR = "comms/_chat"

HEADER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.DOTALL)
FIELD_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$", re.MULTILINE)
FILENAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{4})_([a-z0-9-]+?)_([a-z0-9][a-z0-9.-]*)\.md$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Where each harness reads project skills and instructions, and what it is good at by default.
HARNESSES = {
    "claude-ai": {
        "title": "Claude chat (claude.ai)",
        "skills": None,
        "instructions": None,
        "reach": "through its link to this computer (Claude Desktop filesystem access or the claude.ai device link)",
        "good_for": "discussing results with the human; planning what to ask next; reading reports",
        "not_for": "running code or long jobs; moving or archiving files",
    },
    "claude-code": {
        "title": "Claude Code",
        "skills": ".claude/skills",
        "instructions": "CLAUDE.md",
        "invoke": "/check-comms",
        "reach": "directly, running in this folder",
        "good_for": "code changes and runs; debugging; merging and verifying results from other parties",
        "not_for": "long bulk reading a cheaper harness could do",
    },
    "antigravity": {
        "title": "Antigravity",
        "skills": ".agents/skills",
        "instructions": "AGENTS.md",
        "reach": "directly, as its workspace",
        "good_for": "bulk reading; web and literature search; filling a fixed table or schema; browser and UI work",
        "not_for": "changing files another party owns; unverified merges into the main pipeline",
    },
    "codex": {
        "title": "Codex",
        "skills": ".agents/skills",
        "instructions": "AGENTS.md",
        "reach": "directly, running in this folder",
        "good_for": "scoped implementation, refactoring and test writing",
        "not_for": "browser work; long-context literature synthesis",
    },
    "gemini-cli": {
        "title": "Gemini CLI",
        "skills": ".gemini/skills",
        "instructions": "GEMINI.md",
        "reach": "directly, running in this folder",
        "good_for": "large-context file analysis, search and structured extraction",
        "not_for": "changing files another party owns without verification",
    },
    "opencode": {
        "title": "OpenCode",
        "skills": ".opencode/skills",
        "instructions": "AGENTS.md",
        "reach": "directly, running in this folder",
        "good_for": "scoped code work with whichever model it is configured for",
        "not_for": "work that needs a specific other harness's tools",
    },
    "generic": {
        "title": "an agent harness",
        "skills": ".agents/skills",
        "instructions": "AGENTS.md",
        "reach": "directly, running in this folder",
        "good_for": "tasks the human routes to it",
        "not_for": "",
    },
}
NAME_HINTS = {
    "chat": "claude-ai", "claude-ai": "claude-ai", "claude-chat": "claude-ai",
    "code": "claude-code", "claude": "claude-code", "claude-code": "claude-code",
    "antigravity": "antigravity", "agy": "antigravity",
    "codex": "codex", "gemini": "gemini-cli", "gemini-cli": "gemini-cli", "opencode": "opencode",
}
DEFAULT_RULES = [
    "Keep messages short: tables, evidence, file pointers and questions, not pasted file contents.",
    "A message is a claim, not proof. Check the cited file before acting on a number in it.",
    "Never edit or delete another party's message file beyond the two edits this protocol allows.",
]


# ---------------------------------------------------------------------------------------------- config

def detect_timezone():
    tz = os.environ.get("TZ", "").lstrip(":")
    if "/" in tz:
        return tz
    try:
        name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
        if name:
            return name
    except OSError:
        pass
    target = os.path.realpath("/etc/localtime")
    if "zoneinfo/" in target:
        return target.split("zoneinfo/", 1)[1]
    return "UTC"


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "project"


def parse_parties(spec):
    """'chat,code,antigravity' or 'chat:claude-ai:gated,ui:antigravity' -> ([(name, harness)], gated)."""
    parties, gated = [], None
    for token in filter(None, (t.strip() for t in spec.split(","))):
        name, *opts = [x.strip().lower() for x in token.split(":")]
        if not NAME_RE.match(name):
            raise ValueError(f"party name {name!r}: use lowercase letters, digits and '-'")
        harness = NAME_HINTS.get(name, "generic")
        for opt in opts:
            if opt in HARNESSES:
                harness = opt
            elif opt in ("gated", "remote"):
                gated = name
            elif opt != "local":
                raise ValueError(f"unknown option {opt!r} for party {name!r}; "
                                 f"expected one of {sorted(HARNESSES)}, 'gated' or 'local'")
        if name in (p for p, _ in parties):
            raise ValueError(f"party {name!r} listed twice")
        parties.append((name, harness))
    if not parties:
        raise ValueError("no parties given")
    return parties, gated


def default_gated(parties):
    return next((name for name, harness in parties if harness == "claude-ai"), None)


def normalise(cfg, root):
    hc = cfg.setdefault("harness-comms", {})
    hc.setdefault("project", root.name)
    hc.setdefault("timezone", detect_timezone())
    harnesses = hc.setdefault("harnesses", {})
    for p in cfg["parties"]:
        harnesses.setdefault(p, NAME_HINTS.get(p, "generic"))
    hc.setdefault("routing", {})
    hc.setdefault("hard_rules", list(DEFAULT_RULES))
    hc.setdefault("ownership", [])
    return cfg


def discover_legacy(root):
    """Build a config from a comms/ folder that predates config.json (to_* folders only)."""
    comms = root / "comms"
    parties = sorted(d.name[3:] for d in comms.glob("to_*") if d.is_dir())
    gated = "chat" if "chat" in parties else None
    sweep = comms / "archive_sweep.py"
    if sweep.is_file():
        m = re.search(r"REMOTE_INBOXES\s*=\s*\[(.*?)\]", sweep.read_text(encoding="utf-8"))
        if m:
            names = re.findall(r"to_([a-z0-9-]+)", m.group(1))
            gated = names[0] if names else gated
    cfg = {"parties": parties}
    if gated:
        cfg["gated_party"] = gated
    return cfg


def load_config(root, allow_legacy=False):
    path = root / "comms" / "config.json"
    if path.is_file():
        return normalise(json.loads(path.read_text(encoding="utf-8")), root), False
    if allow_legacy and (root / "comms").is_dir():
        return normalise(discover_legacy(root), root), True
    raise SystemExit(f"{path} not found; run `init` first.")


def check_config(cfg):
    parties = cfg.get("parties") or []
    if not parties:
        raise SystemExit("config.json lists no parties.")
    gated = cfg.get("gated_party")
    if gated and gated not in parties:
        raise SystemExit(f"gated_party {gated!r} is not one of the parties {parties!r}.")
    for p in parties:
        h = cfg["harness-comms"]["harnesses"][p]
        if h not in HARNESSES:
            raise SystemExit(f"party {p!r} has unknown harness {h!r}; known: {sorted(HARNESSES)}")


# ------------------------------------------------------------------------------------------- rendering

def info(cfg, party):
    hc = cfg["harness-comms"]
    harness = hc["harnesses"][party]
    base = HARNESSES[harness]
    return {**base, **hc["routing"].get(party, {}), "harness": harness, "name": party}


def local_parties(cfg):
    return [p for p in cfg["parties"] if info(cfg, p)["harness"] != "claude-ai"]


def skill_name(cfg, party):
    """check-comms, or check-comms-<party> when another party shares the same skills folder."""
    folder = info(cfg, party)["skills"]
    sharers = [p for p in local_parties(cfg) if info(cfg, p)["skills"] == folder]
    return "check-comms" if len(sharers) == 1 else f"check-comms-{party}"


def chat_skill_name(cfg, party):
    base = f"check-comms-{slugify(cfg['harness-comms']['project'])}"
    return (base if party == "chat" else f"{base}-{party}")[:64].rstrip("-")


def py():
    return "python3"


def render_readme(cfg):
    hc = cfg["harness-comms"]
    parties = cfg["parties"]
    gated = cfg.get("gated_party")
    rows = "\n".join(f"| **{p}** | {info(cfg, p)['title']} | {info(cfg, p)['reach']} |" for p in parties)
    routing = "\n".join(
        f"| **{p}** | {info(cfg, p)['good_for']} | {info(cfg, p)['not_for']} |" for p in parties)
    folders = "\n".join(f"| `to_{p}/` | messages for {p} |" for p in parties)
    ownership = ""
    if hc["ownership"]:
        lines = "\n".join(f"| `{r['path']}` | {r['owner']} |" for r in hc["ownership"])
        ownership = f"\n## Who owns which files\n\n| Path | Owner |\n|---|---|\n{lines}\n"
    rules = "\n".join(f"- {r}" for r in hc["hard_rules"])
    example_to = next((p for p in parties if p != parties[0]), parties[0])
    if gated:
        gate = f"""
## The gated party: `{gated}`

`{gated}` may only read and write files, not move them, and is the party most likely to be away. So a
message in `to_{gated}/` is archived only once it is `status: done` **and** `acknowledged: true`.
Whoever writes to `{gated}` sets `acknowledged: false`; only `{gated}` ever flips it to `true`, by
rewriting that one field after actually reading the message. Every other inbox is archived by its own
party once a message is `status: done`.
"""
        ack_line = f"acknowledged: false   # only on messages to {gated}; {gated} flips it to true after reading\n"
    else:
        gate, ack_line = "", ""

    return f"""{MD_MARK}
# comms/: message channel between {", ".join(parties)}

Several AI harnesses work on this project and cannot talk to each other directly. This folder is the
only link between them. The human tells each one when it has something to read ("check comms").

| Party | What it is | How it reaches this folder |
|---|---|---|
{rows}

## Who gets which task

Route by cost and difficulty: well-specified, token-heavy work that is easy to check goes to the
cheaper harness; work that needs judgement or care goes to the stronger one. A request should be
checkable: ask for ids, links, verbatim quotes and a fixed output format.

| Send to | Good for | Not for |
|---|---|---|
{routing}
| **the human** (no folder) | final decisions, labels, credentials and access | |

## Folders

| Folder | Holds |
|---|---|
{folders}
| `archive/YYYY-MM/` | finished messages, plus the append-only `archive/INDEX.md` |
| `config.json` | parties, gated party, timezone; the source of truth for every generated file |
{ownership}
## One message = one file

`to_<recipient>/YYYY-MM-DD_HHMM_<from>_<short-slug>.md`. The timestamp is the sender's real local time
in **{hc["timezone"]}**, read from the clock at the moment of writing: never guessed, rounded, or reused
from an earlier message. Local harnesses create messages with the stamper, which does this for them:

```
{py()} comms/new_message.py --from {parties[0]} --to {example_to} --type request --slug short-slug
```

Every message starts with this header:

```
---
id: 2026-01-31_1430_{parties[0]}_short-slug   # the file name without .md
from: {parties[0]}
to: {example_to}
re: none              # id of the message this answers, or none
type: request         # request | answer | note
status: open          # open | done
{ack_line}---
```

Then short sections: `## Ask` (request) or `## Answer` (answer, note); `## Context` (paths relative to
the project root, ids); `## Expected output` (requests only: format, checks, where to write it). Point
at files instead of pasting them. A number in a message says which file it came from.
{gate}
## Handling a message (every party)

1. On "check comms", read every `status: open` file in your own `to_<you>/`.
2. Do the request within your own instruction file and the rules below. If it belongs with another
   party (see the routing table), say so in your answer instead of doing it.
3. Answer with a new file in the sender's inbox: `re:` = the request's id, `type: answer`,
   `status: done`. For a staged task, send `type: note` (`status: done` on the note) and leave the
   request `open` until the last stage lands. If the human must decide, leave it open and say what is
   needed.
4. When a request is finished, set its `status: done` (a one-field edit to the file in your own inbox)
   and run `{py()} comms/archive_sweep.py --as <you> --gated`.

`status: done` on an answer means "nothing more is needed on this message", not "the task is finished".

## The only edits to another party's file

1. Setting `status: done` on a request in your own inbox once it is finished, and the sweep moving it.
2. The gated party flipping `acknowledged: false` to `true` after reading.

Everything else is a new file.

## Archive

`archive_sweep.py` is deterministic (no model calls). `--as <you>` sweeps only your own inbox on
`status: done`; `--gated` also sweeps the gated inbox where `status: done` and `acknowledged: true`.
Files go to `archive/YYYY-MM/` by their filename date, and one line per file is appended to
`archive/INDEX.md`, which is never rewritten. `--dry-run` previews.

## Rules for every party
{rules}
"""


def render_local_skill(cfg, party):
    me = info(cfg, party)
    gated = cfg.get("gated_party")
    others = [p for p in cfg["parties"] if p != party]
    name = skill_name(cfg, party)
    tz = cfg["harness-comms"]["timezone"]
    gated_step = ""
    if party == gated:
        gated_step = f"""
   You are the gated party: after actually reading each message with `acknowledged: false`, change that
   one field to `acknowledged: true`, save, and re-read the file to confirm only that line changed."""
    ack_note = f" It adds `acknowledged: false` for messages to `{gated}`." if gated and gated != party else ""
    return f"""---
name: {name}
description: Check this project's comms/ folder for messages addressed to {party} ({me["title"]}), answer open requests, archive finished ones, and report what is outstanding. Use when the user says "check comms", asks whether {" or ".join(others) or "another party"} replied, or wants to send work to another party.
---
{MD_MARK}

You are party **`{party}`** in this project's `comms/` channel (parties: {", ".join(cfg["parties"])}).
The protocol is `comms/README.md`; follow it for anything this does not cover.

## Check in

1. List `comms/to_{party}/` and read every file with `status: open` in full.{gated_step}
2. Do each request within your instruction file and the rules in `comms/README.md`. If the routing
   table there says it belongs to another party, say so in your answer instead of doing it.
3. Answer with the stamper, which names the file from the real clock ({tz}) and writes the header:
   `{py()} comms/new_message.py --from {party} --to <sender> --type answer --re <request id> --slug <slug>`
   It prints the new path; fill in `## Answer` and `## Context`.{ack_note} For a staged task use
   `--type note` and leave the request open.
4. When a request in your inbox is fully done, change its `status: open` to `status: done` (only that
   field) and run `{py()} comms/archive_sweep.py --as {party} --gated`.
5. Glance at the other inboxes ({", ".join(f"`to_{p}/`" for p in others) or "none"}) for `status: open`
   files so you know what is pending elsewhere. Do not act on them.
6. Report briefly: what was open in your inbox, what you answered (new file paths), and what is still
   open and waiting on whom.

## Send a request

`{py()} comms/new_message.py --from {party} --to <party> --type request --slug <slug>`, then fill in
`## Ask`, `## Context` and `## Expected output`. Make the result checkable.

## Never

- Guess a timestamp or hand-name a file when the stamper is available.
- Edit, move or delete another party's file beyond the two edits `comms/README.md` allows.
- Treat a write as done without re-reading the file from disk.
"""


def render_instruction_block(cfg, parties, instr_file):
    tz = cfg["harness-comms"]["timezone"]
    gated = cfg.get("gated_party")
    others = [p for p in cfg["parties"] if p not in parties]
    who = "; ".join(
        f"as {info(cfg, p)['title']} you are party `{p}` (skill `{info(cfg, p)['skills']}/{skill_name(cfg, p)}/`)"
        for p in parties)
    me = parties[0] if len(parties) == 1 else "<you>"
    gate = f" Messages to `{gated}` carry `acknowledged: false`; only `{gated}` flips it." if gated else ""
    return f"""{BLOCK_START}
## comms/ (message channel with {", ".join(others) or "the other parties"})

This project's `comms/` folder links {", ".join(cfg["parties"])}. In it, {who}.
When the user says "check comms" (and at the start of a session), follow that skill; the protocol is
`comms/README.md`. Create every message with `{py()} comms/new_message.py` so its filename carries the
real local time ({tz}), never a guessed one.{gate} Finish each check with
`{py()} comms/archive_sweep.py --as {me} --gated`.
{BLOCK_END}
"""


def render_chat_skill(cfg, party, root):
    hc = cfg["harness-comms"]
    others = [p for p in cfg["parties"] if p != party]
    comms = (root / "comms").as_posix()
    routing = "\n".join(
        f"| `{p}` | {info(cfg, p)['title']} | {info(cfg, p)['good_for']} | {info(cfg, p)['not_for']} |"
        for p in others)
    gated = party == cfg.get("gated_party")
    ack_steps = """
3. After actually reading a message with `acknowledged: false`, change that one field to
   `acknowledged: true` and save the file. Re-read it to confirm that only that line changed. This is
   the only edit you ever make to a file you did not write; you never move or delete files (the local
   parties archive acknowledged messages).""" if gated else """
3. Never edit, move or delete a file you did not write."""
    return f"""---
name: {chat_skill_name(cfg, party)}
description: Check the {hc["project"]} comms/ folder on the user's computer ({comms}) for messages to {party} from {", ".join(others)}, acknowledge what you read, and write answers or requests back. Use when the user says "check comms" about {hc["project"]}, asks whether {" or ".join(others)} replied, or wants to hand work to one of them.
---

You are party **`{party}`** in the `comms/` channel of the **{hc["project"]}** project, shared with
{", ".join(f"`{p}`" for p in others)}. You reach it through your link to the user's computer (Claude
Desktop filesystem access or the claude.ai device link). All paths below are absolute.

- Folder: `{comms}/`
- Your inbox: `{comms}/to_{party}/`
- Full protocol: `{comms}/README.md` (read it once per conversation before writing anything)

If you cannot see the folder, tell the user that this chat has no file access to their computer yet
and stop; do not invent its contents.

## Check in

1. List `{comms}/to_{party}/`.
2. Read every message in it in full, oldest first, and tell the user what each one says (one or two
   lines each, with the file name).{ack_steps}
4. A `type: request` with `status: open` addressed to you is usually a question for the user: discuss
   it, then answer it with a new message (below).
5. Glance at the other inboxes ({", ".join(f"`to_{p}/`" for p in others)}) for `status: open` files and
   tell the user what is still waiting on whom. Do not act on them.

## Write a message

File: `{comms}/to_<recipient>/YYYY-MM-DD_HHMM_{party}_<short-slug>.md`. The timestamp is the real
current time in **{hc["timezone"]}**. Read it from a clock tool if you have one (for example `date` on
the linked computer); if you have none, ask the user for the time. Never guess or round it.

```
---
id: YYYY-MM-DD_HHMM_{party}_<short-slug>
from: {party}
to: <recipient>
re: <id of the message this answers, or none>
type: request            # request | answer | note
status: open             # open for a request; done for an answer or note
---

## Ask                   # "## Answer" for an answer or note
<one or two sentences>

## Context
<paths relative to the project root, ids>

## Expected output       # requests only
<format, checks, and where the result should be written>
```

Do not add an `acknowledged` field: only messages *to* `{party}` carry one. Keep messages short and point
at files. After writing, re-read the file from disk to confirm it landed. If the write is refused, show
the complete file name and content in one fenced block and ask the user to save it there.

## Who gets which task

| Party | What it is | Good for | Not for |
|---|---|---|---|
{routing}
"""


def render_chat_instructions(cfg, party, root):
    hc = cfg["harness-comms"]
    others = [p for p in cfg["parties"] if p != party]
    return f"""{MD_MARK}
# Joining claude.ai chat to the {hc["project"]} comms/ channel

1. **Give the chat file access to this computer** (Claude Desktop with filesystem access, or the
   claude.ai device link) covering `{root.as_posix()}`.
2. **Upload the skill**: claude.ai → Settings → Capabilities → Skills → Upload skill →
   `{CHAT_DIR}/{chat_skill_name(cfg, party)}.zip`. Re-upload it after every `sync` that changes it.
3. **Paste this into the claude.ai project's instructions** (Project → Instructions):

```
This project coordinates with {", ".join(others)} through files on my computer at
{root.as_posix()}/comms. You are the party "{party}" there. When I say "check comms", or ask whether
{" or ".join(others)} answered, use the {chat_skill_name(cfg, party)} skill. Never move or delete files in
that folder; the only edit you make to a file you did not write is flipping acknowledged: false to true
after reading it. Timestamps in file names are real {hc["timezone"]} time, never guessed.
```

4. In the chat, say "check comms" to try it.
"""


def zip_skill(name, text):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zi = zipfile.ZipInfo(f"{name}/SKILL.md", date_time=(1980, 1, 1, 0, 0, 0))
        zi.external_attr = 0o644 << 16
        zf.writestr(zi, text)
    return buf.getvalue()


# -------------------------------------------------------------------------------------------- planning

def plan(cfg, root):
    """Every file sync produces: {relative path: (kind, content)}.

    kinds: owned (regenerated while it carries MARK), seed (created only if missing),
    block (marked section merged into an instruction file), config.
    """
    files = {}
    files["comms/README.md"] = ("owned", render_readme(cfg))
    for asset in ("archive_sweep.py", "new_message.py"):
        files[f"comms/{asset}"] = ("owned", (ASSETS / asset).read_text(encoding="utf-8"))
    files["comms/archive/INDEX.md"] = (
        "seed", "# comms archive index\n\nAppend-only: `id | from -> to | summary | path`.\n\n")
    for p in cfg["parties"]:
        files[f"comms/to_{p}/.gitkeep"] = ("seed", "")

    by_instr = {}
    for p in local_parties(cfg):
        me = info(cfg, p)
        files[f"{me['skills']}/{skill_name(cfg, p)}/SKILL.md"] = ("owned", render_local_skill(cfg, p))
        by_instr.setdefault(me["instructions"], []).append(p)
    for instr, ps in by_instr.items():
        files[instr] = ("block", render_instruction_block(cfg, ps, instr))

    for p in cfg["parties"]:
        if info(cfg, p)["harness"] != "claude-ai":
            continue
        name = chat_skill_name(cfg, p)
        text = render_chat_skill(cfg, p, root)
        files[f"{CHAT_DIR}/{name}/SKILL.md"] = ("owned", text.replace("\n---\n", f"\n---\n{MD_MARK}\n", 1))
        files[f"{CHAT_DIR}/{name}.zip"] = ("owned", zip_skill(name, text))
        files[f"{CHAT_DIR}/README.md"] = ("owned", render_chat_instructions(cfg, p, root))
    return files


def merge_block(existing, block):
    if BLOCK_START in existing and BLOCK_END in existing:
        pre, rest = existing.split(BLOCK_START, 1)
        post = rest.split(BLOCK_END, 1)[1]
        return pre + block.rstrip("\n") + post
    legacy = re.compile(r"^## comms/.*?(?=^## |\Z)", re.MULTILINE | re.DOTALL)
    if legacy.search(existing):
        return legacy.sub(lambda _: block + "\n", existing, count=1)
    sep = "" if existing.endswith("\n\n") or not existing else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + sep + block


def is_owned(path):
    if path.suffix == ".zip":
        return path.with_suffix("").joinpath("SKILL.md").is_file() and is_owned(
            path.with_suffix("").joinpath("SKILL.md"))
    try:
        return MARK in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def apply(cfg, root, on_conflict, dry_run, config_text=None):
    files = plan(cfg, root)
    if config_text is not None:
        files = {"comms/config.json": ("config", config_text), **files}
    actions, conflicts, writes = [], [], []
    for rel, (kind, content) in files.items():
        path = root / rel
        data = content.encode("utf-8") if isinstance(content, str) else content
        if not path.exists():
            actions.append({"path": rel, "action": "create"})
            writes.append((path, data))
            continue
        current = path.read_bytes()
        if kind == "seed":
            actions.append({"path": rel, "action": "keep"})
            continue
        if kind == "block":
            text = current.decode("utf-8")
            if BLOCK_START not in text and on_conflict != "overwrite":
                conflicts.append(rel)
                actions.append({"path": rel, "action": "conflict (would add a comms/ section)"})
                continue
            data = merge_block(text, content).encode("utf-8")
        elif kind == "owned" and not is_owned(path) and on_conflict != "overwrite":
            conflicts.append(rel)
            actions.append({"path": rel, "action": "conflict (not generated by harness-comms)"})
            continue
        if current == data:
            actions.append({"path": rel, "action": "unchanged"})
        else:
            actions.append({"path": rel, "action": "update"})
            writes.append((path, data))

    # Generated check-comms skills or chat bundles that the current config no longer produces.
    removes = []
    globs = {f"{h['skills']}/check-comms*/SKILL.md" for h in HARNESSES.values() if h["skills"]}
    globs |= {f"{CHAT_DIR}/*/SKILL.md", f"{CHAT_DIR}/*.zip"}
    for pattern in sorted(globs):
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if rel not in files and is_owned(path):
                removes.append(path)
                actions.append({"path": rel, "action": "remove (no longer generated)"})

    if conflicts and on_conflict == "abort":
        return {"status": "conflict", "message": (
            "These files exist and were not written by harness-comms. Nothing was changed. Show the list "
            "to the user and rerun with --on-conflict skip (leave them) or --on-conflict overwrite "
            "(replace them; instruction files only get a marked comms/ section merged in)."),
            "conflicts": conflicts, "actions": actions}, 2
    if not dry_run:
        for path, data in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if path.suffix == ".py":
                path.chmod(0o755)
        for path in sorted(removes, key=lambda p: p.suffix != ".zip"):  # zips first: ownership reads SKILL.md
            path.unlink()
            if path.name == "SKILL.md" and not any(path.parent.iterdir()):
                path.parent.rmdir()
    return {"status": "dry_run" if dry_run else "ok", "actions": actions,
            "skipped_conflicts": conflicts}, 0


def config_json(cfg):
    ordered = {"parties": cfg["parties"]}
    if cfg.get("gated_party"):
        ordered["gated_party"] = cfg["gated_party"]
    ordered["harness-comms"] = cfg["harness-comms"]
    return json.dumps(ordered, indent=2) + "\n"


def next_steps(cfg):
    steps = []
    for p in local_parties(cfg):
        me = info(cfg, p)
        how = me.get("invoke") or 'say "check comms"'
        steps.append(f"{me['title']} (party {p}): {how}; skill at {me['skills']}/{skill_name(cfg, p)}/")
    for p in cfg["parties"]:
        if info(cfg, p)["harness"] == "claude-ai":
            steps.append(f"claude.ai (party {p}): follow {CHAT_DIR}/README.md: upload "
                         f"{CHAT_DIR}/{chat_skill_name(cfg, p)}.zip and paste the project instructions")
    return steps


# -------------------------------------------------------------------------------------------- auditing

def read_message(path, root):
    rel = path.relative_to(root).as_posix()
    issues = []

    def issue(rule, msg, severity="error"):
        issues.append({"file": rel, "rule": rule, "severity": severity, "message": msg})

    fm = FILENAME_RE.match(path.name)
    if not fm:
        issue("filename", "name is not YYYY-MM-DD_HHMM_<from>_<slug>.md")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        issue("readable", str(e))
        return None, issues
    m = HEADER_RE.match(text)
    if not m:
        issue("header", "missing or malformed --- header block")
        return None, issues
    fields = {k: v.split("#", 1)[0].strip() for k, v in FIELD_RE.findall(m.group(1))}
    for req in ("id", "from", "to", "re", "type", "status"):
        if not fields.get(req):
            issue("required_field", f"missing header field {req!r}")
    if fields.get("id") and fields["id"] != path.stem:
        issue("id_matches_name", f"id {fields['id']!r} differs from file name {path.stem!r}")
    if fm and fields.get("from") and not path.stem.startswith(f"{fm.group(1)}_{fields['from']}_"):
        issue("from_matches_name", f"from {fields['from']!r} is not the sender in the file name")
    if fields.get("type") not in (None, "", "request", "answer", "note"):
        issue("type", f"type {fields['type']!r} is not request | answer | note")
    if fields.get("status") not in (None, "", "open", "done"):
        issue("status", f"status {fields['status']!r} is not open | done")
    body = m.group(2)
    if "## Ask" not in body and "## Answer" not in body and "## Note" not in body:
        issue("body", "no '## Ask' or '## Answer' section", "warning")
    summary = ""
    for heading in ("## Answer", "## Ask", "## Note"):
        i = body.find(heading)
        if i != -1:
            after = body[i + len(heading):].strip().splitlines()
            summary = next((line.strip() for line in after if line.strip() and not line.startswith("#")), "")
            break
    msg = {"file": rel, **{k: fields.get(k) for k in ("id", "from", "to", "re", "type", "status",
                                                       "acknowledged")}, "summary": summary[:140]}
    if fm:
        msg["_stamp"] = fm.group(1)
    return msg, issues


def now_in(tz_name):
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def scan(root, cfg):
    comms = root / "comms"
    gated = cfg.get("gated_party")
    parties = cfg["parties"]
    now = now_in(cfg["harness-comms"]["timezone"])
    issues, inboxes = [], {}
    for d in sorted(x for x in comms.glob("to_*") if x.is_dir()):
        party = d.name[3:]
        if party not in parties:
            issues.append({"file": f"comms/{d.name}/", "rule": "unknown_inbox", "severity": "warning",
                           "message": f"{party!r} is not in config.json parties"})
        msgs = []
        for f in sorted(d.glob("*.md")):
            msg, f_issues = read_message(f, root)
            issues += f_issues
            if not msg:
                continue
            rel = msg["file"]
            if msg["to"] and msg["to"] != party:
                issues.append({"file": rel, "rule": "to_matches_inbox", "severity": "error",
                               "message": f"to: {msg['to']!r} but the file is in to_{party}/"})
            if msg["from"] and msg["from"] not in parties:
                issues.append({"file": rel, "rule": "known_sender", "severity": "warning",
                               "message": f"from: {msg['from']!r} is not a configured party"})
            if party == gated and (msg["acknowledged"] or "").lower() not in ("true", "false"):
                issues.append({"file": rel, "rule": "acknowledged_field", "severity": "error",
                               "message": f"messages to the gated party {gated!r} need 'acknowledged: false'"})
            if party != gated and msg["acknowledged"] is not None:
                issues.append({"file": rel, "rule": "acknowledged_field", "severity": "warning",
                               "message": "only messages to the gated party carry 'acknowledged'"})
            stamp = msg.pop("_stamp", None)
            if stamp:
                try:
                    if datetime.strptime(stamp, "%Y-%m-%d_%H%M") > now + timedelta(minutes=5):
                        issues.append({"file": rel, "rule": "future_timestamp", "severity": "warning",
                                       "message": "file name time is in the future: guessed timestamp?"})
                except ValueError:
                    issues.append({"file": rel, "rule": "filename", "severity": "error",
                                   "message": f"{stamp!r} is not a real date and time"})
            msgs.append(msg)
        inboxes[party] = msgs
    archived = {}
    if (comms / "archive").is_dir():
        for month in sorted(x for x in (comms / "archive").iterdir() if x.is_dir()):
            archived[month.name] = len(list(month.glob("*.md")))
    return inboxes, archived, issues


def sweep_ready(msg, party, gated):
    if msg["status"] != "done":
        return False
    return party != gated or (msg["acknowledged"] or "").lower() == "true"


# -------------------------------------------------------------------------------------------- commands

def cmd_init(args):
    root = Path(args.project_root).resolve()
    if (root / "comms" / "config.json").exists() and args.on_conflict != "overwrite":
        raise SystemExit("comms/config.json already exists: use add-party or sync, "
                         "or --on-conflict overwrite to start the config over.")
    try:
        parties, gated = parse_parties(args.parties)
    except ValueError as e:
        raise SystemExit(f"--parties: {e}")
    if args.gated:
        gated = None if args.gated == "none" else args.gated
    elif gated is None:
        gated = default_gated(parties)
    cfg = {"parties": [p for p, _ in parties]}
    if gated:
        cfg["gated_party"] = gated
    cfg["harness-comms"] = {
        "project": args.project_name or root.name,
        "timezone": args.timezone or detect_timezone(),
        "harnesses": dict(parties),
        "routing": load_json(args.routing_json) or {},
        "hard_rules": load_json(args.hard_rules_json) or list(DEFAULT_RULES),
        "ownership": load_json(args.ownership_json) or [],
    }
    check_config(cfg)
    report, code = apply(cfg, root, args.on_conflict, args.dry_run, config_json(cfg))
    report.update(config=cfg, next_steps=next_steps(cfg))
    return report, code


def cmd_add_party(args):
    root = Path(args.project_root).resolve()
    cfg, legacy = load_config(root, allow_legacy=True)
    try:
        parsed, gated_flag = parse_parties(args.party)
    except ValueError as e:
        raise SystemExit(f"--party: {e}")
    if len(parsed) != 1:
        raise SystemExit("--party takes exactly one party.")
    name, harness = parsed[0]
    if name in cfg["parties"]:
        raise SystemExit(f"party {name!r} already exists.")
    cfg["parties"].append(name)
    cfg["harness-comms"]["harnesses"][name] = harness
    if gated_flag:
        cfg["gated_party"] = name
    check_config(cfg)
    report, code = apply(cfg, root, args.on_conflict, args.dry_run, config_json(cfg))
    report.update(adopted_legacy_setup=legacy, config=cfg, next_steps=next_steps(cfg))
    return report, code


def cmd_sync(args):
    root = Path(args.project_root).resolve()
    cfg, _ = load_config(root)
    check_config(cfg)
    report, code = apply(cfg, root, args.on_conflict, args.dry_run)
    report["next_steps"] = next_steps(cfg)
    return report, code


def cmd_validate(args):
    root = Path(args.project_root).resolve()
    comms = root / "comms"
    if not comms.is_dir():
        return {"valid": False, "issues": [{"file": "comms/", "rule": "exists", "severity": "error",
                                            "message": "no comms/ folder"}]}, 0
    cfg, legacy = load_config(root, allow_legacy=True)
    issues = []
    if legacy:
        issues.append({"file": "comms/config.json", "rule": "config", "severity": "warning",
                       "message": "missing; parties inferred from to_* folders (run add-party or init to adopt)"})
    for req in ("README.md", "archive_sweep.py"):
        if not (comms / req).is_file():
            issues.append({"file": f"comms/{req}", "rule": "protocol_file", "severity": "error",
                           "message": "missing"})
    for p in cfg["parties"]:
        if not (comms / f"to_{p}").is_dir():
            issues.append({"file": f"comms/to_{p}/", "rule": "inbox", "severity": "error",
                           "message": "configured party has no inbox folder"})
    inboxes, _, msg_issues = scan(root, cfg)
    issues += msg_issues
    errors = sum(1 for i in issues if i["severity"] == "error")
    return {"valid": errors == 0, "errors": errors, "warnings": len(issues) - errors,
            "messages_checked": sum(len(v) for v in inboxes.values()),
            "issues": issues[:args.limit], "issues_truncated": len(issues) > args.limit}, 0


def cmd_status(args):
    root = Path(args.project_root).resolve()
    cfg, _ = load_config(root, allow_legacy=True)
    gated = cfg.get("gated_party")
    inboxes, archived, _ = scan(root, cfg)
    out = {}
    for party, msgs in inboxes.items():
        out[f"to_{party}"] = {
            "open": sum(m["status"] == "open" for m in msgs),
            "done_not_swept": sum(m["status"] == "done" for m in msgs),
            "unacknowledged": sum((m["acknowledged"] or "").lower() == "false" for m in msgs)
            if party == gated else None,
            "sweep_ready": sum(sweep_ready(m, party, gated) for m in msgs),
            "messages": msgs[:args.limit],
        }
    return {"gated_party": gated, "inboxes": out,
            "archived": {"total": sum(archived.values()), "by_month": archived}}, 0


def load_json(raw):
    if not raw:
        return None
    p = Path(raw)
    return json.loads(p.read_text(encoding="utf-8") if p.is_file() else raw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p, mutating=False, limit=False):
        p.add_argument("--project-root", default=".", help="project folder (default: current folder)")
        p.add_argument("--output", help="also write the JSON report to this file")
        if mutating:
            p.add_argument("--on-conflict", choices=["abort", "skip", "overwrite"], default="abort",
                           help="files not generated by this tool: abort (default), skip, or overwrite")
            p.add_argument("--dry-run", action="store_true", help="report the plan, write nothing")
        if limit:
            p.add_argument("--limit", type=int, default=50, help="max issues/messages listed (default 50)")

    p = sub.add_parser("init", help="create comms/ for a set of parties")
    common(p, mutating=True)
    p.add_argument("--parties", required=True,
                   help="comma list of name[:harness][:gated], e.g. 'chat,code,antigravity' or "
                        f"'chat:claude-ai,ui:antigravity'; harnesses: {', '.join(HARNESSES)}")
    p.add_argument("--gated", help="gated party name, or 'none' (default: the claude-ai party)")
    p.add_argument("--timezone", help="IANA zone for file names (default: this machine's)")
    p.add_argument("--project-name", help="display name (default: the folder name)")
    p.add_argument("--routing-json", help="JSON or file: {party: {good_for, not_for, title, reach}}")
    p.add_argument("--ownership-json", help="JSON or file: [{path, owner}] (off by default)")
    p.add_argument("--hard-rules-json", help="JSON or file: [rule, ...] replacing the defaults")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("add-party", help="add a party to an existing comms/")
    common(p, mutating=True)
    p.add_argument("--party", required=True, help="name[:harness][:gated], e.g. 'codex' or 'ui:antigravity'")
    p.set_defaults(fn=cmd_add_party)

    p = sub.add_parser("sync", help="regenerate files from comms/config.json")
    common(p, mutating=True)
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("validate", help="audit comms/ and message headers")
    common(p, limit=True)
    p.set_defaults(fn=cmd_validate)

    p = sub.add_parser("status", help="summarise inbox state")
    common(p, limit=True)
    p.set_defaults(fn=cmd_status)

    args = ap.parse_args()
    report, code = args.fn(args)
    text = json.dumps(report, indent=2)
    print(text)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
