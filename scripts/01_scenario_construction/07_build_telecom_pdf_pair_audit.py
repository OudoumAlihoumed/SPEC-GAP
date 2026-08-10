#!/usr/bin/env python3
"""Build compact provenance for the Telecom clean/injected PDF pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "spec_gap.telecom_pdf_pair_audit.v1"

CURRENT_MEMBERS = {
    "handoff": "scenario_1_and_7/trajectory_file/telecom_trajectory.json",
    "doc1_clean": (
        "scenario_1_and_7/match_pair_domain_files/telecom/telecom_doc1_clean.pdf"
    ),
    "doc2_clean": (
        "scenario_1_and_7/match_pair_domain_files/telecom/telecom_doc2_clean.pdf"
    ),
    "doc3_clean": (
        "scenario_1_and_7/match_pair_domain_files/telecom/telecom_doc3_clean.pdf"
    ),
    "doc3_injected": (
        "scenario_1_and_7/match_pair_domain_files/telecom/telecom_doc3_inj.pdf"
    ),
    "doc4_archived": (
        "scenario_1_and_7/match_pair_domain_files/telecom/telecom_doc4_clean.pdf"
    ),
}
ORIGINAL_MEMBERS = {
    "handoff": "trajectory_file/telecom_trajectory.json",
    "doc3_clean": ("match_pair_domain_files/telecom/telecom_doc3_clean.pdf"),
    "doc3_injected": ("match_pair_domain_files/telecom/telecom_doc3_inj.pdf"),
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _tool_version(command: str) -> str:
    result = subprocess.run(
        [command, "-v"],
        check=True,
        capture_output=True,
        text=True,
    )
    return (result.stdout + result.stderr).strip().splitlines()[0]


def _archive_members(
    archive_path: Path,
    member_paths: dict[str, str],
) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    payloads = {}
    records = []
    with zipfile.ZipFile(archive_path) as archive:
        for role, member_path in member_paths.items():
            info = archive.getinfo(member_path)
            payload = archive.read(info)
            payloads[role] = payload
            records.append(
                {
                    "role": role,
                    "member_path": member_path,
                    "uncompressed_bytes": info.file_size,
                    "compressed_bytes": info.compress_size,
                    "crc32": f"{info.CRC:08x}",
                    "sha256": _sha256_bytes(payload),
                }
            )
    return payloads, records


def _archive_binding(
    archive_path: Path,
    members: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "archive_filename": archive_path.name,
        "archive_sha256": _sha256_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "members": members,
        "access_requirement": (
            "Obtain the project Drive export with this exact filename and "
            "SHA-256; source PDFs are not committed to Git."
        ),
    }


def _extract_raw(pdf_path: Path, destination: Path) -> bytes:
    subprocess.run(
        ["pdftotext", "-raw", str(pdf_path), str(destination)],
        check=True,
        capture_output=True,
    )
    return destination.read_bytes()


def _single_insertion(clean: bytes, injected: bytes) -> dict[str, Any]:
    prefix = 0
    limit = min(len(clean), len(injected))
    while prefix < limit and clean[prefix] == injected[prefix]:
        prefix += 1
    suffix = 0
    clean_remaining = len(clean) - prefix
    injected_remaining = len(injected) - prefix
    while (
        suffix < clean_remaining
        and suffix < injected_remaining
        and clean[len(clean) - 1 - suffix] == injected[len(injected) - 1 - suffix]
    ):
        suffix += 1
    clean_delta_end = len(clean) - suffix
    injected_delta_end = len(injected) - suffix
    removed = clean[prefix:clean_delta_end]
    inserted = injected[prefix:injected_delta_end]
    if removed:
        raise ValueError("Telecom PDF pair differs by more than one insertion")
    if clean[:prefix] + inserted + clean[prefix:] != injected:
        raise ValueError("Telecom PDF insertion does not reconstruct injected text")
    return {
        "clean_byte_offset": prefix,
        "clean_character_offset_utf8": len(clean[:prefix].decode("utf-8")),
        "removed_bytes": len(removed),
        "inserted_bytes": len(inserted),
        "inserted_text": inserted.decode("utf-8"),
        "inserted_text_sha256": _sha256_bytes(inserted),
        "reconstruction_exact": True,
    }


def _page_count(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise ValueError("pdfinfo did not report a page count")


def _rasterize(pdf_path: Path, prefix: Path) -> list[dict[str, Any]]:
    subprocess.run(
        ["pdftoppm", "-r", "96", "-png", str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
    )
    pages = sorted(prefix.parent.glob(f"{prefix.name}-*.png"))
    return [
        {
            "page": index,
            "png_sha256": _sha256_file(path),
            "png_bytes": path.stat().st_size,
        }
        for index, path in enumerate(pages, start=1)
    ]


def _member_by_role(
    members: list[dict[str, Any]],
    role: str,
) -> dict[str, Any]:
    return next(item for item in members if item["role"] == role)


def build_audit(args: argparse.Namespace) -> dict[str, Any]:
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    provenance = registry["provenance"]
    adjustment = provenance["injection_position_adjustment"]
    current_payloads, current_members = _archive_members(
        args.current_archive,
        CURRENT_MEMBERS,
    )
    original_payloads, original_members = _archive_members(
        args.original_archive,
        ORIGINAL_MEMBERS,
    )
    if current_payloads["doc3_clean"] != original_payloads["doc3_clean"]:
        raise ValueError("clean carrier PDF changed between source archives")

    if _sha256_file(args.current_archive) != provenance["source_archive_sha256"]:
        raise ValueError("current source archive hash does not match registry")
    original_binding = adjustment["original_source_archive"]
    if args.original_archive.name != original_binding["filename"]:
        raise ValueError("original source archive filename does not match registry")
    if _sha256_file(args.original_archive) != original_binding["sha256"]:
        raise ValueError("original source archive hash does not match registry")

    expected_pdfs = provenance["source_pdf_sha256"]
    expected_current = {
        "handoff": provenance["source_handoff_sha256"],
        "doc1_clean": expected_pdfs["telecom_doc1_clean.pdf"],
        "doc2_clean": expected_pdfs["telecom_doc2_clean.pdf"],
        "doc3_clean": expected_pdfs["telecom_doc3_clean.pdf"],
        "doc3_injected": expected_pdfs["telecom_doc3_inj.pdf"],
        "doc4_archived": provenance["archived_not_active"][0]["sha256"],
    }
    for role, expected in expected_current.items():
        if _member_by_role(current_members, role)["sha256"] != expected:
            raise ValueError(f"current archive member hash mismatch: {role}")
    if (
        _member_by_role(original_members, "handoff")["sha256"]
        != (original_binding["handoff_sha256"])
    ):
        raise ValueError("original handoff hash does not match registry")
    if (
        _member_by_role(original_members, "doc3_injected")["sha256"]
        != (adjustment["original_injected_pdf_sha256"])
    ):
        raise ValueError("original injected PDF hash does not match registry")

    with tempfile.TemporaryDirectory(prefix="telecom_pdf_audit_") as directory:
        temp = Path(directory)
        pdf_paths = {}
        for role in ("doc1_clean", "doc2_clean", "doc3_clean", "doc3_injected"):
            pdf_paths[role] = temp / f"{role}.pdf"
            pdf_paths[role].write_bytes(current_payloads[role])
        pdf_paths["original_doc3_injected"] = temp / "original_doc3_injected.pdf"
        pdf_paths["original_doc3_injected"].write_bytes(
            original_payloads["doc3_injected"]
        )

        extracted = {
            role: _extract_raw(path, temp / f"{role}.txt")
            for role, path in pdf_paths.items()
        }
        revised_delta = _single_insertion(
            extracted["doc3_clean"],
            extracted["doc3_injected"],
        )
        original_delta = _single_insertion(
            extracted["doc3_clean"],
            extracted["original_doc3_injected"],
        )
        clean_pages = _rasterize(
            pdf_paths["doc3_clean"],
            temp / "clean_page",
        )
        revised_pages = _rasterize(
            pdf_paths["doc3_injected"],
            temp / "revised_page",
        )
        original_pages = _rasterize(
            pdf_paths["original_doc3_injected"],
            temp / "original_page",
        )
        page_count = _page_count(pdf_paths["doc3_clean"])
        if {
            _page_count(pdf_paths["doc3_injected"]),
            _page_count(pdf_paths["original_doc3_injected"]),
            page_count,
        } != {page_count}:
            raise ValueError("clean and injected PDFs have different page counts")

    expected_delta = (
        "\n" + registry["injection"]["wordings"][registry["assigned_wording"]]
    ).encode("utf-8")
    if revised_delta["inserted_text"].encode("utf-8") != expected_delta:
        raise ValueError("revised PDF does not contain the registered delta")
    if original_delta["inserted_text"].encode("utf-8") != expected_delta:
        raise ValueError("original PDF does not contain the registered delta")
    if clean_pages != revised_pages or clean_pages != original_pages:
        raise ValueError("clean and injected PDF raster outputs differ")
    page_records = [
        {
            "page": clean["page"],
            "clean_png_sha256": clean["png_sha256"],
            "revised_injected_png_sha256": revised["png_sha256"],
            "original_injected_png_sha256": original["png_sha256"],
            "png_bytes": clean["png_bytes"],
            "all_equal": True,
        }
        for clean, revised, original in zip(
            clean_pages,
            revised_pages,
            original_pages,
            strict=True,
        )
    ]

    tracked_texts = {}
    for index, role in enumerate(("doc1_clean", "doc2_clean", "doc3_clean"), start=1):
        path = args.tracked_documents / f"telecom_doc{index}_clean.txt"
        if path.read_bytes() != extracted[role]:
            raise ValueError(f"tracked clean extraction does not match {role}")
        tracked_texts[role] = {
            "path": path.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": len(extracted[role]),
            "sha256": _sha256_bytes(extracted[role]),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": "2026-08-09",
        "domain_id": "telecom",
        "carrier_doc_id": "telecom_doc3",
        "method": {
            "text_extraction": "pdftotext -raw",
            "text_extractor_version": _tool_version("pdftotext"),
            "rasterization": "pdftoppm -r 96 -png",
            "rasterizer_version": _tool_version("pdftoppm"),
            "comparison": (
                "SHA-256 over each rendered PNG; exact equality required for "
                "all clean/revised/original-injected pages."
            ),
        },
        "source_archives": {
            "current_revised_export": _archive_binding(
                args.current_archive,
                current_members,
            ),
            "original_export": _archive_binding(
                args.original_archive,
                original_members,
            ),
        },
        "tracked_clean_texts": tracked_texts,
        "pdf_hashes": {
            "clean": _member_by_role(current_members, "doc3_clean")["sha256"],
            "revised_injected": _member_by_role(
                current_members,
                "doc3_injected",
            )["sha256"],
            "original_injected": _member_by_role(
                original_members,
                "doc3_injected",
            )["sha256"],
        },
        "text_extraction": {
            "clean_bytes": len(extracted["doc3_clean"]),
            "clean_sha256": _sha256_bytes(extracted["doc3_clean"]),
            "revised_injected_bytes": len(extracted["doc3_injected"]),
            "revised_injected_sha256": _sha256_bytes(extracted["doc3_injected"]),
            "original_injected_bytes": len(extracted["original_doc3_injected"]),
            "original_injected_sha256": _sha256_bytes(
                extracted["original_doc3_injected"]
            ),
            "revised_insertion": revised_delta,
            "original_insertion": original_delta,
            "payload_preserved_exactly": True,
        },
        "render_audit": {
            "dpi": 96,
            "page_count": page_count,
            "revised_all_pages_pixel_identical": True,
            "original_all_pages_pixel_identical": True,
            "pages": page_records,
        },
        "limitations": [
            "The compact audit records hashes and comparisons, not source PDFs.",
            "Reproduction requires both exact project Drive exports.",
            "Pixel identity is specific to the recorded Poppler renderer and 96 DPI.",
        ],
    }


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=_path, required=True)
    parser.add_argument("--tracked-documents", type=_path, required=True)
    parser.add_argument("--current-archive", type=_path, required=True)
    parser.add_argument("--original-archive", type=_path, required=True)
    parser.add_argument("--out", type=_path, required=True)
    args = parser.parse_args()

    audit = build_audit(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
