# agent-skills

Agent Skills that work in any harness: Claude Code, Codex, Antigravity, Gemini CLI, OpenCode, or
anything else that loads `SKILL.md` folders. Each skill lives in `skills/<name>/` and installs on its
own. Each skill's full documentation is in `docs/<name>.md`, which is kept out of the skill folder so
installs stay lean.

## Skills

| Skill                                    | What it does                                                                                                            | Docs                                           |
| ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| [`harness-comms`](skills/harness-comms/) | Lets a claude.ai chat and local coding agents work together on one project through a shared file-based `comms/` mailbox | [docs/harness-comms.md](docs/harness-comms.md) |

## Install

Replace `<skill>` with a name from the table.

**Installer** (Linux, macOS, Windows; Python 3.9+):

```bash
git clone https://github.com/ThaminduMiuranda/agent-skills && cd agent-skills
python3 install.py                        # every skill, into every harness found on this machine
python3 install.py --skill <skill>        # one skill (repeatable)
python3 install.py --target claude-code   # one harness: claude-code, agents, codex, gemini-cli, antigravity, opencode, all
python3 install.py --project ~/my-project # project-level instead of user-level
python3 install.py --link                 # symlink, so `git pull` updates it
python3 install.py --zip                  # dist/<skill>.zip, for uploading to a chat app
```

**`npx skills`:**

```bash
npx skills add ThaminduMiuranda/agent-skills --skill <skill>   # --list shows the skills; --skill '*' installs all
```

**Without cloning** (set `DEST` to your harness's skills folder):

```bash
SKILL=<skill>; DEST=~/.claude/skills
mkdir -p "$DEST" && curl -sL https://github.com/ThaminduMiuranda/agent-skills/archive/refs/heads/main.tar.gz \
  | tar -xz -C "$DEST" --strip-components=2 "agent-skills-main/skills/$SKILL"
```

**Or ask your agent:** "Install the `<skill>` skill from https://github.com/ThaminduMiuranda/agent-skills
(only its `skills/<skill>/` folder) wherever you load skills from."

| Harness                                   | User-level skills folder                  |
| ----------------------------------------- | ----------------------------------------- |
| Claude Code                               | `~/.claude/skills/`                       |
| Codex, OpenCode, other `AGENTS.md` agents | `~/.agents/skills/`                       |
| Antigravity (IDE and `agy` CLI)           | `~/.gemini/config/skills/`                |
| Gemini CLI (enterprise / API key)         | `~/.gemini/skills/`                       |
| anything else                             | wherever it loads `SKILL.md` folders from |

If an older skill with the same name is installed at user level, some harnesses load that copy in
preference to a newer project-level one. Replace it with `install.py --force`.

## Adding a skill

1. Create `skills/<name>/SKILL.md` (frontmatter `name` and `description`), plus any `scripts/`,
   `references/` and `assets/` the skill needs. `install.py` finds it automatically.
2. Write `docs/<name>.md` for humans.
3. Add a row to the table above.

## License

MIT, see [`LICENSE`](LICENSE).
