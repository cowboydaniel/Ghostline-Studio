"""Update installer for Ghostline Studio."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class UpdateInstaller:
    """Downloads and installs Ghostline updates."""

    def __init__(self) -> None:
        self.project_root = self._find_project_root()

    def _find_project_root(self) -> Path:
        """Find the project root directory."""
        # Start from this file's location and work upward
        current = Path(__file__).resolve().parent.parent.parent
        return current

    def download_and_install(self, release_url: str) -> bool:
        """Download a release and install it.

        Args:
            release_url: URL to the GitHub release page

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract repo owner and name from URL
            # e.g., https://github.com/cowboydaniel/Ghostline-Studio/releases/tag/v0.0.1
            parts = release_url.rstrip("/").split("/")
            if "github.com" not in release_url or len(parts) < 5:
                logger.error(f"Invalid release URL: {release_url}")
                return False

            owner = parts[-4]
            repo = parts[-3]

            # Get the tag name from the URL
            tag = parts[-1]
            if tag == "tag":
                # If URL ends with /tag/, get the actual tag
                tag = parts[-1] if len(parts) > 1 else None
                if not tag:
                    logger.error("Could not extract tag from URL")
                    return False

            # Build download URL for source code ZIP
            download_url = f"https://github.com/{owner}/{repo}/archive/refs/tags/{tag}.zip"

            logger.info(f"Downloading update from {download_url}")

            # Download the release
            temp_dir = Path(tempfile.mkdtemp(prefix="ghostline_update_"))
            try:
                zip_path = temp_dir / "release.zip"

                # Download with timeout
                with urllib.request.urlopen(download_url, timeout=30) as response:
                    with open(zip_path, "wb") as f:
                        f.write(response.read())

                logger.info(f"Downloaded {zip_path.stat().st_size} bytes")

                # Extract the archive
                extract_dir = temp_dir / "extracted"
                extract_dir.mkdir()

                import zipfile
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)

                logger.info(f"Extracted to {extract_dir}")

                # Find the extracted project directory
                # GitHub creates a subdirectory like Ghostline-Studio-v0.0.1
                extracted_dirs = list(extract_dir.iterdir())
                if len(extracted_dirs) != 1 or not extracted_dirs[0].is_dir():
                    logger.error(f"Unexpected extraction structure: {extracted_dirs}")
                    return False

                project_dir = extracted_dirs[0]
                logger.info(f"Project directory: {project_dir}")

                # Install the update
                return self._install_from_directory(project_dir)

            finally:
                # Clean up temp directory
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Could not clean up temp directory: {e}")

        except urllib.error.URLError as e:
            logger.error(f"Network error downloading update: {e}")
            return False
        except Exception as e:
            logger.error(f"Error downloading/installing update: {e}")
            return False

    def _install_from_directory(self, source_dir: Path) -> bool:
        """Install from a downloaded/extracted directory.

        Args:
            source_dir: Directory containing the downloaded project

        Returns:
            True if successful
        """
        try:
            # Backup current installation
            backup_dir = self.project_root.parent / f"{self.project_root.name}.backup"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            logger.info(f"Backing up current installation to {backup_dir}")
            shutil.copytree(self.project_root, backup_dir, dirs_exist_ok=True)

            # Copy new files, preserving user configuration
            logger.info(f"Copying update files from {source_dir}")

            # Files/directories to preserve (not overwrite)
            preserve = {".config", ".github", "logs"}

            for item in source_dir.iterdir():
                dest = self.project_root / item.name

                # Don't overwrite config
                if item.name in preserve:
                    logger.info(f"Preserving {item.name}")
                    continue

                # Remove old file/directory
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()

                # Copy new file/directory
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

            logger.info("Update installed successfully")
            return True

        except Exception as e:
            logger.error(f"Error installing update: {e}")
            # Restore from backup on failure
            try:
                backup_dir = self.project_root.parent / f"{self.project_root.name}.backup"
                if backup_dir.exists():
                    logger.info("Restoring from backup due to install failure")
                    shutil.rmtree(self.project_root)
                    shutil.copytree(backup_dir, self.project_root)
            except Exception as restore_error:
                logger.error(f"Failed to restore backup: {restore_error}")

            return False

    def restart_application(self) -> None:
        """Restart the application with the same arguments."""
        try:
            # Get the script that started the app
            if hasattr(sys, "argv") and len(sys.argv) > 0:
                script = sys.argv[0]
            else:
                script = str(self.project_root / "start.py")

            # Preserve any command line arguments (except the script name)
            args = sys.argv[1:] if len(sys.argv) > 1 else []

            logger.info(f"Restarting application: {script} {args}")

            # Detach from current process and start new one
            if sys.platform == "win32":
                # Windows
                subprocess.Popen([sys.executable, script] + args, cwd=self.project_root)
            else:
                # Unix-like (Linux, macOS)
                subprocess.Popen(
                    [sys.executable, script] + args,
                    cwd=self.project_root,
                    start_new_session=True,
                )

            # Exit current application
            sys.exit(0)

        except Exception as e:
            logger.error(f"Error restarting application: {e}")
            raise
