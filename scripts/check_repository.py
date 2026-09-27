#!/usr/bin/env python3
"""Read-only repository hygiene checks; never import or run product packages."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = (
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".python-version",
    "README.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "bot/pyproject.toml",
    "bot/src/changgeun/__init__.py",
    "inference/pyproject.toml",
    "inference/src/changgeun_inference/__init__.py",
    "deploy/config.example.yaml",
    "deploy/profiles/jev-api.yaml",
    "deploy/profiles/mock.yaml",
    "deploy/bot.env.example",
    "deploy/gateway.env.example",
    "Plans/CHANGGEUN_DEVELOPMENT_SPEC_v1.3.md",
    "Plans/0.DevPhase/STATUS.md",
    "Plans/0.DevPhase/INFERENCE_PROFILES.md",
    ".github/workflows/repository-check.yml",
)
IGNORE_PROBES = (
    ".private/GitHub-info",
    ".private/Jev-API-key",
    ".private/ServerInfo",
    "nested/.private/credentials.json",
    ".env",
    ".env.production",
    "bot/.env.local",
    "deploy/bot.env",
    "deploy/gateway.env",
    "deploy/config.yaml",
    "deploy/profiles/jev-api.private.yaml",
    "bot/.venv/bin/python",
    "bot/src/changgeun/__pycache__/config.cpython-312.pyc",
    "inference/.venv-local/bin/python",
    "data/test/changgeun.sqlite3",
    "bot/request-ledger.sqlite3-wal",
    "bot/request-ledger.sqlite3-shm",
    "logs/bot.log",
    "backups/restore.dump",
    "offnode-backup.cms",
    "models/qwen/model.safetensors",
    "inference/.cache/model/tokenizer.json",
    "test_audio.wav",
    "private.pem",
    "evidence/0.5.0/01/jev-api/run/raw.json",
    "evidence/public/run/raw.log",
)
PUBLIC_PROBES = REQUIRED + (
    "tests/fixtures/synthetic-catalog.json",
    "bot/src/changgeun/storage/migrations/0001_schema.sql",
    "evidence/README.md",
    "evidence/public/README.md",
    "evidence/public/0.5.0/01/jev-api/run/summary.md",
)
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml", ".json", ".sql", ".sh"}
SECRET_PATTERNS = (
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("API secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    (
        "Discord token",
        re.compile(r"\b[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}\b"),
    ),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
)
ENV_SECRET = re.compile(
    r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD))\s*=\s*(.*?)\s*$"
)
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
REFERENCE_LINK = re.compile(r"^\[[^\]\n]+\]:\s*(\S+)", re.MULTILINE)


def git(*args: str, input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        input=input_bytes,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        # Do not echo subprocess stderr: repository configuration may contain secrets.
        raise RuntimeError(f"Git repository command failed (exit {result.returncode}).")
    return result.stdout


def ignored(paths: tuple[str, ...] | list[str]) -> set[str]:
    if not paths:
        return set()
    payload = b"\0".join(p.encode() for p in paths) + b"\0"
    result = subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "--no-index", "-z", "--stdin"],
        input=payload,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Could not inspect Git ignore rules.")
    return {p.decode() for p in result.stdout.split(b"\0") if p}


def anchors(markdown: str) -> set[str]:
    result = set(re.findall(r'(?:id|name)=["\x27]([^"\x27]+)["\x27]', markdown))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+)$", markdown, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug if not count else f"{slug}-{count}")
    return result


def check_credentials(name: str, text: str, errors: list[str], *, staged: bool = False) -> None:
    location = f"{name} (staged)" if staged else name
    path = Path(name)
    is_environment_example = path.name.endswith((".env.example", ".env.template")) or path.name in {
        ".env.example",
        ".env.template",
    }
    for number, line in enumerate(text.splitlines(), 1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                errors.append(f"{location}:{number}: possible {label} (value withheld)")
        match = ENV_SECRET.match(line) if is_environment_example else None
        if match:
            value = match[2].strip('"\x27')
            if value and not (value.startswith("<REPLACE_") and value.endswith(">")):
                errors.append(f"{location}:{number}: non-placeholder credential assignment")


def check_links(path: Path, text: str, errors: list[str]) -> int:
    count = 0
    outside_code = re.sub(r"^```.*?^```\s*$", "", text, flags=re.MULTILINE | re.DOTALL)
    targets = INLINE_LINK.findall(outside_code) + REFERENCE_LINK.findall(outside_code)
    for target in targets:
        if target.startswith("<"):
            target = target.split(">", 1)[0][1:]
        else:
            target = target.split(' "', 1)[0].split(" '", 1)[0]
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("//"):
            continue
        location, _, fragment = target.partition("#")
        destination = (path.parent / unquote(location)).resolve() if location else path
        count += 1
        if not destination.is_relative_to(ROOT):
            errors.append(f"{path.relative_to(ROOT)}: local link escapes the repository")
        elif ".private" in destination.relative_to(ROOT).parts:
            errors.append(f"{path.relative_to(ROOT)}: local link points to private input")
        elif not destination.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing local link {target}")
        elif fragment and destination.suffix == ".md":
            if unquote(fragment) not in anchors(destination.read_text(encoding="utf-8")):
                errors.append(f"{path.relative_to(ROOT)}: missing anchor {target}")
    return count


def main() -> int:
    errors: list[str] = []
    try:
        files = {
            p.decode()
            for p in git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split(
                b"\0"
            )
            if p
        }
        for required in REQUIRED:
            if required not in files or not (ROOT / required).is_file():
                errors.append(f"Missing public repository file: {required}")
        for probe in sorted(set(IGNORE_PROBES) - ignored(IGNORE_PROBES)):
            errors.append(f"Sensitive/runtime path is not ignored: {probe}")
        for probe in sorted(ignored(PUBLIC_PROBES)):
            errors.append(f"Public source/template is incorrectly ignored: {probe}")
        # This also catches ignored files that were force-added or previously tracked.
        excluded = ignored(sorted(files))
        for name in sorted(excluded):
            errors.append(f"Ignored path is included in the Git index: {name}")

        # Inspect index blobs too: a safe working copy can hide an earlier staged secret.
        for record in git("ls-files", "--stage", "-z").split(b"\0"):
            if not record:
                continue
            metadata, raw_name = record.split(b"\t", 1)
            mode, blob_id, stage = metadata.decode().split()
            name = raw_name.decode()
            if name in excluded or ".private" in Path(name).parts:
                continue
            if stage != "0" or mode != "100644" and mode != "100755":
                errors.append(f"Review non-regular or conflicted index entry: {name}")
                continue
            size = int(git("cat-file", "-s", blob_id).strip())
            if size > 1_048_576:
                errors.append(f"Review large staged file before publication: {name}")
                continue
            if Path(name).suffix in TEXT_SUFFIXES or name in REQUIRED or name.endswith(".example"):
                try:
                    staged_text = git("cat-file", "blob", blob_id).decode("utf-8")
                except UnicodeDecodeError:
                    errors.append(f"Expected UTF-8 staged text: {name}")
                    continue
                check_credentials(name, staged_text, errors, staged=True)

        inspected = links = tomls = json_examples = 0
        for name in sorted(files - excluded):
            if ".private" in Path(name).parts:
                errors.append("Private input directory is included in public Git candidates")
                continue
            path = ROOT / name
            if path.is_symlink():
                errors.append(f"Review symlink before publication: {name}")
                continue
            if not path.is_file():
                # Tracked deletions have no content to inspect.
                continue
            if path.stat().st_size > 1_048_576:
                errors.append(f"Review large file before publication: {name}")
                continue
            if not (
                path.suffix in TEXT_SUFFIXES or name in REQUIRED or path.name.endswith(".example")
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"Expected UTF-8 text: {name}")
                continue
            inspected += 1
            check_credentials(name, text, errors)
            if path.suffix == ".toml":
                try:
                    tomllib.loads(text)
                    tomls += 1
                except tomllib.TOMLDecodeError:
                    errors.append(f"Invalid TOML: {name}")
            elif path.suffix == ".json":
                try:
                    json.loads(text)
                except json.JSONDecodeError:
                    errors.append(f"Invalid JSON: {name}")
            elif path.suffix == ".md":
                links += check_links(path, text, errors)
                for block in re.findall(r"```json\n(.*?)\n```", text, re.DOTALL):
                    try:
                        json.loads(block)
                        json_examples += 1
                    except json.JSONDecodeError:
                        errors.append(f"Invalid Markdown JSON example: {name}")
    except (OSError, RuntimeError, UnicodeError):
        print("Repository inspection could not finish; no product operations were performed.")
        return 1
    if errors:
        print("Repository inspection failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Repository files OK: {len(files)} public candidates, {inspected} text files, "
        f"{links} local links, {tomls} TOML files, {json_examples} JSON examples."
    )
    print("Ignore/credential-pattern checks passed. This is not a product test result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
