"""AutoResearch experiment routes."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from autolab.config import settings as autolab_settings
from autolab.obsidian import ObsidianClient, ExperimentResult

router = APIRouter(prefix="/api/autolab", tags=["AutoLab"])
logger = logging.getLogger(__name__)

TRACK_NAMES = ["esl_tuning", "prompt_opt", "context_scoring"]

TRACKS_DIR = Path(__file__).parent.parent / "autolab" / "tracks"
SURFACE_PATHS = {
    "esl_tuning": TRACKS_DIR / "esl_tuning" / "surface.py",
    "prompt_opt": TRACKS_DIR / "prompt_opt" / "surface.py",
    "context_scoring": TRACKS_DIR / "context_scoring" / "surface.py",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fallback_dir() -> Path:
    """Return the fallback results directory as a Path object."""
    return Path(autolab_settings.fallback_dir)


def _read_track_results(track: str) -> list[dict]:
    """Read all JSON result files for a given track from the fallback dir.

    Files may be:
      - <fallback_dir>/<track>_<timestamp>.json  (flat layout)
      - <fallback_dir>/<track>/log.jsonl          (JSONL per-track layout)
      - <fallback_dir>/<track>/best.json          (single best result)
    """
    results: list[dict] = []
    fallback = _fallback_dir()

    if not fallback.exists():
        return results

    # Flat layout: track_*.json at top level
    for p in fallback.glob(f"{track}_*.json"):
        try:
            results.append(json.loads(p.read_text()))
        except Exception:
            pass

    # Per-track subdirectory: log.jsonl
    jsonl_path = fallback / track / "log.jsonl"
    if jsonl_path.exists():
        try:
            for line in jsonl_path.read_text().splitlines():
                line = line.strip()
                if line:
                    results.append(json.loads(line))
        except Exception:
            pass

    # Per-track subdirectory: best.json (include so status can detect trials=0 gap)
    best_path = fallback / track / "best.json"
    if best_path.exists():
        try:
            obj = json.loads(best_path.read_text())
            # Only add if not already present via JSONL
            if not any(
                r.get("trial") == obj.get("trial") and r.get("track") == obj.get("track")
                for r in results
            ):
                results.append(obj)
        except Exception:
            pass

    return results


def _track_status(track: str) -> dict:
    """Summarise results for one track."""
    results = _read_track_results(track)
    if not results:
        return {"best_score": None, "trials": 0, "last_outcome": None}

    best_score: Optional[float] = None
    last_outcome: Optional[str] = None

    # Sort by trial number if available, otherwise by timestamp
    try:
        sorted_results = sorted(results, key=lambda r: r.get("trial", 0))
    except Exception:
        sorted_results = results

    wins = [r for r in sorted_results if r.get("outcome") == "WIN"]
    if wins:
        best_score = max(r.get("score", 0.0) for r in wins)

    last_outcome = sorted_results[-1].get("outcome") if sorted_results else None

    return {
        "best_score": best_score,
        "trials": len(sorted_results),
        "last_outcome": last_outcome,
    }


def _get_evaluate_fn(track: str):
    if track == "esl_tuning":
        from autolab.tracks.esl_tuning.evaluator import evaluate_esl_config
        return evaluate_esl_config
    elif track == "prompt_opt":
        from autolab.tracks.prompt_opt.evaluator import evaluate_prompts
        return evaluate_prompts
    elif track == "context_scoring":
        from autolab.tracks.context_scoring.evaluator import evaluate_context_scoring
        return evaluate_context_scoring
    return None


def _obsidian_client() -> ObsidianClient:
    return ObsidianClient(
        api_key=autolab_settings.obsidian_api_key,
        base_url=autolab_settings.obsidian_base_url,
        vault_path=autolab_settings.obsidian_vault_path,
        fallback_dir=autolab_settings.fallback_dir,
    )


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

def _run_experiment(track: str, max_trials: int) -> None:
    """Run hill-climbing experiment in the background."""
    from autolab.runner import HillClimbingRunner

    try:
        evaluate_fn = _get_evaluate_fn(track)
        if evaluate_fn is None:
            logger.error(f"[autolab] No evaluator found for track '{track}'")
            return

        surface_path = SURFACE_PATHS[track]
        program_md_path = surface_path.parent / "program.md"

        client = _obsidian_client()
        runner = HillClimbingRunner(
            track_name=track,
            surface_path=surface_path,
            program_md_path=program_md_path,
            evaluate_fn=evaluate_fn,
            obsidian_client=client,
            budget_secs=autolab_settings.budget_secs,
            anthropic_api_key=autolab_settings.anthropic_api_key,
        )
        summary = runner.run(max_trials=max_trials)
        logger.info(f"[autolab] Run complete for '{track}': {summary}")
    except Exception as exc:
        logger.error(f"[autolab] Background run failed for '{track}': {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    track: str
    max_trials: int = 5


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_autolab_status() -> dict:
    """Return current status of all three experiment tracks."""
    tracks: dict[str, Any] = {}
    for track in TRACK_NAMES:
        tracks[track] = _track_status(track)

    obsidian_available = _obsidian_client().ping()

    return {"tracks": tracks, "obsidian_available": obsidian_available}


@router.post("/run")
async def trigger_run(body: RunRequest, background_tasks: BackgroundTasks) -> dict:
    """Trigger a background experiment run for a given track."""
    if body.track not in TRACK_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown track '{body.track}'. Valid tracks: {TRACK_NAMES}",
        )

    background_tasks.add_task(_run_experiment, body.track, body.max_trials)
    return {"status": "started", "track": body.track}


@router.get("/stream/{track}")
async def stream_track_results(track: str):
    """SSE stream of the last 20 result entries for a given track."""
    if track not in TRACK_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown track '{track}'. Valid tracks: {TRACK_NAMES}",
        )

    results = _read_track_results(track)
    # Take the last 20
    last_20 = results[-20:] if len(results) > 20 else results

    async def event_generator():
        for result in last_20:
            yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# /api/insights — separate prefix, mounted on the same router via a separate
# APIRouter to avoid prefix collision with /api/autolab
# ---------------------------------------------------------------------------

insights_router = APIRouter(tags=["AutoLab"])


@insights_router.get("/api/insights")
async def get_insights() -> dict:
    """Aggregated insights for the frontend Insights page."""
    # Gather autolab data
    best_scores: dict[str, Optional[float]] = {}
    total_trials = 0
    total_wins = 0
    recent_experiments: list[dict] = []

    for track in TRACK_NAMES:
        results = _read_track_results(track)
        wins = [r for r in results if r.get("outcome") == "WIN"]
        best_scores[track] = max((r.get("score", 0.0) for r in wins), default=None)
        total_trials += len(results)
        total_wins += len(wins)

        # Collect recent results across all tracks
        for r in results:
            recent_experiments.append({
                "track": r.get("track", track),
                "trial": r.get("trial"),
                "score": r.get("score"),
                "outcome": r.get("outcome"),
                "hypothesis": r.get("hypothesis", ""),
            })

    # Sort recent experiments by trial descending, take top 10
    try:
        recent_experiments.sort(key=lambda x: (x.get("trial") or 0), reverse=True)
    except Exception:
        pass
    recent_experiments = recent_experiments[:10]

    # Try to fetch daily insight
    daily_insight = "Check back later for your daily insight."
    try:
        from routes.insight import router as _insight_router  # noqa: F401
        # We can't call the endpoint directly without a real request/auth context,
        # so we use a static placeholder when the import succeeds but we cannot invoke it.
        daily_insight = "Your AI companion is gathering today's insights."
    except Exception:
        pass

    return {
        "daily_insight": daily_insight,
        "autolab": {
            "best_scores": best_scores,
            "total_trials": total_trials,
            "total_wins": total_wins,
        },
        "recent_experiments": recent_experiments,
    }
