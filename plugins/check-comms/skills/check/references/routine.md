# Check-in routine (chat side)

Default rules for the protocol family (harness-comms v0.1 and v0.2, and the older pre-harness-comms protocol). The project's own `comms/README.md` wins
wherever it differs. Stage and read it first, every check.

## Verify every write

`device_commit_files` returning `"written"` is not proof a file changed. After every write, `device_stage_files` the device path
again and compare it with what was written (content and mtime). When editing a staged file, pass `expectedMtimeMs` from that
staging so a concurrent edit by another agent is refused, not overwritten. Never trust a local draft in place of the device copy.

## Statuses

`open | in_progress | blocked | done` (claiming projects), or `open | done` (no claiming). Requests may carry `claimed_by`, `claimed_at`.
- `open`: nobody has taken it.
- `in_progress`: claimed by `claimed_by` since `claimed_at`. Never touch it.
- `blocked`: waiting on the user. Only the user (or someone they name) sets it back to `open`.
- `done`: finished. Swept by a local agent.

## Routine per project

1. **List the chat inbox** (`to_chat/`, or as the README names it). Skip files without a header (`README.md`, `.gitkeep`).
   - `type: request`, `status: open`, addressed to chat: claim it before working (claiming projects: `status: in_progress`,
     `claimed_by: chat`, `claimed_at:` real clock time), commit with `expectedMtimeMs`, re-stage, proceed only if still `chat`.
   - Answer or note still `open` or `blocked`: it waits on a user decision. Surface it plainly, do not decide it.
   - `status: done`, `acknowledged: false`: read it in full.
   - `status: done`, `acknowledged: true`: handled. A local agent's sweep archives it. Nothing to do.
2. **Acknowledge** every `done` file just read: change only `acknowledged: false` to `true`, commit with `expectedMtimeMs`, re-stage
   and confirm only that field changed. This is the one edit chat may make to a file it does not own.
3. **Glance at the other inboxes** (`to_code/`, `to_antigravity/`, ...). Do not act on them. Note every file not `done`: `open`
   (not picked up), `in_progress` (who, since when, stale if over 12 h or missing/unparseable `claimed_at`, never reset it),
   `blocked` (what the user must decide).
4. **Project checks from the README**, for example extra fields or pre-archive steps. When an answer says work is done, check the
   files it names exist and changed, and report gaps instead of fixing them silently.
5. **Chat never moves or deletes files and never runs the sweep.** Local agents archive with `archive_sweep.py --as <self> --gated`
   (harness-comms) or the older `--chat` form.

## Sending a request or answer

- Choose the right channel when a project has several (the README's routing rules). Never send the same request to two channels.
- Read the real time from a clock (shell `date` with the project timezone, or a clock tool). Never guess or round it.
- File name `YYYY-MM-DD_HHMM_chat_<slug>.md`, placed in the recipient's inbox. Header exactly as the README defines it: `id`, `from`,
  `to`, `re`, `type`, `status`, plus extra fields the project declares (for example `repo:`), `claimed_by: none` and `claimed_at: none`
  on requests in claiming projects, and no `acknowledged` field (only messages to chat carry it).
- Before setting a request chat handled to `done`, follow the README's pre-archive steps (for example: file the outcome in the
  project's wiki and log).
- Commit, then re-stage and compare to confirm it landed. If the device link refuses a write, show the complete file (name and
  content) in one fenced block and ask the user to save it.
