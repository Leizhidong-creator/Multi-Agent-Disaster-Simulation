from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cff",
    ".css",
    ".env",
    ".example",
    ".html",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".text",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILENAMES = {"LICENSE", ".gitignore"}
CLI_EXCLUDED_PREFIXES = ("tests/", "docs/superpowers/")
PLACEHOLDERS = ("your_", "example_", "placeholder", "changeme", "omitted")


PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "openai_compatible_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "generic_credential": re.compile(
        r"(?im)^\s*(?:export\s+)?[\"']?(?:[A-Z][A-Z0-9_]*_)?"
        r"(?:API_KEY|TOKEN|SECRET|PASSWORD)[\"']?\s*[:=]\s*"
        r"[\"']?([A-Za-z0-9_./+=-]{20,})[\"']?\s*,?\s*$"
    ),
    "china_phone": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    "china_id": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str

    def render(self) -> str:
        return f"{self.rule}: {self.path}:{self.line}"


def scan_text(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for rule, pattern in PATTERNS.items():
            match = pattern.search(line)
            if not match:
                continue
            matched_text = match.group(0).lower()
            if rule == "generic_credential" and any(item in matched_text for item in PLACEHOLDERS):
                continue
            findings.append(Finding(path=path, line=line_number, rule=rule))
    return findings


def is_scannable(path: str) -> bool:
    normalized = path.replace("\\", "/")
    if normalized.startswith(CLI_EXCLUDED_PREFIXES):
        return False
    candidate = Path(normalized)
    return candidate.name in TEXT_FILENAMES or candidate.suffix.lower() in TEXT_SUFFIXES


def run_git(*args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def iter_worktree_texts() -> Iterable[tuple[str, str]]:
    output = str(run_git("ls-files", "--cached", "--others", "--exclude-standard"))
    for relative in sorted(set(output.splitlines())):
        if not is_scannable(relative):
            continue
        path = ROOT / relative
        if path.is_file():
            yield relative.replace("\\", "/"), path.read_text(encoding="utf-8", errors="replace")


def iter_staged_texts() -> Iterable[tuple[str, str]]:
    output = str(
        run_git(
            "diff",
            "--cached",
            "--no-ext-diff",
            "--unified=0",
            "--",
            ".",
            ":(exclude)tests/**",
            ":(exclude)docs/superpowers/**",
        )
    )
    added_lines = [line[1:] for line in output.splitlines() if line.startswith("+") and not line.startswith("+++")]
    if added_lines:
        yield "staged-diff", "\n".join(added_lines)


def iter_history_texts() -> Iterable[tuple[str, str]]:
    commits = str(run_git("rev-list", "HEAD")).splitlines()
    seen_blobs: set[str] = set()
    for commit in commits:
        tree = str(run_git("ls-tree", "-r", "--full-tree", commit))
        for entry in tree.splitlines():
            metadata, separator, path = entry.partition("\t")
            if not separator or not is_scannable(path):
                continue
            parts = metadata.split()
            if len(parts) < 3 or parts[1] != "blob":
                continue
            blob = parts[2]
            if blob in seen_blobs:
                continue
            seen_blobs.add(blob)
            content = bytes(run_git("cat-file", "blob", blob, text=False)).decode("utf-8", errors="replace")
            yield f"{path}@{blob[:12]}", content


def scan_items(items: Iterable[tuple[str, str]]) -> list[Finding]:
    findings: list[Finding] = []
    for path, content in items:
        findings.extend(scan_text(path, content))
    return findings


def print_result(label: str, findings: list[Finding]) -> bool:
    if not findings:
        print(f"PASS: no sensitive patterns found in {label}")
        return True
    print(f"FAIL: {len(findings)} sensitive pattern(s) found in {label}")
    for finding in findings:
        print(f"  {finding.render()}")
    return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan the public repository without echoing secret values.")
    parser.add_argument("--worktree", action="store_true", help="Scan tracked and untracked public files.")
    parser.add_argument("--staged", action="store_true", help="Scan added lines in the staged diff.")
    parser.add_argument("--history", action="store_true", help="Scan blobs reachable from HEAD.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    selected = args.worktree or args.staged or args.history
    checks = []
    if args.worktree or not selected:
        checks.append(("worktree", iter_worktree_texts()))
    if args.staged or not selected:
        checks.append(("staged diff", iter_staged_texts()))
    if args.history or not selected:
        checks.append(("reachable history", iter_history_texts()))

    passed = True
    for label, items in checks:
        passed = print_result(label, scan_items(items)) and passed
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
