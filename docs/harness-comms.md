# harness-comms

Lets a claude.ai chat and local coding agents work together. Source:
[`skills/harness-comms/`](../skills/harness-comms/).

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

## What it generates

A single command creates:

- the `comms/` folder, its protocol README, and two small scripts: `new_message.py` creates messages
  with correct headers and real-clock timestamps, and `archive_sweep.py` archives finished messages
- a `check-comms` skill for each local harness, in the folder that harness reads skills from, plus a
  marked section in `CLAUDE.md`, `AGENTS.md` or `GEMINI.md` that leaves the rest of the file as it was
- a **claude.ai bundle**: a skill zip to upload, and a block to paste into the claude.ai project's
  instructions, so the chat can check its inbox, acknowledge what it has read, and send requests

Messages to the chat are archived only after the chat has acknowledged reading them, and each agent
archives only its own inbox, so nobody's unread mail disappears. The skill can also add a harness
later, re-generate everything from `comms/config.json`, and audit headers and inbox state.

## Which chat apps can join

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

## Setup

1. Install the skill for a local agent (see the [root README](../README.md#install)).
2. Ask that agent to "set up harness-comms for this project". It confirms the parties, then runs:

   ```bash
   python3 <skills-dir>/harness-comms/scripts/harness_comms.py init \
     --project-root . --parties "chat:claude-ai,code:claude-code,antigravity" --dry-run
   ```

3. For the claude.ai chat, follow the generated `comms/_chat/README.md`:
   - keep the Claude app running so the computer is listed under Local devices
   - upload `comms/_chat/check-comms-<project>.zip` under claude.ai → Settings → Capabilities → Skills
   - paste the project-instructions block into the claude.ai project

Chat apps don't need `harness-comms` itself installed, because its script has to run on the machine
that holds the project. To upload it to a chat app anyway (for example, so the chat can read the
protocol), `python3 install.py --zip --skill harness-comms` builds `dist/harness-comms.zip`.

## Reference

- [`SKILL.md`](../skills/harness-comms/SKILL.md): the agent-facing workflow
- [`references/protocol.md`](../skills/harness-comms/references/protocol.md): the message protocol
- [`references/harnesses.md`](../skills/harness-comms/references/harnesses.md): where each harness
  reads skills and instructions
