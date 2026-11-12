# check-comms (claude.ai plugin)

Chat-side check-in for file-based `comms/` folders shared between claude.ai chat and local agents (Claude Code, Antigravity, Codex...),
as set up by [harness-comms](../../docs/harness-comms.md) or the older protocol it grew out of.

It is the claude.ai counterpart of harness-comms: the check-in of the gated party. Install it once and the chat can check every
harness-comms project on the linked computer, instead of uploading one generated `check-comms-<project>` skill per project.

## Commands
| Command | What it does |
|---|---|
| `/check-comms:check [project]` | Check one project (name, nickname or path), or every discovered project when empty |

## How projects are found
At run time, in the folders connected to the linked computer: any `comms/README.md` up to 3 levels deep. A `comms/config.json`
(harness-comms) gives the project name. `skills/check/references/projects.md` only adds nicknames and fallback paths.
Adding a project needs no rebuild: run harness-comms `init` in a connected folder. Only new shortcut commands need a rebuild.

## Requirements
The chat must be linked to the computer that holds the projects (Claude app open and online, listed under Local devices), with
those folders connected.

## Rules kept
Acknowledgement gate (chat only flips `acknowledged`), claiming (works with harness-comms claiming on or off, and with the older
protocol), verify every write against the device, chat never moves files and never runs the sweep.
Each project's `comms/README.md` wins over the plugin.

## Build and install
claude.ai takes the plugin as a zip with a `.plugin` extension. From the repo root:

```bash
mkdir -p dist && (cd plugins/check-comms && zip -r ../../dist/check-comms.plugin . -x '*.DS_Store')
```

Then add `dist/check-comms.plugin` in claude.ai under your plugin or skill settings. `dist/` is git-ignored, so built files are not
committed.

## Optional: a one-project shortcut
To get a short command such as `/check-comms:myproject`, add `skills/myproject/SKILL.md` before building:

```markdown
---
name: myproject
description: This skill should be used when the user runs /check-comms:myproject or says "check comms myproject". Shortcut that checks comms for the myproject project.
---

# check-comms: myproject

1. With the Read tool (plugin files are local, not on the linked computer), read `${CLAUDE_PLUGIN_ROOT}/skills/check/SKILL.md` and `${CLAUDE_PLUGIN_ROOT}/skills/check/references/routine.md`.
2. Follow them with the project resolved to the `myproject` nickname from `${CLAUDE_PLUGIN_ROOT}/skills/check/references/projects.md`. Skip discovery unless that path is unreachable.
3. Report as the check skill describes, one section headed `myproject`.
```

Add a matching `myproject` row to `projects.md`. Each shortcut means rebuilding and reinstalling the plugin, while
`/check-comms:check myproject` works without either.

## Notes for editing
- No angle brackets in any frontmatter `description`: claude.ai reads them as XML tags and rejects the skill.
- `${CLAUDE_PLUGIN_ROOT}` expands inside skill text in claude.ai.
- Plugin files are read with the Read tool, not through the device tools (those reach the user's computer).
