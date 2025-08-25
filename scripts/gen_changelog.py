#!/usr/bin/env python3
"""Generate release notes from conventional commits since previous tag.

Environment variables:
  CURRENT_TAG: tag name being released (vX.Y.Z)
  PREV_TAG: previous tag (may be empty)
  RANGE: git revision range (e.g. prev..HEAD or HEAD)
Output: writes markdown to stdout
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

current_tag = os.environ.get("CURRENT_TAG", "(unknown)")
prev_tag = os.environ.get("PREV_TAG", "")
range_spec = os.environ.get("RANGE", "HEAD")


def git_log(range_spec: str):
    out = subprocess.check_output(
        ["git", "log", "--pretty=format:%H%x01%s%x01%b%x02", range_spec], text=True
    )
    for block in out.split("\x02"):
        if not block.strip():
            continue
        parts = block.split("\x01")
        if len(parts) != 3:
            continue
        h, subject, body = parts
        yield h, subject.strip(), body.strip()


categories = ["feat", "fix", "perf", "docs", "refactor", "test", "build", "chore"]
titles = {
    "feat": "Features",
    "fix": "Fixes",
    "perf": "Performance",
    "refactor": "Refactoring",
    "docs": "Documentation",
    "test": "Tests",
    "build": "Build",
    "chore": "Chores",
}
cats = {c: [] for c in categories}
breaking = []
other = []
pattern = re.compile(
    r"^(?P<type>feat|fix|perf|docs|refactor|test|build|chore)(\(.+?\))?(!)?:\s*(?P<desc>.*)"
)

for h, subj, body in git_log(range_spec):
    m = pattern.match(subj)
    line = f"- {subj} ({h[:7]})"
    if m:
        t = m.group("type")
        cats[t].append(line)
        if "BREAKING CHANGE" in body or "!" in subj.split(":", 1)[0]:
            breaking.append(line)
    else:
        if subj:
            other.append(line)

content = [f"## {current_tag}"]
if prev_tag:
    content.append(f"_Changes since {prev_tag}_\n")
if breaking:
    content.append("### Breaking Changes\n" + "\n".join(breaking))
for key in categories:
    items = cats[key]
    if items:
        content.append(f"### {titles[key]}\n" + "\n".join(items))
if other:
    content.append("### Other\n" + "\n".join(other))

notes = "\n\n".join(content) + "\n"
sys.stdout.write(notes)
