#!/usr/bin/env python3
"""Install skills from this repo into one or more agent harnesses, or build claude.ai upload zips.

  python3 install.py                          # every skill -> every harness found on this machine
  python3 install.py --target claude-code     # one harness (repeatable)
  python3 install.py --project .              # into the current project instead of your home folder
  python3 install.py --skill harness-comms --link   # symlink, so `git pull` updates it
  python3 install.py --zip                    # dist/<skill>.zip to upload to a chat app

Works on Linux, macOS and Windows (Python 3.9+, standard library only).
"""
import argparse
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent
SKILLS = REPO / "skills"
HOME = Path.home()

# harness -> (user-level folder, project-level folder)
TARGETS = {
    "claude-code": (HOME / ".claude/skills", ".claude/skills"),
    "agents": (HOME / ".agents/skills", ".agents/skills"),  # Codex, OpenCode, other AGENTS.md agents
    "codex": (HOME / ".codex/skills", ".agents/skills"),
    "gemini-cli": (HOME / ".gemini/skills", ".gemini/skills"),
    "antigravity": (HOME / ".gemini/config/skills", ".agents/skills"),
    "opencode": (HOME / ".config/opencode/skills", ".opencode/skills"),
}
# a harness counts as present when its config folder exists
PRESENT = {
    "claude-code": HOME / ".claude",
    "agents": HOME / ".agents",
    "codex": HOME / ".codex",
    "gemini-cli": HOME / ".gemini",
    "antigravity": HOME / ".gemini/config",
    "opencode": HOME / ".config/opencode",
}


def install(src, dest_dir, link, force):
    dest = dest_dir / src.name
    if dest.exists() or dest.is_symlink():
        if not force:
            return f"exists, skipped (use --force to replace): {dest}"
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    if link:
        dest.symlink_to(src, target_is_directory=True)
        return f"linked {dest} -> {src}"
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return f"copied to {dest}"


def build_zip(src, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{src.name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(src.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                zf.write(f, f"{src.name}/{f.relative_to(src).as_posix()}")
    return out


def main():
    skills = sorted(d.name for d in SKILLS.iterdir() if (d / "SKILL.md").is_file())
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", action="append", choices=skills, help="skill to install (default: all)")
    ap.add_argument("--target", action="append", choices=[*TARGETS, "all"],
                    help="harness (default: every one found on this machine)")
    ap.add_argument("--project", help="install into this project's folders instead of your home folder")
    ap.add_argument("--link", action="store_true", help="symlink instead of copy")
    ap.add_argument("--force", action="store_true", help="replace an existing install")
    ap.add_argument("--zip", action="store_true", help="only build dist/<skill>.zip for claude.ai")
    args = ap.parse_args()

    chosen = [SKILLS / s for s in (args.skill or skills)]
    if args.zip:
        for src in chosen:
            print(f"built {build_zip(src, REPO / 'dist')}  (upload it wherever your chat app takes skills, "
                  "e.g. claude.ai -> Settings -> Capabilities -> Skills)")
        return 0

    if args.target and "all" in args.target:
        targets = list(TARGETS)
    elif args.target:
        targets = args.target
    else:
        targets = [t for t in TARGETS if PRESENT[t].is_dir()]
        if not targets:
            sys.exit("No harness folders found; pass --target explicitly.")

    seen = set()
    for t in targets:
        user_dir, project_dir = TARGETS[t]
        dest_dir = Path(args.project).resolve() / project_dir if args.project else user_dir
        if dest_dir in seen:
            continue
        seen.add(dest_dir)
        for src in chosen:
            print(f"[{t}] {install(src, dest_dir, args.link, args.force)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
