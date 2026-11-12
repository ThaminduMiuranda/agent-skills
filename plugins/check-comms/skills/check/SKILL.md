---
name: check
description: This skill should be used when the user runs /check-comms:check, says "check comms" or "check comms" followed by a project name, asks about a project's comms/ folder, archive_sweep, or whether a request or answer to another agent landed. Checks any project's comms/ folder on the linked computer, found automatically, from the claude.ai chat side.
argument-hint: "[project name | nickname | absolute path to a comms folder]  (empty = all projects)"
---

# check-comms: check

Check-in routine for a file-based `comms/` folder that the chat shares with local agents (Claude Code, Antigravity, Codex...).
Project agnostic: the project is resolved at run time. The full routine is in
`${CLAUDE_PLUGIN_ROOT}/skills/check/references/routine.md`. Read it before acting, every time.
Plugin files are local to this session: open them with the Read tool, never through the device tools (those reach the user's computer).

## 1. Resolve the project(s)

Argument handling:
- **Absolute path** to a folder containing `README.md` (a comms folder) or a project folder containing `comms/README.md`: use it.
- **Name or nickname**: match it, case-insensitive and ignoring `-`, `_` and spaces, against
  (a) the `harness-comms.project` value in each discovered `comms/config.json`,
  (b) the discovered project folder name,
  (c) the nicknames in the user's registry on the linked computer (see `${CLAUDE_PLUGIN_ROOT}/skills/check/references/registry.md`),
  (d) the nicknames in `${CLAUDE_PLUGIN_ROOT}/skills/check/references/projects.md` (built-in fallback).
  One match: use it. Several: list them and ask. None: list the discovered projects and ask.
- **Empty**: check every discovered project, one report section each.

Discovery (only when the argument is not an absolute path, or to list candidates):
1. Get the linked computer's connected folders (`get_device_info`, or the folders named in this session's context).
2. For each connected folder, look for `comms/README.md` at the folder itself and in its subfolders up to 3 levels down. Use
   non-recursive `device_list_dir` calls level by level and skip heavy or irrelevant folders (`.git`, `.venv`, `node_modules`,
   `__pycache__`, `data`, `papers`, `out`, `work`, `Datasets`, `archive`). Never stage files just to discover.
3. A folder whose `comms/` holds `config.json` is a harness-comms project: its key is `harness-comms.project` from that file
   (stage it, it is small). A `comms/` with only `README.md` is an older-protocol project: its key is the parent folder name.
4. Read the registry (`references/registry.md` says where and how, and that its paths are relative to the registry's own folder). Add its Projects rows that discovery did not reach, and drop
   every discovered project whose comms folder is listed under Ignored. Then add any `projects.md` path still missing.
If the linked computer cannot be reached, say so plainly (asleep, offline, or the Claude app closed) and stop.

## 2. Run the routine

For each resolved project, follow `${CLAUDE_PLUGIN_ROOT}/skills/check/references/routine.md` exactly. That project's own `comms/README.md` is the source of truth
and wins over the routine wherever they differ (header fields, statuses, claiming, extra fields, pre-archive steps).

## 3. Report

One section per project, headed with its key: what is new, what was acknowledged, what is open / in progress (with claimant and
age) / blocked / stale, and who it waits on (a named agent or the user). State only, not the steps taken. Keep it short.
If discovery found a comms folder that is neither registered nor ignored, list it once at the end with "add it with
/check-comms:add-project or hide it with /check-comms:remove-project".
No middle dot separators, no en or em dashes.
