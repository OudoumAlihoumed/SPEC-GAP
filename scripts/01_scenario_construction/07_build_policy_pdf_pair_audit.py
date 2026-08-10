#!/usr/bin/env python3
"""Build compact provenance for the Policy clean/injected PDF pair."""

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
SCHEMA_VERSION = "spec_gap.policy_pdf_pair_audit.v1"


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
    output = (result.stdout + result.stderr).strip().splitlines()
    return output[0]


def _archive_member(
    archive_path: Path,
    member_path: str,
) -> tuple[bytes, dict[str, Any]]:
    with zipfile.ZipFile(archive_path) as archive:
        info = archive.getinfo(member_path)
        payload = archive.read(info)
    return payload, {
        "member_path": member_path,
        "uncompressed_bytes": info.file_size,
        "compressed_bytes": info.compress_size,
        "crc32": f"{info.CRC:08x}",
        "sha256": _sha256_bytes(payload),
    }


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
            "Obtain the project Drive export with this exact archive filename "
            "and SHA-256; source PDFs are not committed to Git."
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
        raise ValueError("Policy PDF pair differs by more than one insertion")
    if clean[:prefix] + inserted + clean[prefix:] != injected:
        raise ValueError("Policy PDF pair insertion does not reconstruct injected text")
    return {
        "clean_byte_offset": prefix,
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


def build_audit(args: argparse.Namespace) -> dict[str, Any]:
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    clean_payload, clean_member = _archive_member(
        args.current_archive,
        args.clean_member,
    )
    injected_payload, injected_member = _archive_member(
        args.current_archive,
        args.injected_member,
    )
    old_clean_payload, old_clean_member = _archive_member(
        args.original_archive,
        args.original_clean_member,
    )
    original_payload, original_member = _archive_member(
        args.original_archive,
        args.original_injected_member,
    )
    if clean_payload != old_clean_payload:
        raise ValueError("clean carrier PDF changed between source archives")

    expected_hashes = registry["provenance"]["source_pdf_sha256"]
    adjustment = registry["provenance"]["injection_position_adjustment"]
    if clean_member["sha256"] != expected_hashes["policy_doc3_clean.pdf"]:
        raise ValueError("clean carrier PDF hash does not match registry")
    if injected_member["sha256"] != expected_hashes["policy_doc3_inj.pdf"]:
        raise ValueError("revised injected PDF hash does not match registry")
    if original_member["sha256"] != adjustment["original_injected_pdf_sha256"]:
        raise ValueError("original injected PDF hash does not match registry")

    with tempfile.TemporaryDirectory(prefix="policy_pdf_audit_") as directory:
        temp = Path(directory)
        clean_pdf = temp / "clean.pdf"
        injected_pdf = temp / "injected.pdf"
        original_pdf = temp / "original_injected.pdf"
        clean_pdf.write_bytes(clean_payload)
        injected_pdf.write_bytes(injected_payload)
        original_pdf.write_bytes(original_payload)
        clean_text = _extract_raw(clean_pdf, temp / "clean.txt")
        injected_text = _extract_raw(injected_pdf, temp / "injected.txt")
        original_text = _extract_raw(original_pdf, temp / "original.txt")
        current_delta = _single_insertion(clean_text, injected_text)
        original_delta = _single_insertion(clean_text, original_text)
        clean_pages = _rasterize(clean_pdf, temp / "clean_page")
        injected_pages = _rasterize(injected_pdf, temp / "injected_page")
        page_count = _page_count(clean_pdf)
        if _page_count(injected_pdf) != page_count:
            raise ValueError("clean and injected PDFs have different page counts")

    assigned = registry["assigned_wording"]
    expected_delta = (
        "\n" + registry["injection"]["wordings"][assigned]
    ).encode("utf-8")
    if current_delta["inserted_text"].encode("utf-8") != expected_delta:
        raise ValueError("revised PDF does not contain the exact registered delta")
    if original_delta["inserted_text"].encode("utf-8") != expected_delta:
        raise ValueError("original PDF does not contain the exact registered delta")
    tracked_clean_text = args.tracked_clean_text.read_bytes()
    if tracked_clean_text != clean_text:
        raise ValueError("tracked clean extraction does not match pdftotext -raw")
    if clean_pages != injected_pages:
        raise ValueError("clean and injected PDF raster outputs differ")

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": "2026-08-09",
        "domain_id": "policy",
        "carrier_doc_id": "policy_doc3",
        "method": {
            "text_extraction": "pdftotext -raw",
            "text_extractor_version": _tool_version("pdftotext"),
            "rasterization": "pdftoppm -r 96 -png",
            "rasterizer_version": _tool_version("pdftoppm"),
            "comparison": (
                "SHA-256 over each rendered PNG; exact equality required for "
                "all clean/revised-injected pages"
            ),
        },
        "source_archives": {
            "current_revised_export": _archive_binding(
                args.current_archive,
                [clean_member, injected_member],
            ),
            "original_export": _archive_binding(
                args.original_archive,
                [old_clean_member, original_member],
            ),
        },
        "pdf_hashes": {
            "clean": clean_member["sha256"],
            "revised_injected": injected_member["sha256"],
            "original_injected": original_member["sha256"],
        },
        "text_extraction": {
            "clean_bytes": len(clean_text),
            "clean_sha256": _sha256_bytes(clean_text),
            "tracked_clean_text_path": args.tracked_clean_text.relative_to(
                PROJECT_ROOT
            ).as_posix(),
            "tracked_clean_text_sha256": _sha256_file(args.tracked_clean_text),
            "revised_injected_bytes": len(injected_text),
            "revised_injected_sha256": _sha256_bytes(injected_text),
            "original_injected_bytes": len(original_text),
            "original_injected_sha256": _sha256_bytes(original_text),
            "revised_insertion": current_delta,
            "original_insertion": original_delta,
            "payload_preserved_exactly": True,
        },
        "render_audit": {
            "dpi": 96,
            "page_count": page_count,
            "all_pages_pixel_identical": True,
            "pages": clean_pages,
        },
        "limitations": [
            "The compact audit records hashes and derived comparisons, not the source PDFs themselves.",
            "Reproduction requires the two project Drive exports identified by exact filename and SHA-256.",
            "Pixel identity is specific to the recorded Poppler renderer and 96-DPI setting.",
        ],
    }


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=_path, required=True)
    parser.add_argument("--tracked-clean-text", type=_path, required=True)
    parser.add_argument("--current-archive", type=_path, required=True)
    parser.add_argument("--original-archive", type=_path, required=True)
    parser.add_argument("--clean-member", required=True)
    parser.add_argument("--injected-member", required=True)
    parser.add_argument("--original-clean-member", required=True)
    parser.add_argument("--original-injected-member", required=True)
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
