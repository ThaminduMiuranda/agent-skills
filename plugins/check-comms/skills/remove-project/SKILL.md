---
name: remove-project
description: This skill should be used when the user runs /check-comms:remove-project, or asks to remove, unregister, hide or stop tracking a project in the comms pipeline or in check-comms. Removes a project from the check-comms registry on the linked computer and hides it from discovery, without touching the project's files.
argument-hint: "project nickname, name or comms folder path [reason]"
---

# check-comms: remove-project

Stop `/check-comms:check` from showing a project. This never deletes, moves or edits anything inside the project, including its `comms/`
folder and messages: local agents keep using it unless the user removes it there. Plugin files are local to this session: read them with
the Read tool. Read `${CLAUDE_PLUGIN_ROOT}/skills/check/references/registry.md` and `${CLAUDE_PLUGIN_ROOT}/skills/check/references/routine.md` first.

## Steps
1. **Resolve the project** the same way `/check-comms:check` does (registry nicknames, `harness-comms.project` names, folder names, or a path).
   If nothing matches, list the known projects and stop. If several match, ask which one.
2. **Warn about pending mail.** List the project's inboxes. If any message is `open`, `in_progress` or `blocked`, or a message to chat is
   `done` but not acknowledged, show them and ask the user to confirm before going on.
3. **Registry.** Find `check-comms-registry.md` as `registry.md` describes (connected folder roots and their direct subfolders) (create it in the exact format from `registry.md` if
   none exists, asking where).
   - Delete the project's row from Projects, if present.
   - Add a row under Ignored: the comms folder path relative to the registry's folder, today's date (from a clock), and the reason if the user gave one (else `removed`).
     Skip if it is already there.
4. **Verify** the write as `routine.md` requires. Report what changed, and how to undo it (`/check-comms:add-project <path>`).
   If the project's built-in fallback nickname in `projects.md` still matches, say that the nickname keeps resolving until the plugin is
   rebuilt without it, but discovery and the no-argument check will skip the project.
