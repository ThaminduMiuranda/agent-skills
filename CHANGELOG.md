# Changelog

## Unreleased

- **`check-comms` claude.ai plugin** (`plugins/check-comms/`): the chat side of `harness-comms` as one
  installable plugin. `/check-comms:check [project]` discovers `comms/` projects on the linked computer,
  so chat no longer needs a generated skill per project.
- `check-comms` plugin v0.2.1: `/check-comms:add-project` and `/check-comms:remove-project`, and an on-computer
  registry (`check-comms-registry.md` at a connected folder root or one of its direct subfolders) with Projects and
  Ignored tables. The check skill reads it and lists discovered folders that are neither registered nor ignored.

## v0.2.0

`harness-comms`:

- **Claiming** (`"claiming": true` in `comms/config.json`, on by default for new projects, `init
  --no-claiming` to turn it off). Statuses `open | in_progress | blocked | done`; requests carry
  `claimed_by` and `claimed_at`. `archive_sweep.py` reports stale claims (`--stale-hours`, default 12)
  and never moves `in_progress` or `blocked` files. `validate`, `status`, `new_message.py`, the
  generated README and every generated check-comms skill follow the setting.
- **Project extensions**: `extra_fields` (extra header fields such as `repo`, written by
  `new_message.py --<name>`) and `pre_archive_steps` (steps inserted before "set status: done and
  archive" in the README and every skill).
- **Project notes** in `comms/README.md` between `<!-- harness-comms:project-notes:start -->` and
  `<!-- harness-comms:project-notes:end -->` survive `sync`.
- `validate` and `status` skip `README.md` folder notes inside inboxes.
- Backward compatible: a `config.json` without the new keys generates the same README, skills and
  instruction blocks as v0.1.0.

## v0.1.0

First release: `harness-comms` with `init`, `add-party`, `sync`, `validate`, `status`, the claude.ai
chat bundle, `archive_sweep.py --as` and `new_message.py`.
