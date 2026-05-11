"""
QMD semantic search integration for claude-note.

Provides semantic search capabilities using the qmd MCP tool if available.
Falls back gracefully if qmd is not available.
"""

import shutil
import subprocess
import sys
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _resolve_qmd_cmd() -> Optional[list[str]]:
    """
    Resolve the command list to invoke qmd.

    On Windows, npm-installed .cmd wrappers contain Unix paths and fail under
    cmd.exe. Instead we locate qmd.js via the .ps1 wrapper and invoke it with
    node directly.
    """
    if sys.platform == "win32":
        # npm installs qmd.cmd but its shell wrapper uses Unix paths that break
        # under cmd.exe. Find the npm global dir via qmd.cmd, then locate the
        # .ps1 file (same dir, .ps1 extension) and extract the path to qmd.js.
        cmd_path = shutil.which("qmd.cmd") or shutil.which("qmd")
        if cmd_path:
            npm_dir = Path(cmd_path).parent
            ps1 = npm_dir / "qmd.ps1"
            if ps1.exists():
                try:
                    import re
                    text = ps1.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r'\$qmdjs\s*=\s*"([^"]+)"', text)
                    if m:
                        # Replace $basedir with the actual npm dir
                        rel = m.group(1).replace("$basedir", str(npm_dir))
                        qmd_js = Path(rel)
                        if qmd_js.exists():
                            node = shutil.which("node")
                            if node:
                                return [node, str(qmd_js)]
                except Exception:
                    pass
            return [str(cmd_path)]
        return None

    # Non-Windows: plain executable
    qmd = shutil.which("qmd")
    return [qmd] if qmd else None


def _run_qmd(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run qmd command, resolving the full path so any shell environment works."""
    cmd = _resolve_qmd_cmd()
    if not cmd:
        raise FileNotFoundError("qmd not found in PATH")
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return subprocess.run(cmd + args, **kwargs)


@dataclass
class SearchResult:
    """A semantic search result."""
    path: str
    title: str
    score: float
    snippet: str = ""


_qmd_available_cache: Optional[bool] = None
_qmd_available_checked: float = 0.0
_qmd_doc_count_cache: Optional[int] = None
_QMD_CACHE_TTL = 300.0  # re-check at most every 5 minutes


def _parse_doc_count(status_output: str) -> int:
    """Parse total indexed document count from 'qmd status' output."""
    import re
    m = re.search(r"Total:\s+(\d+)\s+files? indexed", status_output)
    return int(m.group(1)) if m else 0


def is_qmd_available() -> bool:
    """
    Check if qmd is installed AND has documents indexed (result cached 5 min).

    Returns False when the index is empty — no point running searches.
    """
    import time
    global _qmd_available_cache, _qmd_available_checked, _qmd_doc_count_cache

    now = time.monotonic()
    if _qmd_available_cache is not None and (now - _qmd_available_checked) < _QMD_CACHE_TTL:
        return _qmd_available_cache

    # Quick path check first — avoids cold-start cost when qmd is not installed
    if _resolve_qmd_cmd() is None:
        _qmd_available_cache = False
        _qmd_available_checked = now
        return False

    try:
        result = _run_qmd(
            ["status"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            _qmd_available_cache = False
        else:
            doc_count = _parse_doc_count(result.stdout)
            _qmd_doc_count_cache = doc_count
            # Treat empty index as unavailable — searches would return nothing
            _qmd_available_cache = doc_count > 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _qmd_available_cache = False

    _qmd_available_checked = now
    return _qmd_available_cache


def get_doc_count() -> int:
    """Return cached document count from last is_qmd_available() call."""
    return _qmd_doc_count_cache or 0


def search_vector(
    query: str,
    limit: int = 10,
    min_score: float = 0.3,
) -> list[SearchResult]:
    """
    Perform semantic (vector) search using qmd vsearch.

    Args:
        query: Natural language query
        limit: Maximum results to return
        min_score: Minimum similarity score (0-1)

    Returns:
        List of SearchResult objects
    """
    if not is_qmd_available():
        return []

    try:
        result = _run_qmd(
            [
                "vsearch",
                query,
                "--limit", str(limit),
                "--min-score", str(min_score),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        results = []

        for item in data.get("results", []):
            results.append(SearchResult(
                path=item.get("path", ""),
                title=item.get("title", Path(item.get("path", "")).stem),
                score=float(item.get("score", 0)),
                snippet=item.get("snippet", ""),
            ))

        return results

    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return []


def search_keyword(
    query: str,
    limit: int = 10,
) -> list[SearchResult]:
    """
    Perform keyword (BM25) search using qmd search.

    Args:
        query: Keywords to search for
        limit: Maximum results to return

    Returns:
        List of SearchResult objects
    """
    if not is_qmd_available():
        return []

    try:
        result = _run_qmd(
            [
                "search",
                query,
                "--limit", str(limit),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        results = []

        for item in data.get("results", []):
            results.append(SearchResult(
                path=item.get("path", ""),
                title=item.get("title", Path(item.get("path", "")).stem),
                score=float(item.get("score", 0)),
                snippet=item.get("snippet", ""),
            ))

        return results

    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        return []


def find_similar_content(
    query: str,
    limit: int = 5,
    min_score: float = 0.6,
) -> list[SearchResult]:
    """
    Find content semantically similar to the given query.

    Used for deduplication checking.

    Args:
        query: Content to find similar matches for
        limit: Maximum results
        min_score: Minimum similarity threshold

    Returns:
        List of SearchResult objects sorted by score descending
    """
    return search_vector(query, limit=limit, min_score=min_score)


def find_related_notes(
    keywords: list[str] = None,
    tags: list[str] = None,
    limit: int = 10,
    use_semantic: bool = True,
) -> list[SearchResult]:
    """
    Find notes related to keywords and tags.

    Combines keyword and semantic search for best results.

    Args:
        keywords: Keywords to search for
        tags: Tags to match (used as additional keywords)
        limit: Maximum results
        use_semantic: Use vector search (slower but better)

    Returns:
        List of SearchResult objects
    """
    if not is_qmd_available():
        return []

    # Build query from keywords and tags
    query_parts = []
    if keywords:
        query_parts.extend(keywords)
    if tags:
        # Tags are often descriptive, include them
        query_parts.extend(tags)

    if not query_parts:
        return []

    query = " ".join(query_parts)

    if use_semantic:
        return search_vector(query, limit=limit)
    else:
        return search_keyword(query, limit=limit)


def get_document(file_path: str) -> Optional[str]:
    """
    Get the full content of a document by path.

    Args:
        file_path: Path to the document (relative or absolute)

    Returns:
        Document content, or None if not found
    """
    if not is_qmd_available():
        return None

    try:
        result = _run_qmd(
            ["get", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return None

        return result.stdout

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
