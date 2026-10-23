---
name: harness-comms
description: Join several AI harnesses (claude.ai chat, Claude Code, Antigravity, Codex, Gemini CLI, OpenCode, ...) working on one project through a file-based comms/ folder. Scaffolds the folder, protocol README, archive and message-stamping scripts, a check-comms skill and instruction block per local harness, and an uploadable skill plus project instructions for claude.ai chat; also adds parties and audits message headers and inbox state. Use when the user wants agents in different harnesses (especially claude.ai chat) to coordinate on a project, set up or extend a comms/ pipeline, or check that comms/ is healthy.
---

# harness-comms

Harnesses that cannot talk to each other share one project folder. `comms/` is their mailbox: one
inbox per party (`comms/to_<party>/`), one Markdown file per message, a fixed header, and a
deterministic archive script. claude.ai chat joins through the user's computer, which is linked to
Claude as a local device while the Claude app runs on it. The chat reads and writes files but never
moves them, so it is the **gated** party. A message to it is archived only after it flips
`acknowledged: true`.

All the work is done by `scripts/harness_comms.py` in this skill's folder (Python 3.9+, standard
library only). Run it with `python3` (`python` or `py -3` on Windows; `uv run` also works) using the
absolute path of this skill folder. It prints a JSON report.

`references/protocol.md` is the full protocol. `references/harnesses.md` lists where each harness
reads skills and instructions, and how claude.ai joins.

## Set up a project

1. **Settle the configuration with the user.** Use your platform's structured question tool if it has
   one; otherwise ask in plain text, one question at a time. Propose answers based on what you can see;
   don't ask cold:
   - **Parties.** Short lowercase names, each with a harness: `claude-ai`, `claude-code`,
     `antigravity`, `codex`, `gemini-cli`, `opencode`, `generic`. Suggest yourself, plus `chat` for
     claude.ai, plus any harness the project already shows signs of (`.claude/`, `.agents/`, `.gemini/`,
     `AGENTS.md`, `GEMINI.md`).
   - **Gated party.** Defaults to the claude.ai party. Explain why: other inboxes are archived as soon
     as a message is `status: done`, but the gated inbox is archived only after that party has actually
     read the message.
   - **Timezone.** Defaults to this machine's. File names carry real local time.
   - **Routing and ownership (optional).** Each harness comes with default "good for / not for" rows.
     Offer to adjust them (`--routing-json`). Add a file-ownership table (`--ownership-json`) only if
     the user wants one.
2. **Dry run:**
   ```
   python3 <skill>/scripts/harness_comms.py init --project-root <project> \
     --parties "chat:claude-ai,code:claude-code,antigravity" --dry-run
   ```
   Party spec: `name[:harness][:gated]`. Common names imply their harness: `chat` (claude-ai), `code`
   (claude-code), `antigravity`, `codex`, `gemini` (gemini-cli), `opencode`.
3. **Run it without `--dry-run`.** If it exits with code 2 and `"status": "conflict"`, some files
   exist that this tool did not write (for example a hand-written `CLAUDE.md`). Nothing has changed at
   that point. Show the user the list and let them pick, then rerun with that choice:
   - `--on-conflict merge`: add a marked `## comms/` section to `CLAUDE.md`, `AGENTS.md` and
     `GEMINI.md`, keeping the rest of each file, and leave every other conflicting file alone.
   - `--on-conflict skip`: leave all of them alone.
   - `--on-conflict overwrite`: replace them. The instruction files still only get the section
     merged in.

   If you cannot ask (a non-interactive run), use `merge`, and list the skipped files in your
   report. Never use `overwrite` without the user's say-so.
4. **Verify.** Run `validate` and `status`, and re-read a generated file or two from disk.
5. **Hand off.** Give the user the report's `next_steps`: the exact check-in command for each local
   harness (for example `/check-comms` in Claude Code), and the claude.ai steps from
   `comms/_chat/README.md`:
   - keep the Claude app running on this computer, so it is listed under Local devices
   - upload `comms/_chat/check-comms-<project>.zip` under claude.ai → Settings → Capabilities → Skills
   - paste the project-instructions block into the claude.ai project

## Change a project

- **Add a harness:** `add-party --party codex` (or `--party ui:antigravity`). This also works on an
  older `comms/` that has no `config.json`; it infers the parties from the `to_*` folders.
- **Edit routing, rules, timezone or ownership:** edit `comms/config.json` (the source of truth),
  then run `sync`. Generated files carry a `harness-comms: generated file` marker line. Deleting that
  line makes the file yours, and `sync` will no longer overwrite it without asking.
- **Audit:** `validate` checks file names, headers, `to:` matching the inbox, the `acknowledged` field
  on gated messages, and timestamps in the future (a sign that one was guessed). `status` counts open,
  unacknowledged and sweep-ready messages for each inbox.

## Day-to-day

Day-to-day work runs through each party's generated `check-comms` skill, not this one. Every local
party creates messages with `python3 comms/new_message.py`, which reads the real clock and writes the
header. Each party ends a check-in with `python3 comms/archive_sweep.py --as <self> --gated`, which
archives only its own inbox plus acknowledged gated messages. It never archives another party's unread
mail.

## Mistakes to avoid

- Writing over a user's `CLAUDE.md`, `AGENTS.md` or `comms/README.md` without asking: always let the
  conflict check run first.
- Leaving out the claude.ai steps at hand-off. Without the uploaded skill and file access, chat cannot
  join.
- Guessing timestamps, or naming message files by hand when `new_message.py` is available.
- Running `archive_sweep.py` without `--as`. That sweeps every non-gated inbox, including messages
  their owners have not read yet.
