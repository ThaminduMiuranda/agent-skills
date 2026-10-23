# Harnesses

## Where `init` and `sync` put each party's files (paths are inside the project)

| Harness id | Harness | Check-in skill | Instruction file | How to invoke |
|---|---|---|---|---|
| `claude-ai` | claude.ai chat or project | `comms/_chat/<name>/SKILL.md`, plus `<name>.zip` to upload | pasted into the claude.ai project (see `comms/_chat/README.md`) | say "check comms" |
| `claude-code` | Claude Code | `.claude/skills/check-comms/` | `CLAUDE.md` | `/check-comms` |
| `antigravity` | Antigravity | `.agents/skills/check-comms/` | `AGENTS.md` | say "check comms" |
| `codex` | Codex CLI | `.agents/skills/check-comms/` | `AGENTS.md` | `$check-comms` or say "check comms" |
| `gemini-cli` | Gemini CLI | `.gemini/skills/check-comms/` | `GEMINI.md` | say "check comms" |
| `opencode` | OpenCode | `.opencode/skills/check-comms/` | `AGENTS.md` | say "check comms" |
| `generic` | any other agent that reads `AGENTS.md` | `.agents/skills/check-comms/` | `AGENTS.md` | say "check comms" |

When two parties share a skills folder (for example Antigravity and Codex both use `.agents/skills`),
each skill is named `check-comms-<party>`, and the shared instruction file tells each harness which
party it is.

If a harness reads skills from a different folder in your version, put the party's harness in
`comms/config.json` as `generic`, or copy the generated skill to the right place and delete its marker
line, so `sync` leaves your copy alone.

## How claude.ai chat joins

claude.ai runs in the cloud. It reaches the project only through a link to the user's computer:
Claude Desktop's filesystem access, or the claude.ai device link. Through that link it can list, read
and write files. It should not be expected to move files or run scripts. That is why it is the gated
party:

- it reads its inbox and flips `acknowledged: true` on each message it has read
- the local parties archive those messages on their next sweep
- it writes requests and answers as new files, with the timestamp taken from a clock tool (or the
  user), never guessed
- if a write is refused, it shows the full file in a fenced block for the user to save

To set it up, the user does three things, all listed in `comms/_chat/README.md`:

1. Give the chat access to the project folder.
2. Upload `comms/_chat/check-comms-<project>.zip` at claude.ai → Settings → Capabilities → Skills.
   Skills uploaded to claude.ai belong to the account, not to one project, so each project's chat
   skill has the project's name in it.
3. Paste the instruction block into the claude.ai project's instructions.

The `harness-comms` skill itself is meant for local harnesses: its script has to run on the machine
that holds the project. Uploading it to claude.ai lets chat read the protocol, but not scaffold
anything.

## Installing harness-comms itself (user-level skill folders)

| Harness | Folder |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex, OpenCode and other `AGENTS.md`-style agents | `~/.agents/skills/` |
| Gemini CLI | `~/.gemini/skills/` |
| Antigravity | `~/.gemini/config/skills/` (newer builds; some versions use `~/.gemini/antigravity/skills/`) |
| OpenCode | `~/.config/opencode/skills/` (also reads `~/.claude/skills/` and `~/.agents/skills/`) |

The repo's `install.py` copies or links the skill into any of these folders.
