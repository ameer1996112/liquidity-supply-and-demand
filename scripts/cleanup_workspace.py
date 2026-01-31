#!/usr/bin/env python3
"""
Trading Bot v2.0 - Workspace Cleanup Script
============================================

This script safely cleans up the workspace by:
1. Moving deprecated files to _archive/ (not deleting)
2. Deleting obvious junk (logs, __pycache__)
3. Reporting what was done

SAFETY FIRST: Run with --dry-run first!

Usage:
    python scripts/cleanup_workspace.py --dry-run   # Preview changes
    python scripts/cleanup_workspace.py             # Execute cleanup
    python scripts/cleanup_workspace.py --restore   # Undo (restore from archive)
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

# Project root (relative to this script)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = PROJECT_ROOT / "_archive"
ARCHIVE_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Files to ARCHIVE (move to _archive/, preserving directory structure)
FILES_TO_ARCHIVE = [
    # Legacy monolithic app (superseded by main.py + worker.py)
    "backend/trading_bot.py",

    # Test scripts for deprecated code
    "backend/test_bot.py",
    "backend/test_news_logic.py",

    # Experimental/untracked files (review these manually first!)
    # Uncomment after review:
    # "backend/pine_guardian.py",
    # "scripts/reset_system.py",
    # "scripts/test_full_system.py",
]

# Files/patterns to DELETE (logs, cache - safe to remove)
PATTERNS_TO_DELETE = [
    # Log files
    "backend/bot.log",
    "backend/trading_bot.log",
    "dashboard/.next/dev/logs/*.log",

    # Python cache (will be regenerated)
    "backend/__pycache__",
    "scripts/__pycache__",

    # Common junk patterns
    "**/*.pyc",
    "**/.DS_Store",
]

# Directories to clean (remove __pycache__ inside, but not the dir itself)
DIRS_TO_CLEAN_PYCACHE = [
    "backend",
    "scripts",
]

# =============================================================================
# COLORS FOR OUTPUT
# =============================================================================

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")

def print_action(action: str, path: str, dry_run: bool = False):
    prefix = f"{Colors.YELLOW}[DRY-RUN]{Colors.END} " if dry_run else ""

    if action == "ARCHIVE":
        icon = f"{Colors.BLUE}📦{Colors.END}"
    elif action == "DELETE":
        icon = f"{Colors.RED}🗑️{Colors.END}"
    elif action == "SKIP":
        icon = f"{Colors.YELLOW}⏭️{Colors.END}"
    elif action == "RESTORE":
        icon = f"{Colors.GREEN}♻️{Colors.END}"
    else:
        icon = "  "

    print(f"{prefix}{icon} {action}: {path}")

# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def archive_file(file_path: Path, dry_run: bool = False) -> bool:
    """Move a file to the archive directory, preserving relative path."""
    if not file_path.exists():
        print_action("SKIP", f"{file_path} (not found)", dry_run)
        return False

    # Create archive path preserving directory structure
    relative_path = file_path.relative_to(PROJECT_ROOT)
    archive_path = ARCHIVE_DIR / ARCHIVE_TIMESTAMP / relative_path

    if dry_run:
        print_action("ARCHIVE", f"{relative_path} -> _archive/{ARCHIVE_TIMESTAMP}/{relative_path}", dry_run)
        return True

    # Create parent directories
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    # Move file
    shutil.move(str(file_path), str(archive_path))
    print_action("ARCHIVE", f"{relative_path} -> _archive/{ARCHIVE_TIMESTAMP}/{relative_path}")
    return True


def delete_path(path: Path, dry_run: bool = False) -> bool:
    """Delete a file or directory."""
    if not path.exists():
        return False

    relative_path = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path

    if dry_run:
        print_action("DELETE", str(relative_path), dry_run)
        return True

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()

    print_action("DELETE", str(relative_path))
    return True


def clean_pycache(directory: Path, dry_run: bool = False) -> int:
    """Remove all __pycache__ directories within a directory."""
    count = 0
    for pycache in directory.rglob("__pycache__"):
        if pycache.is_dir():
            # Skip venv directories
            if "venv" in str(pycache) or "node_modules" in str(pycache):
                continue
            if delete_path(pycache, dry_run):
                count += 1
    return count


def expand_glob_pattern(pattern: str) -> list[Path]:
    """Expand a glob pattern to actual file paths."""
    if "*" in pattern:
        return list(PROJECT_ROOT.glob(pattern))
    else:
        path = PROJECT_ROOT / pattern
        return [path] if path.exists() else []


def restore_archive(timestamp: str = None, dry_run: bool = False) -> int:
    """Restore files from archive back to their original locations."""
    if not ARCHIVE_DIR.exists():
        print(f"{Colors.RED}No archive directory found.{Colors.END}")
        return 0

    # Find archive to restore
    archives = sorted([d for d in ARCHIVE_DIR.iterdir() if d.is_dir()], reverse=True)

    if not archives:
        print(f"{Colors.RED}No archives found.{Colors.END}")
        return 0

    if timestamp:
        archive_to_restore = ARCHIVE_DIR / timestamp
        if not archive_to_restore.exists():
            print(f"{Colors.RED}Archive '{timestamp}' not found.{Colors.END}")
            print(f"Available archives: {[a.name for a in archives]}")
            return 0
    else:
        archive_to_restore = archives[0]  # Most recent
        print(f"Restoring most recent archive: {archive_to_restore.name}")

    count = 0
    for archived_file in archive_to_restore.rglob("*"):
        if archived_file.is_file():
            # Calculate original path
            relative_to_archive = archived_file.relative_to(archive_to_restore)
            original_path = PROJECT_ROOT / relative_to_archive

            if dry_run:
                print_action("RESTORE", f"{relative_to_archive}", dry_run)
                count += 1
                continue

            # Create parent directories
            original_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file back
            shutil.move(str(archived_file), str(original_path))
            print_action("RESTORE", str(relative_to_archive))
            count += 1

    # Clean up empty archive directory
    if not dry_run and count > 0:
        try:
            shutil.rmtree(archive_to_restore)
            print(f"\n{Colors.GREEN}Removed empty archive directory: {archive_to_restore.name}{Colors.END}")
        except Exception:
            pass

    return count


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Trading Bot Workspace Cleanup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cleanup_workspace.py --dry-run     # Preview changes
  python scripts/cleanup_workspace.py               # Execute cleanup
  python scripts/cleanup_workspace.py --restore     # Restore from archive
  python scripts/cleanup_workspace.py --list        # List archived files
        """
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview changes without executing"
    )
    parser.add_argument(
        "--restore", "-r",
        action="store_true",
        help="Restore files from archive"
    )
    parser.add_argument(
        "--timestamp", "-t",
        type=str,
        help="Specific archive timestamp to restore (default: most recent)"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available archives"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # List archives
    if args.list:
        print_header("Available Archives")
        if ARCHIVE_DIR.exists():
            archives = sorted([d for d in ARCHIVE_DIR.iterdir() if d.is_dir()], reverse=True)
            if archives:
                for archive in archives:
                    file_count = len(list(archive.rglob("*")))
                    print(f"  {archive.name} ({file_count} files)")
            else:
                print("  No archives found.")
        else:
            print("  No archive directory exists.")
        return 0

    # Restore mode
    if args.restore:
        print_header("Restore from Archive")
        count = restore_archive(args.timestamp, args.dry_run)
        print(f"\n{Colors.GREEN}Restored {count} files.{Colors.END}")
        return 0

    # Cleanup mode
    print_header("Trading Bot Workspace Cleanup")

    if args.dry_run:
        print(f"{Colors.YELLOW}DRY-RUN MODE: No changes will be made.{Colors.END}\n")

    archived_count = 0
    deleted_count = 0

    # Step 1: Archive deprecated files
    print(f"{Colors.BOLD}Step 1: Archiving deprecated files...{Colors.END}")
    for file_rel in FILES_TO_ARCHIVE:
        file_path = PROJECT_ROOT / file_rel
        if archive_file(file_path, args.dry_run):
            archived_count += 1

    if archived_count == 0:
        print(f"  {Colors.GREEN}No files to archive (already clean).{Colors.END}")

    # Step 2: Delete junk files
    print(f"\n{Colors.BOLD}Step 2: Deleting junk files...{Colors.END}")
    for pattern in PATTERNS_TO_DELETE:
        for path in expand_glob_pattern(pattern):
            # Skip venv and node_modules
            if "venv" in str(path) or "node_modules" in str(path):
                continue
            if delete_path(path, args.dry_run):
                deleted_count += 1

    # Step 3: Clean __pycache__ directories
    print(f"\n{Colors.BOLD}Step 3: Cleaning __pycache__ directories...{Colors.END}")
    for dir_rel in DIRS_TO_CLEAN_PYCACHE:
        dir_path = PROJECT_ROOT / dir_rel
        if dir_path.exists():
            count = clean_pycache(dir_path, args.dry_run)
            deleted_count += count

    # Summary
    print_header("Summary")
    print(f"  Archived: {archived_count} files")
    print(f"  Deleted:  {deleted_count} items")

    if args.dry_run:
        print(f"\n{Colors.YELLOW}This was a dry run. Run without --dry-run to execute.{Colors.END}")
    else:
        print(f"\n{Colors.GREEN}Cleanup complete!{Colors.END}")
        if archived_count > 0:
            print(f"  Archived files are in: _archive/{ARCHIVE_TIMESTAMP}/")
            print(f"  To restore: python scripts/cleanup_workspace.py --restore")

    return 0


if __name__ == "__main__":
    sys.exit(main())
