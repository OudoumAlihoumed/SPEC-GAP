"""Guard the repository's canonical names and rename provenance metadata."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = (
    "aihc",
    "convex_open_access_v3",
    "fin",
    "kg",
    "macro",
    "neuro",
    "petro",
    "policy",
    "telecom",
)
PACKAGE_ROOT = ROOT / "experiments" / "scenario1" / "inputs" / "fellow_packages"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_root_readme_is_the_only_readme() -> None:
    readmes = sorted(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("README*")
        if path.is_file()
        and not {".git", ".pytest_cache", ".venv"}.intersection(path.parts)
    )
    assert readmes == ["README.md"]


def test_renamed_text_files_explain_identity_date_and_purpose() -> None:
    renamed_text_files = (
        ROOT / "archive" / "scenario1_v3" / "ARCHIVE_NOTES.md",
        PACKAGE_ROOT / "neuro" / "LICENSE_NOTICE.md",
        ROOT / "tests" / "test_aihc_package.py",
        ROOT / "tests" / "test_convex_package.py",
        ROOT / "tests" / "test_knowledge_graphs_package.py",
        ROOT / "tests" / "test_neuro_package.py",
        ROOT / "tests" / "test_petroleum_package.py",
    )
    for path in renamed_text_files:
        header = "\n".join(path.read_text(encoding="utf-8").splitlines()[:10])
        assert "filename:" in header.lower() or "renamed from:" in header.lower()
        assert "original date:" in header.lower()
        assert "renamed on: 2026-08-10" in header.lower()
        assert "purpose:" in header.lower()


def test_every_active_domain_uses_stable_intuitive_names() -> None:
    for package in PACKAGES:
        root = PACKAGE_ROOT / package
        for relative in (
            Path("domain_config.json"),
            Path("retrieval/plan.json"),
            Path("retrieval/context_check.json"),
        ):
            path = root / relative
            assert path.is_file(), path
            assert "gen5000" not in path.name
            assert not path.name.startswith("qwen_")


def test_every_renamed_json_preserves_its_identity_and_purpose() -> None:
    renamed_files = []
    for path in (ROOT / "experiments" / "scenario1" / "inputs").rglob("*.json"):
        payload = _load_json(path)
        info = payload.get("_file_info")
        if info is None:
            continue
        renamed_files.append(path)
        assert next(iter(payload)) == "_file_info"
        assert set(info) == {
            "renamed_from",
            "original_date",
            "renamed_on",
            "purpose",
        }
        assert info["renamed_from"]
        assert info["renamed_on"] == "2026-08-10"
        assert info["purpose"].strip()
        assert Path(info["renamed_from"]).name != path.name
        former_date = re.search(
            r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)",
            info["renamed_from"],
        )
        if former_date:
            assert info["original_date"] == "-".join(former_date.groups())
        else:
            assert info["original_date"] is None

    assert len(renamed_files) == 44


def test_obsolete_active_filenames_do_not_remain_in_package_inputs() -> None:
    obsolete_fragments = (
        "registry_gen5000_v2.json",
        "full_corpus_bm25_balanced_gen5000_v2.json",
        "qwen_context_preflight_balanced_gen5000_v2.json",
        "pdf_pair_audit_gen5000_v2.json",
    )
    relative_paths = [
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
    ]
    for fragment in obsolete_fragments:
        assert all(fragment not in path for path in relative_paths)
