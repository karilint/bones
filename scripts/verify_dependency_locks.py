"""Compare generated dependency locks while tolerating duplicate hashes."""

from __future__ import annotations

import difflib
import sys
from pathlib import Path


def normalize_lock(content: str) -> str:
    """Return a lock representation with repeated hashes removed per package."""
    normalized: list[str] = []
    package_hashes: set[str] = set()

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("--hash="):
            if stripped in package_hashes:
                continue
            package_hashes.add(stripped)
        elif line and not line[0].isspace() and not line.startswith("#"):
            package_hashes.clear()
        normalized.append(line)

    return "\n".join(normalized) + "\n"


def compare_locks(committed: Path, generated: Path) -> bool:
    """Compare one committed/generated pair and print a useful diff on drift."""
    committed_text = normalize_lock(committed.read_text(encoding="utf-8"))
    generated_text = normalize_lock(generated.read_text(encoding="utf-8"))
    if committed_text == generated_text:
        return True

    sys.stderr.writelines(
        difflib.unified_diff(
            committed_text.splitlines(keepends=True),
            generated_text.splitlines(keepends=True),
            fromfile=str(committed),
            tofile=str(generated),
        )
    )
    return False


def main(arguments: list[str]) -> int:
    """Compare committed/generated path pairs supplied on the command line."""
    if not arguments or len(arguments) % 2:
        print(
            "usage: verify_dependency_locks.py COMMITTED GENERATED [...]",
            file=sys.stderr,
        )
        return 2

    matches = True
    for index in range(0, len(arguments), 2):
        matches &= compare_locks(Path(arguments[index]), Path(arguments[index + 1]))
    return 0 if matches else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
