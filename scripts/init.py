#!/usr/bin/env python3
"""Bootstrap a fresh project from this seed/template repo.

Run once, right after creating a repo from the template:

    python scripts/init.py --name acme
    python scripts/init.py --name acme --display "Acme Inc" --fresh-git

It rewrites the seed's identity (``shipyard`` / ``Shipyard``) to your project's
across every tracked text file, resets the package version, writes a ``.env``
with a freshly generated ``SECRET_KEY``, and clears the seed's project-status
notes. It is safe to read before running — it only touches files git tracks and
prints exactly what it changed.
"""

from __future__ import annotations

import argparse
import re
import secrets
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Tracked files we never rewrite: this script, lockfiles we'd rather regenerate,
# and anything binary. Lockfiles still get the package-name rename below because
# the dependency name lives in them, but we skip free-text doc resets there.
SKIP_REWRITE = {
    "scripts/init.py",
}

# Files whose *entire* contents are project history, not reusable architecture.
# These get a fresh stub instead of an in-place rename.
STATUS_HEADING = "## Status"


def derive(slug: str, display: str | None) -> tuple[str, str, str]:
    """Return (lower_slug, Title_display, UPPER) used for the three case styles."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", slug):
        sys.exit(
            f"--name must be a lowercase slug ([a-z][a-z0-9_-]*); got {slug!r}.\n"
            "It becomes the Python/DB/bucket identifier, so keep it simple."
        )
    title = display or slug.replace("-", " ").replace("_", " ").title().replace(" ", "")
    return slug, title, slug.upper()


def rewrite_identity(slug: str, title: str, upper: str) -> list[str]:
    """Replace shipyard/Shipyard/SHIPYARD across tracked text files."""
    subs = [("SHIPYARD", upper), ("Shipyard", title), ("shipyard", slug)]
    changed: list[str] = []
    files = subprocess.check_output(
        ["git", "ls-files"], cwd=REPO, text=True
    ).splitlines()
    for rel in files:
        if rel in SKIP_REWRITE:
            continue
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # binary or removed
        new = text
        for old, repl in subs:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(rel)
    return changed


def reset_version() -> bool:
    """Reset the package version to 0.1.0 in pyproject.toml."""
    pyproject = REPO / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    new = re.sub(r'(?m)^version = "[^"]*"', 'version = "0.1.0"', text, count=1)
    if new != text:
        pyproject.write_text(new, encoding="utf-8")
        return True
    return False


def write_env(title: str) -> bool:
    """Create .env from .env.example with a real SECRET_KEY. No-op if .env exists."""
    env = REPO / ".env"
    if env.exists():
        return False
    example = (REPO / ".env.example").read_text(encoding="utf-8")
    key = secrets.token_urlsafe(48)
    out = re.sub(r"(?m)^SECRET_KEY=.*$", f"SECRET_KEY={key}", example)
    env.write_text(out, encoding="utf-8")
    return True


def reset_status(title: str) -> list[str]:
    """Replace the per-project '## Status' block in CLAUDE.md with a clean start."""
    touched: list[str] = []
    claude = REPO / "CLAUDE.md"
    if claude.exists():
        text = claude.read_text(encoding="utf-8")
        idx = text.find(STATUS_HEADING)
        if idx != -1:
            fresh = (
                f"{STATUS_HEADING}\n\nFresh project scaffolded from the "
                f"{title} seed template. Inherits the boilerplate's features "
                "(auth, teams, billing, notifications, files); build from here.\n"
            )
            claude.write_text(text[:idx] + fresh, encoding="utf-8")
            touched.append("CLAUDE.md")
    return touched


def fresh_git(slug: str) -> None:
    """Drop seed history and start a new repo with one initial commit."""
    git_dir = REPO / ".git"
    if git_dir.exists():
        subprocess.run(["rm", "-rf", str(git_dir)], check=True)
    subprocess.run(["git", "init", "-q"], cwd=REPO, check=True)
    subprocess.run(["git", "add", "-A"], cwd=REPO, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", f"Initial commit ({slug}, from seed template)"],
        cwd=REPO,
        check=True,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Initialize a project from the seed template.")
    ap.add_argument("--name", required=True, help="Project slug, e.g. 'acme' (lowercase).")
    ap.add_argument("--display", help="Display name, e.g. 'Acme Inc'. Defaults from --name.")
    ap.add_argument(
        "--fresh-git",
        action="store_true",
        help="Delete seed git history and create a fresh initial commit.",
    )
    args = ap.parse_args()

    slug, title, upper = derive(args.name, args.display)
    print(f"Seeding project: slug={slug!r} display={title!r}\n")

    changed = rewrite_identity(slug, title, upper)
    print(f"  ✓ renamed shipyard → {slug} ({len(changed)} files)")
    print(f"  ✓ renamed Shipyard → {title}")
    print(f"  ✓ pyproject version → 0.1.0" if reset_version() else "  · version unchanged")
    print("  ✓ wrote .env with a fresh SECRET_KEY" if write_env(title) else "  · .env exists, left as-is")
    for f in reset_status(title):
        print(f"  ✓ reset status block in {f}")

    if args.fresh_git:
        fresh_git(slug)
        print(f"  ✓ fresh git history (initial commit)")
    else:
        print("  · kept existing git history (pass --fresh-git to reset)")

    print(
        "\nNext steps:\n"
        "  1. Review README.md and docs/PLAN.md — trim the seed's design notes.\n"
        "  2. Delete scripts/init.py (one-shot; you won't need it again).\n"
        "  3. uv venv && uv pip install -e \".[dev]\" && .venv/bin/python -m pytest -q\n"
    )


if __name__ == "__main__":
    main()
