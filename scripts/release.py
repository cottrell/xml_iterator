#!/usr/bin/env python
"""One-shot release: bump Cargo version + CHANGELOG, commit, tag (optional push).

Package version is **only** in Cargo.toml (pyproject is dynamic). CI publishes to
PyPI when a ``v*`` tag is pushed — the tag must match Cargo or the wheel is wrong.

Usage:
  python scripts/release.py patch              # 0.2.13 → 0.2.14, commit + tag
  python scripts/release.py minor
  python scripts/release.py major
  python scripts/release.py 0.3.0             # explicit version
  python scripts/release.py patch --push      # also push main + tag (triggers PyPI)
  python scripts/release.py patch --push --gh-release
  python scripts/release.py patch -m "fix foo" -m "bench bar"
  python scripts/release.py --dry-run patch

Does not run tests; CI does that on the tag.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARGO = ROOT / "Cargo.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
VERSION_RE = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"\s*$', re.M)


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def current_version() -> str:
    text = CARGO.read_text(encoding="utf-8")
    m = VERSION_RE.search(text)
    if not m:
        die(f'no version = "x.y.z" in {CARGO}')
    return m.group(1)


def parse_ver(s: str) -> tuple[int, int, int]:
    parts = s.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        die(f"bad version {s!r} (want X.Y.Z)")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump(ver: str, kind: str) -> str:
    major, minor, patch = parse_ver(ver)
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    die(f"unknown bump {kind!r}")


def set_cargo_version(new: str) -> None:
    text = CARGO.read_text(encoding="utf-8")
    new_text, n = VERSION_RE.subn(f'version = "{new}"', text, count=1)
    if n != 1:
        die("failed to rewrite Cargo.toml version")
    CARGO.write_text(new_text, encoding="utf-8")


def prepend_changelog(new: str, notes: list[str]) -> None:
    today = date.today().isoformat()
    bullets = notes or ["(describe changes)"]
    body = "\n".join(f"- {b}" for b in bullets)
    block = f"## {new} ({today})\n\n{body}\n\n"
    text = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Changelog\n\n"
    if re.search(rf"^## {re.escape(new)}\b", text, re.M):
        die(f"CHANGELOG already has section ## {new}")
    if text.lstrip().startswith("#"):
        # insert after first heading line
        lines = text.splitlines(keepends=True)
        out = []
        inserted = False
        for i, line in enumerate(lines):
            out.append(line)
            if not inserted and line.startswith("# ") and i == 0:
                # skip blank lines after title
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    out.append(lines[j])
                    j += 1
                out.append(block)
                out.extend(lines[j:])
                inserted = True
                break
        if not inserted:
            out = [block, text]
        CHANGELOG.write_text("".join(out) if inserted else block + text, encoding="utf-8")
    else:
        CHANGELOG.write_text("# Changelog\n\n" + block + text, encoding="utf-8")


def git_ok_for_release(*, allow_dirty: bool) -> None:
    r = run(["git", "status", "--porcelain"])
    dirty = [ln for ln in r.stdout.splitlines() if ln.strip()]
    # allow only our files after we edit? check before edit
    if dirty and not allow_dirty:
        die("working tree not clean — commit/stash first, or pass --allow-dirty")
    r = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = r.stdout.strip()
    if branch not in ("main", "master") and not allow_dirty:
        print(f"warning: on branch {branch!r} (expected main)", file=sys.stderr)


def tag_exists(tag: str) -> bool:
    r = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], check=False)
    return r.returncode == 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "version",
        help="patch | minor | major | X.Y.Z",
    )
    p.add_argument("-m", "--message", action="append", default=[], help="CHANGELOG bullet (repeatable)")
    p.add_argument("--dry-run", action="store_true", help="print actions only")
    p.add_argument("--push", action="store_true", help="git push origin HEAD and tag")
    p.add_argument("--gh-release", action="store_true", help="gh release create (after --push)")
    p.add_argument("--allow-dirty", action="store_true", help="allow dirty tree / non-main branch")
    p.add_argument("--no-commit", action="store_true", help="only edit files (no git commit/tag)")
    args = p.parse_args()

    cur = current_version()
    if args.version in ("patch", "minor", "major"):
        new = bump(cur, args.version)
    else:
        new = args.version.lstrip("v")
        parse_ver(new)
        if parse_ver(new) <= parse_ver(cur):
            die(f"new version {new} must be greater than current {cur}")

    tag = f"v{new}"
    print(f"{cur} → {new}  (tag {tag})")

    if not args.dry_run and not args.no_commit:
        git_ok_for_release(allow_dirty=args.allow_dirty)
    if tag_exists(tag) and not args.dry_run:
        die(f"tag {tag} already exists")

    if args.dry_run:
        print(f"would set Cargo.toml version = {new}")
        print(f"would prepend CHANGELOG ## {new}")
        if not args.no_commit:
            print(f'would commit "Release {new}" and tag -a {tag}')
        if args.push:
            print("would push origin HEAD and tag")
        if args.gh_release:
            print(f"would gh release create {tag}")
        return

    set_cargo_version(new)
    prepend_changelog(new, args.message)
    print(f"updated {CARGO.relative_to(ROOT)}")
    print(f"updated {CHANGELOG.relative_to(ROOT)}")

    if args.no_commit:
        print("stopped before commit (--no-commit)")
        return

    run(["git", "add", str(CARGO), str(CHANGELOG)])
    msg = f"Release {new}\n\nAgent: Grok release script.\n"
    run(["git", "commit", "-m", msg])
    run(["git", "tag", "-a", tag, "-m", f"{tag}: release"])
    print(f"committed and tagged {tag}")

    if args.push:
        run(["git", "push", "origin", "HEAD"])
        run(["git", "push", "origin", tag])
        print(f"pushed HEAD and {tag} → CI will publish to PyPI if secret is set")

    if args.gh_release:
        if not args.push:
            die("--gh-release needs --push (or push the tag yourself first)")
        notes = CHANGELOG.read_text(encoding="utf-8")
        # extract section for this version only
        m = re.search(
            rf"## {re.escape(new)}.*?(?=\n## |\Z)",
            notes,
            re.S,
        )
        body = m.group(0).strip() if m else f"Release {new}"
        r = run(
            [
                "gh",
                "release",
                "create",
                tag,
                "--title",
                tag,
                "--notes",
                body,
            ],
            check=False,
        )
        if r.returncode != 0:
            print(r.stderr or r.stdout, file=sys.stderr)
            die("gh release create failed")
        print(f"GitHub release {tag} created")

    print(f"\nNext: gh run watch   # wait for tag CI / Release job\nPyPI: https://pypi.org/project/xml-iterator/{new}/")


if __name__ == "__main__":
    main()
