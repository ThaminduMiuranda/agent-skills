---
name: add-project
description: This skill should be used when the user runs /check-comms:add-project, or asks to add, register or start tracking a project in the comms pipeline or in check-comms. Registers a project folder in the check-comms registry on the linked computer and reports whether its comms/ folder is set up.
argument-hint: "path to the project folder (or its comms folder) [nickname, ...]"
---

# check-comms: add-project

Register a project so `/check-comms:check` finds it by nickname. Plugin files are local to this session: read them with the Read tool.
Read `${CLAUDE_PLUGIN_ROOT}/skills/check/references/registry.md` first (location and exact format), and
`${CLAUDE_PLUGIN_ROOT}/skills/check/references/routine.md` (write verification).

## Steps
1. **Arguments.** First argument: the project folder or its `comms/` folder (absolute path, or a folder name to look for in the connected
   folders). Remaining arguments: nicknames. If no path is given, ask for it. If no nickname is given, propose one from the
   `harness-comms.project` value in `comms/config.json`, else from the folder name (lowercase, no spaces), and ask the user to confirm.
2. **Reach the folder.** Check it lies inside a connected folder of the linked computer. If not, request access to that one folder
   (`device_request_folder_access`, with a one-line reason). If the computer is unreachable or access is declined, stop and say so.
3. **Detect the comms state.**
   - `comms/config.json` present: protocol `harness-comms v<version if stated, else "?">`. Note the parties and the gated party. If chat
     is not a party, or not the gated party, warn that chat cannot use this project's comms until a local agent adds it.
   - Only `comms/README.md`: protocol `older`.
   - No `comms/`: protocol `none yet`. Do not scaffold it from chat (chat cannot run scripts or move files). Tell the user to have a local
     agent set it up with harness-comms, then rerun this command. Ask whether to register the folder now anyway.
4. **Registry.** Find `check-comms-registry.md` as `registry.md` describes (connected folder roots and their direct subfolders). If none exists, ask which connected folder root
   should hold it (propose the one that contains the project), and create it in the exact format from `registry.md`.
   - If the comms folder is under Ignored, move it back (delete that Ignored row).
   - If it is already under Projects, merge the nicknames instead of adding a second row.
   - If a nickname is already used by another project, stop and ask for a different one.
   - Otherwise add one Projects row: nicknames, comms folder path relative to the registry's folder (see `registry.md`), protocol,
     today's date (from a clock).
   - If the registry still has absolute paths in other rows, offer to convert them to relative in the same write.
5. **Verify** the write as `routine.md` requires (re-stage, compare). Report: the row as written, the registry path, the comms state, and
   the command to check it (`/check-comms:check <first nickname>`). Chat never creates, moves or deletes anything inside the project.
