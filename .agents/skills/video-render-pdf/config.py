"""Shared configuration utilities for video-render-pdf.

Handles API key discovery without hard-coding secrets.
Priority:
  1. SILICONFLOW_API_KEY environment variable
  2. <git repo root>/.config/video-render-pdf/siliconflow_key
  3. ~/.config/video-render-pdf/siliconflow_key
  4. ./.config/siliconflow_key (legacy fallback)
"""

import os
import subprocess
import sys
from pathlib import Path


def _git_repo_root() -> Path | None:
    """Return the git repository root, or None if not inside a git repo."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return Path(root)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def load_siliconflow_key() -> str:
    """Load SiliconFlow API key from env/file with clear precedence."""
    # 1. Environment variable
    env_key = os.getenv("SILICONFLOW_API_KEY")
    if env_key:
        return env_key.strip()

    # 2. Repository-local config
    candidates = []
    repo_root = _git_repo_root()
    if repo_root is not None:
        candidates.append(repo_root / ".config" / "video-render-pdf" / "siliconflow_key")

    # 3. User home config
    candidates.append(Path.home() / ".config" / "video-render-pdf" / "siliconflow_key")

    # 4. Legacy: current working directory
    candidates.append(Path(".config") / "siliconflow_key")

    for p in candidates:
        if p.exists():
            return p.read_text().strip()

    print(
        "ERROR: siliconflow_key not found.\n"
        "  Please create one of:\n"
        "    - <repo>/.config/video-render-pdf/siliconflow_key (recommended)\n"
        "    - ~/.config/video-render-pdf/siliconflow_key\n"
        "  Or set the SILICONFLOW_API_KEY environment variable.",
        file=sys.stderr,
    )
    sys.exit(1)
