# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZipInfo

from ..models import AnalysisLimits


class AnalysisLimitError(ValueError):
    pass


def _zip_member_is_symlink(member: ZipInfo) -> bool:
    mode = member.external_attr >> 16
    return (mode & 0o170000) == 0o120000


def validate_archive(archive: ZipFile, limits: AnalysisLimits) -> None:
    members = archive.infolist()
    if len(members) > limits.max_zip_members:
        raise AnalysisLimitError(
            "Archive contains too many entries "
            f"({len(members)} > {limits.max_zip_members})."
        )

    total_uncompressed = 0
    for member in members:
        name = member.filename
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise AnalysisLimitError(f"Archive contains unsafe path {name!r}.")

        if _zip_member_is_symlink(member):
            raise AnalysisLimitError(f"Archive contains symlink entry {name!r}.")

        if member.is_dir():
            continue

        if member.file_size > limits.max_file_size_bytes:
            raise AnalysisLimitError(
                f"Archive member {name!r} exceeds file size limit."
            )

        total_uncompressed += member.file_size
        if total_uncompressed > limits.max_zip_uncompressed_bytes:
            raise AnalysisLimitError("Archive exceeds uncompressed size limit.")

        if member.compress_size == 0:
            if member.file_size > 0:
                raise AnalysisLimitError(
                    f"Archive member {name!r} has invalid compression ratio."
                )
            continue

        ratio = member.file_size / member.compress_size
        if ratio > limits.max_zip_compression_ratio:
            raise AnalysisLimitError(
                f"Archive member {name!r} exceeds compression ratio limit."
            )


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def walk_regular_files(root: Path, limits: AnalysisLimits) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    total_size = 0

    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if not _is_within_root(path, root):
            continue

        size = path.stat().st_size
        if size > limits.max_file_size_bytes:
            raise AnalysisLimitError(f"File {path.name!r} exceeds file size limit.")

        total_size += size
        if total_size > limits.max_total_file_bytes:
            raise AnalysisLimitError("Package exceeds total file size limit.")

        if len(files) >= limits.max_files:
            raise AnalysisLimitError(
                f"Package contains too many files (> {limits.max_files})."
            )
        files.append(path)

    return files


def read_text_with_limit(
    path: Path,
    limits: AnalysisLimits,
    *,
    encoding: str = "utf-8",
) -> str:
    if path.stat().st_size > limits.max_file_size_bytes:
        raise AnalysisLimitError(f"File {path.name!r} exceeds file size limit.")
    return path.read_text(encoding=encoding)
