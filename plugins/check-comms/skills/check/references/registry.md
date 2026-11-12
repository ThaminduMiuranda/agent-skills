# Project registry (on the linked computer)

The installed plugin is read-only, so the user's own project list lives on the linked computer, in a file named
`check-comms-registry.md` at the root of a connected folder or of one of its direct subfolders.

## Finding it
List each connected folder root, and each of its direct subfolders (skip dot folders and heavy ones such as `Datasets`, `node_modules`,
`.venv`), non-recursively, and look for `check-comms-registry.md`. Use every one found (merge them). If none
exists, the check skill relies on discovery plus `projects.md`; the add-project skill creates one.

## Format (keep exactly this shape, flat Markdown tables)

```
# check-comms registry

Edited by the check-comms plugin (add-project, remove-project). Safe to edit by hand.

## Projects
| Nickname(s) | comms folder | Protocol | Added |
|---|---|---|---|
| myproject, mp | /path/to/myproject/comms | harness-comms v0.2 | 2026-01-31 |

## Ignored
| comms folder | Removed | Reason |
|---|---|---|
| /path/to/oldproject/comms | 2026-02-15 | finished |
```

- Nicknames: comma separated, lowercase, no spaces. The first one is the project's key in reports.
- `Protocol`: `harness-comms vX.Y` (has `comms/config.json`), `older` (README only), or `none yet` (folder registered, comms not set up).
- `Ignored`: comms folders that discovery must skip. A path in Ignored never shows up in `/check-comms:check`, even if discovery finds it.

## Writing it
Read it fresh (stage it), edit only the rows concerned, commit with `expectedMtimeMs` from that staging, then re-stage and confirm the
change landed and nothing else changed. Keep both tables even when empty.
