"""Obsidian Local REST API client with JSON fallback.

Requires the 'Local REST API' community plugin installed and enabled in Obsidian.
Plugin runs at https://127.0.0.1:27124 with a self-signed cert.
If Obsidian is not running, all writes fall back to JSONL files under fallback_dir.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    track: str            # "esl_tuning" | "prompt_opt" | "context_scoring"
    trial: int
    score: float
    baseline: float
    delta: float          # score - baseline (positive = improvement)
    outcome: str          # "WIN" | "LOSS"
    hypothesis: str       # one-line description of the change made
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ObsidianClient:
    """Write experiment results to an Obsidian vault via Local REST API.

    Falls back silently to JSONL files if Obsidian is not reachable.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://127.0.0.1:27124",
        vault_path: str = "EthicCompanion",
        fallback_dir: Optional[str] = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.vault_path = vault_path.strip("/")
        self.fallback_dir = Path(fallback_dir) if fallback_dir else Path(__file__).parent / "results"
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "text/markdown",
        }

    def ping(self) -> bool:
        """Return True if the Obsidian REST API is reachable."""
        try:
            resp = requests.get(
                f"{self.base_url}/",
                headers={"Authorization": f"Bearer {self.api_key}"},
                verify=False,
                timeout=2,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def log_result(self, result: ExperimentResult) -> None:
        """Append a trial result to the track's log.md in Obsidian, or fallback to JSONL."""
        row = (
            f"| {result.trial} | {result.score:.4f} | "
            f"{result.delta:+.4f} | {result.outcome} | {result.hypothesis} | "
            f"{result.timestamp} |\n"
        )
        vault_file = f"{self.vault_path}/Experiments/{result.track}/log.md"
        try:
            resp = requests.patch(
                f"{self.base_url}/vault/{vault_file}",
                headers={
                    **self._headers,
                    "Target-Type": "heading",
                    "Target": "## Trial Log",
                    "Operation": "append",
                },
                data=row,
                verify=False,
                timeout=5,
            )
            if resp.status_code not in (200, 204):
                raise ValueError(f"Obsidian API returned {resp.status_code}")
        except (requests.exceptions.RequestException, ValueError, OSError) as e:
            logger.warning(f"Obsidian write failed ({e}), falling back to JSONL")
            self._write_fallback(result)

    def update_best(self, result: ExperimentResult) -> None:
        """Overwrite best.md for this track with the new best result."""
        content = (
            f"# Best Result — {result.track}\n\n"
            f"**Score:** {result.score:.4f}  \n"
            f"**Trial:** {result.trial}  \n"
            f"**Delta from baseline:** {result.delta:+.4f}  \n"
            f"**Hypothesis:** {result.hypothesis}  \n"
            f"**Timestamp:** {result.timestamp}  \n"
        )
        vault_file = f"{self.vault_path}/Experiments/{result.track}/best.md"
        try:
            resp = requests.put(
                f"{self.base_url}/vault/{vault_file}",
                headers=self._headers,
                data=content,
                verify=False,
                timeout=5,
            )
            if resp.status_code not in (200, 204):
                raise ValueError(f"Obsidian API returned {resp.status_code}")
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning(f"Obsidian write failed ({e}), falling back to JSONL")
            best_file = self.fallback_dir / result.track / "best.json"
            best_file.parent.mkdir(parents=True, exist_ok=True)
            best_file.write_text(json.dumps(asdict(result), indent=2))

    def _write_fallback(self, result: ExperimentResult) -> None:
        try:
            log_file = self.fallback_dir / result.track / "log.jsonl"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a") as f:
                f.write(json.dumps(asdict(result)) + "\n")
        except Exception as e:
            logger.error(f"Fallback write also failed: {e}")
