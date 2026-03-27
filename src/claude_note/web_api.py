"""Web API for claude-note management.

Provides FastAPI endpoints for worker management, configuration,
and status monitoring.
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    raise ImportError(
        "FastAPI is required for web mode. "
        "Install with: pip install fastapi uvicorn"
    )

from . import config
from . import __version__
from . import models
from . import queue_manager
from . import session_tracker
from . import vault_indexer
from . import cleaner
from . import synthesizer
from . import worker_manager
from pydantic import BaseModel


# =============================================================================
# Pydantic Models
# =============================================================================

class ConfigUpdate(BaseModel):
    """Configuration update request."""
    models: Optional[List[str]] = None
    synth_mode: Optional[str] = None
    max_model_retries: Optional[int] = None
    model_retry_delay: Optional[int] = None


class WorkerAction(BaseModel):
    """Worker action request."""
    action: str  # "start" or "stop"


class SessionRetry(BaseModel):
    """Session retry request."""
    model: Optional[str] = None


class CleanRequest(BaseModel):
    """Cleanup request."""
    execute: bool = False
    clean_state: bool = True
    clean_sessions: bool = True
    clean_inbox: bool = True
    clean_topics: bool = True


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(title="claude-note", version=__version__)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# =============================================================================
# Helper Functions
# =============================================================================

def _load_config_file() -> dict:
    """Load config.toml file."""
    config_path = config._get_config_path()
    if not config_path.exists():
        return {}
    return config._load_toml_config()


def _save_config_file(data: dict) -> None:
    """Save config.toml file."""
    config_path = config._get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Simple TOML writer
    lines = []
    for section, values in data.items():
        if isinstance(values, dict):
            lines.append(f"\n[{section}]")
            for key, value in values.items():
                if isinstance(value, list):
                    # Inline array format for TOML
                    value_str = ", ".join(repr(v) for v in value)
                    lines.append(f"{key} = [{value_str}]")
                elif isinstance(value, bool):
                    lines.append(f"{key} = {str(value).lower()}")
                else:
                    lines.append(f"{key} = {repr(value)}")
        else:
            # Top-level key=value (without section)
            lines.append(f"{section} = {repr(values)}")

    config_path.write_text("\n".join(lines) + "\n")


def _get_recent_log_entries(limit: int = 50) -> List[dict]:
    """Get recent log entries from worker log file."""
    log_dir = config.LOGS_DIR
    if not log_dir.exists():
        return []

    # Get today's log file
    today = datetime.utcnow().strftime("%Y-%m-%d")
    log_file = log_dir / f"worker-{today}.log"

    if not log_file.exists():
        # Try most recent log file
        log_files = sorted(log_dir.glob("worker-*.log"), reverse=True)
        if log_files:
            log_file = log_files[0]
        else:
            return []

    entries = []
    try:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        for line in content.splitlines()[-limit:]:
            # Parse log line format: "YYYY-MM-DD HH:MM:SS [LEVEL] message"
            if line and "[" in line:
                try:
                    timestamp_end = line.index(" [")
                    timestamp = line[:timestamp_end]
                    level_start = timestamp_end + 2
                    level_end = line.index("]", level_start)
                    level = line[level_start:level_end]
                    message = line[level_end + 2:].strip()
                    entries.append({
                        "timestamp": timestamp,
                        "level": level,
                        "message": message,
                    })
                except (ValueError, IndexError):
                    # Skip unparseable lines
                    pass
    except (IOError, OSError):
        pass

    return entries


# =============================================================================
# API Routes
# =============================================================================

@app.get("/")
async def root() -> FileResponse:
    """Serve main UI."""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>claude-note Web API</h1><p>See <a href='/docs'>/docs</a> for API documentation.</p>")


@app.get("/api/status")
async def get_status() -> dict:
    """Get overall system status."""
    # Worker status
    worker_status = worker_manager.get_worker_status()

    # Queue stats
    queue_files = list(config.QUEUE_DIR.glob("*.jsonl")) if config.QUEUE_DIR.exists() else []
    total_events = 0
    sessions: Dict[str, int] = {}

    for event in queue_manager.read_all_events():
        total_events += 1
        sessions[event.session_id] = sessions.get(event.session_id, 0) + 1

    written_count = 0
    pending_count = 0
    for session_id in sessions:
        state = session_tracker.load_session_state(session_id)
        if state and state.last_write_ts:
            written_count += 1
        else:
            pending_count += 1

    # Vault index
    index = vault_indexer.get_index()
    index_age = None
    if index:
        import time
        index_age = int(time.time() - index.last_full_scan)

    return {
        "worker": worker_status,
        "queue": {
            "files": len(queue_files),
            "events": total_events,
            "sessions": len(sessions),
            "written": written_count,
            "pending": pending_count,
        },
        "vault": {
            "notes": len(index.notes) if index else 0,
            "index_age_seconds": index_age,
        },
        "config": {
            "vault_root": str(config.VAULT_ROOT),
            "synth_mode": config.SYNTH_MODE,
            "models": config.SYNTH_MODELS,
        },
    }


@app.get("/api/sessions")
async def list_sessions(limit: int = 100, status: Optional[str] = None) -> List[dict]:
    """List all sessions with optional filtering."""
    sessions: Dict[str, List] = {}
    for event in queue_manager.read_all_events():
        if event.session_id not in sessions:
            sessions[event.session_id] = []
        sessions[event.session_id].append(event)

    result = []
    for session_id, events in sessions.items():
        state = session_tracker.load_session_state(session_id)

        # Determine status: check if ALL events have been processed
        session_status = "pending"
        if state:
            # Check if all events are processed
            total_events = len(state.events)
            processed_events = len(state.processed_event_ids) if state.processed_event_ids else 0
            if total_events > 0 and processed_events >= total_events:
                session_status = "written"
            # Also check timestamp as fallback (for sessions without event list in state)
            elif state.last_event_ts and state.last_write_ts:
                last_event = datetime.fromisoformat(state.last_event_ts.rstrip("Z"))
                last_write = datetime.fromisoformat(state.last_write_ts.rstrip("Z"))
                if last_write >= last_event:
                    session_status = "written"

        # Apply filter
        if status and session_status != status:
            continue

        result.append({
            "session_id": session_id,
            "status": session_status,
            "cwd": state.cwd if state else "",
            "event_count": len(events),
            "last_write": state.last_write_ts if state else None,
            "last_event": state.last_event_ts if state else None,
            "synth_model": state.synth_model if state else None,
            "transcript": str(state.transcript_path) if state and state.transcript_path else None,
        })

    # Sort by most recent activity
    result.sort(key=lambda x: x["last_event"] or x["last_write"] or "", reverse=True)
    return result[:limit]


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get detailed session info."""
    state = session_tracker.load_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": state.session_id,
        "cwd": state.cwd,
        "events": state.events,
        "last_write_ts": state.last_write_ts,
        "synth_model": state.synth_model,
        "transcript_path": str(state.transcript_path) if state.transcript_path else None,
    }


@app.post("/api/sessions/{session_id}/retry")
async def retry_session(session_id: str, request: SessionRetry) -> dict:
    """Retry synthesis for a session."""
    try:
        pack = synthesizer.resynthesize_session(session_id, model=request.model)
        if pack is None or pack.is_empty():
            return {"success": True, "message": "No knowledge extracted"}

        # Apply changes
        from . import note_router
        results = note_router.apply_note_ops(pack, mode=config.SYNTH_MODE)

        return {
            "success": True,
            "pack": {
                "title": pack.title,
                "highlights": len(pack.highlights),
                "concepts": len(pack.concepts),
                "decisions": len(pack.decisions),
                "model_used": getattr(pack, "model_used", "unknown"),
            },
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config() -> dict:
    """Get current configuration."""
    return {
        "vault_root": str(config.VAULT_ROOT),
        "synth_mode": config.SYNTH_MODE,
        "models": config.SYNTH_MODELS,
        "max_model_retries": config.SYNTH_MAX_MODEL_RETRIES,
        "model_retry_delay": config.SYNTH_MODEL_RETRY_DELAY,
        "language_code": config.LANGUAGE_CODE,
        "prompts_archive_enabled": config.PROMPTS_ARCHIVE_ENABLED,
        "qmd_enabled": config.QMD_SYNTH_ENABLED,
    }


@app.put("/api/config")
async def update_config(update: ConfigUpdate) -> dict:
    """Update configuration."""
    config_data = _load_config_file()

    # Ensure synthesis section exists
    if "synthesis" not in config_data:
        config_data["synthesis"] = {}

    if update.models is not None:
        config_data["synthesis"]["models"] = update.models
    if update.synth_mode is not None:
        config_data["synthesis"]["mode"] = update.synth_mode
    if update.max_model_retries is not None:
        config_data["synthesis"]["max_model_retries"] = update.max_model_retries
    if update.model_retry_delay is not None:
        config_data["synthesis"]["model_retry_delay"] = update.model_retry_delay

    _save_config_file(config_data)

    # Reload config
    config._config_cache = None

    return {"success": True}


@app.get("/api/models")
async def get_models() -> dict:
    """Get available models and their status."""
    return {
        "models": config.SYNTH_MODELS,
        "current": config.SYNTH_MODEL,
        "suggestions": [
            {"value": "claude-sonnet-4-5-20250929", "label": "claude-sonnet-4-5-20250929 (default)"},
            {"value": "claude-opus-4-6-20250514", "label": "claude-opus-4-6-20250514"},
            {"value": "claude-haiku-4-5-20251001", "label": "claude-haiku-4-5-20251001"},
            {"value": "claude-z:glm-4.7", "label": "claude-z:glm-4.7 (zhipu)"},
            {"value": "claude-k:deepseek-v3", "label": "claude-k:deepseek-v3"},
            {"value": "claude-k:deepseek-r1", "label": "claude-k:deepseek-r1"},
        ],
    }


@app.put("/api/models")
async def update_models(models: List[str]) -> dict:
    """Update model order."""
    if not models:
        raise HTTPException(status_code=400, detail="Models list cannot be empty")

    try:
        config_data = _load_config_file()
        if "synthesis" not in config_data:
            config_data["synthesis"] = {}

        config_data["synthesis"]["models"] = models
        _save_config_file(config_data)

        # Reload config
        config._config_cache = None

        return {"success": True, "models": models}
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")


@app.post("/api/worker/start")
async def start_worker() -> dict:
    """Start the worker process."""
    success = worker_manager.start_worker()
    return {"success": success, "running": worker_manager.is_worker_running()}


@app.post("/api/worker/stop")
async def stop_worker() -> dict:
    """Stop the worker process."""
    success = worker_manager.stop_worker()
    return {"success": success, "running": worker_manager.is_worker_running()}


@app.get("/api/worker/status")
async def get_worker_status() -> dict:
    """Get worker process status."""
    return worker_manager.get_worker_status()


@app.get("/api/logs")
async def get_logs(limit: int = 50) -> List[dict]:
    """Get recent log entries."""
    return _get_recent_log_entries(limit)


@app.post("/api/clean")
async def run_cleanup(request: CleanRequest) -> dict:
    """Run cleanup operations."""
    results = cleaner.run_daily_clean(
        date=None,
        dry_run=not request.execute,
        clean_state=request.clean_state,
        clean_sessions=request.clean_sessions,
        clean_inbox=request.clean_inbox,
        clean_topics=request.clean_topics,
    )

    return {
        "dry_run": not request.execute,
        "results": results,
    }


@app.post("/api/index")
async def rebuild_index() -> dict:
    """Rebuild vault index."""
    index = vault_indexer.build_index()
    vault_indexer.save_index(index)

    summary = vault_indexer.get_index_summary()

    return {
        "success": True,
        "notes": summary["total_notes"],
        "tags": summary["unique_tags"],
    }


# =============================================================================
# Run Server
# =============================================================================

def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the web API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="claude-note Web API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Port to bind to")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)
