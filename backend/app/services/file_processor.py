import os
import zipfile
import tempfile
import shutil
import logging
from pathlib import Path
from typing import List, Tuple

from app.utils.helpers import (
    collect_files,
    read_file_safe,
    is_allowed_extension,
    MAX_FILE_SIZE_BYTES,
)
from app.models.schemas import FileInfo

logger = logging.getLogger(__name__)


class FileProcessor:
    """Handles file upload, ZIP extraction, and content preparation."""

    def __init__(self):
        self._temp_dirs: List[str] = []

    def create_temp_dir(self) -> str:
        temp_dir = tempfile.mkdtemp(prefix="codereview_")
        self._temp_dirs.append(temp_dir)
        logger.info("Created temp directory: %s", temp_dir)
        return temp_dir

    def cleanup_temp_dir(self, temp_dir: str) -> None:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info("Cleaned up temp directory: %s", temp_dir)
                if temp_dir in self._temp_dirs:
                    self._temp_dirs.remove(temp_dir)
        except Exception as e:
            logger.error("Error cleaning up temp dir %s: %s", temp_dir, e)

    def cleanup_all(self) -> None:
        for temp_dir in list(self._temp_dirs):
            self.cleanup_temp_dir(temp_dir)

    def validate_zip(self, file_path: str) -> Tuple[bool, str]:
        """Validate a ZIP file for safety (no path traversal, no symlinks)."""
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for member in zf.namelist():
                    # Block path traversal
                    if ".." in member or member.startswith("/"):
                        return False, f"Unsafe path in ZIP: {member}"
                    # Block absolute paths on Windows
                    if len(member) > 1 and member[1] == ":":
                        return False, f"Absolute path in ZIP: {member}"
            return True, ""
        except zipfile.BadZipFile:
            return False, "Invalid ZIP file"
        except Exception as e:
            return False, str(e)

    def extract_zip(self, zip_path: str, extract_to: str) -> List[str]:
        """Extract ZIP and return list of relative paths for allowed files."""
        valid, error = self.validate_zip(zip_path)
        if not valid:
            raise ValueError(f"ZIP validation failed: {error}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_to)

        logger.info("Extracted ZIP to %s", extract_to)
        return collect_files(extract_to)

    def process_single_file(self, file_path: str, save_to: str, original_name: str) -> List[str]:
        """Save a single uploaded file and return its relative path."""
        if not is_allowed_extension(original_name):
            raise ValueError(f"Unsupported file extension: {Path(original_name).suffix}")

        dest = os.path.join(save_to, original_name)
        shutil.copy2(file_path, dest)
        logger.info("Saved single file: %s", dest)
        return [original_name]

    def load_file_contents(self, base_dir: str, relative_paths: List[str]) -> List[FileInfo]:
        """Load file contents for a list of relative paths."""
        file_infos = []
        for rel_path in relative_paths:
            full_path = os.path.join(base_dir, rel_path)
            if not os.path.isfile(full_path):
                logger.warning("File not found: %s", full_path)
                continue

            size = os.path.getsize(full_path)
            if size > MAX_FILE_SIZE_BYTES:
                logger.warning("File too large, skipping: %s (%d bytes)", rel_path, size)
                continue

            content, truncated = read_file_safe(full_path)
            ext = Path(rel_path).suffix.lower()

            file_info = FileInfo(
                path=rel_path,
                size=size,
                extension=ext,
                content=content,
                truncated=truncated,
            )
            if truncated:
                logger.warning("File truncated due to size: %s", rel_path)
            file_infos.append(file_info)

        return file_infos
