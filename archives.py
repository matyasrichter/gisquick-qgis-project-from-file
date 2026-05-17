from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path
from typing import FrozenSet


_ARCHIVE_SUFFIXES = frozenset({".zip", ".tar", ".tgz", ".tbz2", ".txz"})
_ARCHIVE_COMPOUND_SUFFIXES = frozenset({".tar.gz", ".tar.bz2", ".tar.xz"})


def is_archive(name: str) -> bool:
    lower = name.lower()
    if Path(lower).suffix in _ARCHIVE_SUFFIXES:
        return True
    return any(lower.endswith(ext) for ext in _ARCHIVE_COMPOUND_SUFFIXES)


def archive_stem(name: str) -> str:
    """Return the base name of an archive, stripping compound extensions like .tar.gz."""
    stem = Path(name).stem
    if Path(stem).suffix == ".tar":
        stem = Path(stem).stem
    return stem


def extract_archive(archive_path: Path, dest_dir: Path) -> None:
    """Extract archive_path into dest_dir.

    Raises ValueError on ZIP-slip attempts. Raises zipfile/tarfile errors on
    corrupt or unsupported archives.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest_dir.resolve()

    if archive_path.name.lower().endswith(".zip"):
        _extract_zip(archive_path, dest_dir, dest_resolved)
    else:
        _extract_tar(archive_path, dest_dir, dest_resolved)


def scan_spatial_files(directory: Path, extensions: FrozenSet[str]) -> list[Path]:
    """Recursively find files whose suffix (lowercased) is in extensions."""
    return sorted(
        f for f in directory.rglob("*")
        if f.is_file() and f.suffix.lower() in extensions
    )


def _assert_no_slip(member_path: str, dest_dir: Path, dest_resolved: Path) -> None:
    target = (dest_dir / member_path).resolve()
    try:
        target.relative_to(dest_resolved)
    except ValueError:
        raise ValueError(f"ZIP slip detected in archive member: {member_path!r}")


def _extract_zip(archive_path: Path, dest_dir: Path, dest_resolved: Path) -> None:
    with zipfile.ZipFile(archive_path) as zf:
        for member in zf.infolist():
            _assert_no_slip(member.filename, dest_dir, dest_resolved)
        zf.extractall(dest_dir)


def _extract_tar(archive_path: Path, dest_dir: Path, dest_resolved: Path) -> None:
    with tarfile.open(archive_path, mode="r:*") as tf:
        for member in tf.getmembers():
            _assert_no_slip(member.name, dest_dir, dest_resolved)
        tf.extractall(dest_dir)
