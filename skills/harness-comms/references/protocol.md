# comms/ protocol

The rules every party follows. The README that `harness_comms.py` generates in each project
(`comms/README.md`) is this document applied to that project's parties.

## Parties

A **party** is one agent session that works on the project, usually one per harness (`chat`, `code`,
`antigravity`, ...). Each party has one inbox, `comms/to_<party>/`. Anyone may write to any inbox.

One party may be **gated**: it can read and write files but not move them, and it is the most likely
to be away (claude.ai chat, by default). Messages to it carry an extra `acknowledged` field.

## Layout

```
comms/
  config.json          parties, gated_party, timezone, routing (source of truth)
  README.md            this protocol, for this project
  archive_sweep.py     deterministic archiver
  new_message.py       creates a correctly named and headed message
  to_<party>/          one inbox per party
  archive/YYYY-MM/     archived messages
  archive/INDEX.md     append-only log, one line per archived message
  _chat/               claude.ai bundle: skill folder, upload zip, setup steps
```

`config.json` uses the same keys as other comms tools (`parties`, `gated_party`) and keeps everything
specific to harness-comms under one `harness-comms` key:

```json
{
  "parties": ["chat", "code", "antigravity"],
  "gated_party": "chat",
  "harness-comms": {
    "project": "MyProject",
    "timezone": "Asia/Colombo",
    "harnesses": {"chat": "claude-ai", "code": "claude-code", "antigravity": "antigravity"},
    "routing": {"antigravity": {"good_for": "...", "not_for": "..."}},
    "hard_rules": ["..."],
    "ownership": [{"path": "src/", "owner": "code"}],
    "claiming": true,
    "extra_fields": [{"name": "repo", "help": "repo the work happens in"}],
    "pre_archive_steps": ["File the outcome in the project wiki and point the answer at it."]
  }
}
```

The last three keys arrived in v0.2.0. A config without them behaves as before: no claiming, no extra
fields, no extra steps. `init` turns claiming on for new projects (`--no-claiming` turns it off).

## Messages

File name: `to_<recipient>/YYYY-MM-DD_HHMM_<from>_<slug>.md`. The timestamp is the sender's real
local time in the project timezone, read from the clock at the moment of writing. It is never guessed,
rounded, or reused from an earlier message. Local parties use `new_message.py`. The chat party reads a
clock tool, or asks the user.

```
---
id: 2026-01-31_1430_chat_rerun-eval   # file name without .md
from: chat
to: code
re: none                               # id of the message this answers, or none
type: request                          # request | answer | note
status: open                           # open | done (with claiming: open | in_progress | blocked | done)
repo: none                             # only if config.json lists it in extra_fields
claimed_by: none                       # requests only, with claiming on
claimed_at: none                       # requests only, with claiming on: ISO 8601, real clock
acknowledged: false                    # only when `to:` is the gated party
---

## Ask            (## Answer for an answer or note)
## Context        paths relative to the project root, ids
## Expected output   (requests only) format, checks, where to write the result
```

Keep messages short. Point at files instead of pasting them, and say which file each number came from.
A message is a claim, not proof: check the cited file before acting on it.

## Claiming (when `claiming` is on)

1. A party picks up only `status: open` requests. It claims one by editing the header in place:
   `status: in_progress`, `claimed_by: <self>`, `claimed_at: <now>` (ISO 8601 with UTC offset, from
   the real clock).
2. It re-reads the file at once and goes on only if `claimed_by` is still itself.
3. Nobody touches an `in_progress` request claimed by someone else. `archive_sweep.py` prints a
   `[stale-claim]` line for any `in_progress` request whose `claimed_at` is older than `--stale-hours`
   (default 12), missing or unparseable. It never resets or moves one; the human decides.
4. `status: blocked` means waiting on the human. Only the human, or a party they tell, sets it back to
   `open`.

`in_progress` and `blocked` files are never archived. `validate` accepts the four statuses, warns about
claim fields on answers and notes or missing from requests, and treats `in_progress` without
`claimed_by` as an error. `status` counts `in_progress`, `blocked` and stale claims per inbox.

## Project extensions

- **`extra_fields`**: header fields a project adds, for example `repo` in a hub that hands work to
  several repositories. `new_message.py` takes each as a flag (`--repo FYP_Hub`), asks for it on a
  terminal, and writes `none` otherwise. The generated README lists them in its header block.
  `validate` does not flag them.
- **`pre_archive_steps`**: steps every party does before setting a request `status: done`, for example
  "file the outcome in the wiki". They are inserted into the generated README lifecycle and into every
  generated check-comms skill, chat's included.
- **Project notes in `comms/README.md`**: text between `<!-- harness-comms:project-notes:start -->` and
  `<!-- harness-comms:project-notes:end -->` is kept when `sync` regenerates the file. Use it for
  routing between several comms channels or project rules that need more than one line. Short rules
  belong in `hard_rules`.

## Lifecycle

1. On "check comms", a party reads every `status: open` file in its own inbox, and with claiming on
   claims each request first. The gated party reads every unacknowledged file.
2. It does the work. If the work belongs to another party, it says so in its answer instead.
3. It answers with a new file in the sender's inbox: `re:` set to the request id, `type: answer`,
   `status: done`.
   - A staged task gets interim `type: note` replies (each `status: done`). The request stays `open`
     (`in_progress` with claiming) until the last stage lands.
   - A request that needs a human decision stays `open` (`blocked` with claiming), and the answer says
     what is needed.
4. It does any `pre_archive_steps` the project defines.
5. Once a request is finished, its recipient sets the request's `status: done` and runs
   `archive_sweep.py --as <self> --gated`.

`status: done` on an answer means "nothing more is needed on this message". It does not mean the
task is finished.

## The only edits to another party's file

1. The recipient sets `status: done` on a finished request in its own inbox. The sweep then moves it.
   With claiming on, the recipient also claims the request (`status: in_progress`, `claimed_by`,
   `claimed_at`) and may set it to `blocked`.
2. The gated party changes `acknowledged: false` to `true` after actually reading a message, and
   re-reads the file to confirm that only that field changed.

Everything else is a new file.

## Archiving

`archive_sweep.py` is deterministic and makes no model calls.

- `--as <party>` archives `to_<party>/` files with `status: done`. A party can therefore archive only
  its own inbox, so mail its owner has not read yet is never moved.
- `--gated` (alias `--chat`) also archives files in the gated inbox that have both `status: done` and
  `acknowledged: true`. It is safe to pass on every run.
- With no `--as`, it archives every non-gated inbox. This is the older behaviour; avoid it.
- Each file goes to `archive/<YYYY-MM>/`, using the month from the filename's date, and one line is
  appended to `archive/INDEX.md`. The sweep never overwrites an existing file, and never rewrites
  `INDEX.md`.

## Why these rules exist

- **Real clock timestamps:** messages are sorted and threaded by file name. A guessed or rounded
  time silently misorders them. `validate` flags timestamps that are in the future.
- **One file per message, never edited:** concurrent writers from different harnesses cannot
  clobber each other, and the archive stays a faithful record.
- **The acknowledged gate:** the author of a message can say it is done, but only the reader can say
  it was read. Without the gate, a sweep can archive an answer before the chat ever sees it.
- **Claiming:** two sessions checking the same inbox at once would otherwise both start the same
  request. The claim plus an immediate re-read makes the second one back off. Stale claims are only
  reported, because a claim may be old for a good reason (a long run) and only the human knows.
- **`blocked` as its own status:** an `open` request waiting on the human looks the same as one nobody
  has picked up, so other parties keep re-reading it. `blocked` says who it waits on.
- **Extensions in config, not in hand edits:** a hand-edited README or skill stops receiving fixes
  from `sync`. `extra_fields`, `pre_archive_steps` and the project-notes block keep project rules in
  places `sync` respects.
- **`--as` sweeps:** in older versions, any party's sweep archived every local inbox. One agent could
  file away another agent's unread answer.
- **Verify writes:** a tool reporting "written" is not proof. Re-read the file from its real path.
