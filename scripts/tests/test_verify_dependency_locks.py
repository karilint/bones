from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from scripts.verify_dependency_locks import compare_locks, normalize_lock


LOCK = """\
# generated lock
ruff==0.16.3 \\
    --hash=sha256:first \\
    --hash=sha256:second
    # via requirements-ci.in
"""


class NormalizeLockTests(TestCase):
    def test_repeated_hash_for_same_package_is_ignored(self):
        duplicated = LOCK.replace(
            "    --hash=sha256:first \\\n",
            "    --hash=sha256:first \\\n    --hash=sha256:first \\\n",
        )

        self.assertEqual(normalize_lock(LOCK), normalize_lock(duplicated))

    def test_same_hash_in_separate_packages_is_preserved(self):
        content = "one==1 \\\n    --hash=sha256:same\ntwo==2 \\\n    --hash=sha256:same\n"

        self.assertEqual(normalize_lock(content).count("sha256:same"), 2)

    def test_version_change_is_not_equivalent(self):
        self.assertNotEqual(normalize_lock(LOCK), normalize_lock(LOCK.replace("0.16.3", "0.16.4")))

    def test_missing_hash_is_not_equivalent(self):
        self.assertNotEqual(
            normalize_lock(LOCK),
            normalize_lock(LOCK.replace("    --hash=sha256:second\n", "")),
        )

    def test_compare_locks_accepts_only_duplicate_hash_drift(self):
        with TemporaryDirectory() as directory:
            committed = Path(directory, "committed.txt")
            generated = Path(directory, "generated.txt")
            committed.write_text(LOCK + "    --hash=sha256:second\n", encoding="utf-8")
            generated.write_text(LOCK, encoding="utf-8")

            self.assertTrue(compare_locks(committed, generated))
