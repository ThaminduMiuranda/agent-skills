# agent-skills

Agent Skills that work in any harness. Each one is a `SKILL.md` with YAML frontmatter, plus any
`scripts/`, `references/` and `assets/` it needs. Each skill lives in its own folder under `skills/`
and installs on its own.

## Skills

### [`harness-comms`](skills/harness-comms/): let claude.ai chat and local coding agents work together

Claude Code, Antigravity, Codex, Gemini CLI and a claude.ai chat can all work on the same project,
but they cannot message each other. `harness-comms` gives them a shared mailbox inside the project:

```
            claude.ai chat  (reaches your files via Local devices: the Claude app on your PC)
                  │  reads its inbox, flips acknowledged: true, writes new files
                  ▼
 ┌──────────────── project/comms/ ────────────────┐
 │ to_chat/   to_code/   to_antigravity/   ...     │  one message = one Markdown file
 │ config.json   README.md   archive/YYYY-MM/      │  fixed header, real-clock timestamps
 │ new_message.py   archive_sweep.py               │  deterministic, no model calls
 └─────────────────────────────────────────────────┘
       ▲                  ▲                  ▲
  Claude Code        Antigravity        Codex / Gemini CLI / OpenCode
  /check-comms       check-comms        check-comms
```

A single command generates:

- the `comms/` folder, its protocol README, and two small scripts: one creates messages with correct
  headers and timestamps, the other archives finished messages
- a `check-comms` skill for each local harness, placed in the folder that harness reads skills from,
  plus a marked section in `CLAUDE.md`, `AGENTS.md` or `GEMINI.md` that leaves the rest of the file
  as it was
- a **claude.ai bundle**: a skill zip to upload, and a block to paste into the claude.ai project's
  instructions, so the chat can check its inbox, acknowledge what it has read, and send requests

Messages to the chat are archived only after the chat has acknowledged reading them, and each agent
archives only its own inbox, so nobody's unread mail disappears. The skill can also add a harness
later, re-generate everything from `comms/config.json`, and audit headers and inbox state.

#### Which chat apps can join

A party only has to **read and write files in the project folder**. It does not need to move them or
run scripts, which is why the chat is the gated party. Coding agents (Claude Code, Codex, Antigravity,
Grok Build, ...) run on your machine and always qualify. Chat apps vary, as of October 2026:

| Chat app | Reads/writes a local folder? | In this pipeline |
|---|---|---|
| **Claude** (web, desktop app, mobile) | Yes, through **Local devices**: while the Claude app runs on your computer (macOS, Windows, Linux beta), chats can run tasks with its local files, browser and local MCPs. No extension needed. | Supported: the `chat` party, with the generated claude.ai skill (tested) |
| **ChatGPT**, desktop app (Work) | Yes, if your plan and workspace allow it and you grant each folder. Web and mobile can't. | Untested; Codex (local) joins as `codex` |
| **Gemini**, Mac app (Spark) | Yes, for "Connected folders" (beta: US, Google AI Ultra). Windows app and web can't. | Untested; Antigravity (local) joins as `antigravity` |
| **Grok Bot** | No. It works in an xAI cloud computer, not on your machine. | Can't join; Grok Build (local CLI) joins as `generic` |

Notes:
- **Local access still means cloud processing.** Whatever a chat app reads from a connected folder is
  sent to that provider's models. Connect the project folder only, not your home folder.
- **Claude has other routes in the desktop app:** the Filesystem extension (Settings → Extensions)
  and Cowork's connected folders. Local devices is the simplest of the three, and the only one that
  also reaches your files from a phone or browser.
- **The computer must be on, with the Claude app running.** If it is asleep or the app is closed,
  the chat can't see `comms/` and the skill tells it to stop rather than guess.
- **Gemini CLI no longer serves personal accounts.** That ended on 18 June 2026 for free, AI Pro and AI
  Ultra; enterprise and API-key users keep it. Personal users should add `antigravity` (Antigravity
  CLI, `agy`) instead of `gemini`.

## Install

All of these put the skill folder where your harness looks for skills. Then ask your agent to "set
up harness-comms for this project".

**Installer (Linux, macOS, Windows; needs Python 3.9+):**

```bash
git clone https://github.com/ThaminduMiuranda/agent-skills
cd agent-skills
python3 install.py                        # every harness found on this machine
python3 install.py --target claude-code   # or: agents, codex, gemini-cli, antigravity, opencode, all
python3 install.py --project ~/my-project # project-level instead of user-level
python3 install.py --link                 # symlink, so `git pull` updates it
```

**`npx skills`:**

```bash
npx skills add ThaminduMiuranda/agent-skills --skill harness-comms
```

**Without cloning** (copy only the one skill folder; set `DEST` to your harness's skills folder):

```bash
DEST=~/.claude/skills   # ~/.agents/skills, ~/.gemini/skills, ~/.gemini/config/skills, ...
mkdir -p "$DEST" && curl -sL https://github.com/ThaminduMiuranda/agent-skills/archive/refs/heads/main.tar.gz \
  | tar -xz -C "$DEST" --strip-components=2 agent-skills-main/skills/harness-comms
```

**Or ask your agent:**

> Install the `harness-comms` skill from https://github.com/ThaminduMiuranda/agent-skills (only the
> `skills/harness-comms/` folder) wherever you load skills from, then use it to set up comms/ for this
> project with claude.ai chat as one of the parties.

| Harness | User-level skills folder |
|---|---|
| Claude Code | `~/.claude/skills/` |
| Codex, OpenCode, other `AGENTS.md` agents | `~/.agents/skills/` |
| Antigravity (IDE and `agy` CLI) | `~/.gemini/config/skills/` |
| Gemini CLI (enterprise / API key) | `~/.gemini/skills/` |
| anything else | wherever it loads `SKILL.md` folders from |

If an older skill with the same name is already installed at user level, some harnesses load that
one instead of a newer project-level copy. Replace it with `install.py --force`.

**Chat apps** do not need `harness-comms` installed. The script has to run on the machine that holds
the project, so a local agent sets the project up. For the claude.ai chat, upload the project's own
chat skill, `comms/_chat/check-comms-<project>.zip`, under claude.ai → Settings → Capabilities →
Skills, and follow `comms/_chat/README.md`. To upload `harness-comms` itself to a chat app (for
example, so it can read the protocol), `python3 install.py --zip` builds `dist/harness-comms.zip`.

## Quick start (what your agent runs)

`<skills-dir>` is wherever the skill was installed:

```bash
python3 <skills-dir>/harness-comms/scripts/harness_comms.py init \
  --project-root . --parties "chat:claude-ai,code:claude-code,antigravity" --dry-run
```

See [`skills/harness-comms/SKILL.md`](skills/harness-comms/SKILL.md) for the full workflow, and
[`references/protocol.md`](skills/harness-comms/references/protocol.md) for the protocol.

## License

MIT, see [`LICENSE`](LICENSE).
