"""Hill-climbing experiment runner.

For each trial:
  1. Read surface.py + program.md
  2. Ask Claude to propose a unified diff
  3. Apply the diff
  4. Run evaluator within budget_secs
  5. Keep if score improved, else revert
  6. Log to Obsidian
"""

import logging
import subprocess
import tempfile
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from autolab.obsidian import ObsidianClient, ExperimentResult

logger = logging.getLogger(__name__)


class TrialOutcome(str, Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    SKIP = "SKIP"   # evaluator returned None (dependency unavailable)
    ERROR = "ERROR"  # diff apply failed or evaluator crashed


class HillClimbingRunner:
    """Runs hill-climbing experiments for one track.

    Args:
        track_name: Identifier used for Obsidian vault paths and logging.
        surface_path: Path to the mutable surface.py file the agent edits.
        program_md_path: Path to the program.md guidance file.
        evaluate_fn: Callable(surface_path) -> float | None. Returns metric
            score, or None if evaluation should be skipped (e.g. dependency down).
        obsidian_client: ObsidianClient instance for logging results.
        budget_secs: Wall-clock seconds allowed per evaluator run (unused in
            unit tests since evaluate_fn is a mock).
        anthropic_api_key: Key for Claude API calls in _propose_diff.
    """

    def __init__(
        self,
        track_name: str,
        surface_path: Path,
        program_md_path: Path,
        evaluate_fn: Callable[[Path], Optional[float]],
        obsidian_client: ObsidianClient,
        budget_secs: int = 300,
        anthropic_api_key: str = "",
    ):
        self.track_name = track_name
        self.surface_path = surface_path
        self.program_md_path = program_md_path
        self.evaluate_fn = evaluate_fn
        self.obsidian = obsidian_client
        self.budget_secs = budget_secs
        self.anthropic_api_key = anthropic_api_key
        self.baseline_score: Optional[float] = None

    def run_one_trial(self, trial_num: int) -> TrialOutcome:
        """Run a single trial. Returns the outcome."""
        # Save current surface state for potential revert
        original_content = self.surface_path.read_text()

        # Evaluate current state — establishes baseline on first call,
        # confirms infrastructure is available on subsequent calls.
        current_score = self.evaluate_fn(self.surface_path)
        if current_score is None:
            return TrialOutcome.SKIP
        if self.baseline_score is None:
            self.baseline_score = current_score
            logger.info(f"[{self.track_name}] Initial baseline: {self.baseline_score:.4f}")

        # Ask Claude for a diff
        try:
            diff = self._propose_diff()
        except Exception as e:
            logger.error(f"[{self.track_name}] _propose_diff failed: {e}")
            return TrialOutcome.ERROR

        # Apply the diff
        try:
            self._apply_diff(diff)
        except Exception as e:
            logger.warning(f"[{self.track_name}] Diff apply failed: {e}")
            self.surface_path.write_text(original_content)
            return TrialOutcome.ERROR

        # Evaluate after applying the diff
        new_score = self.evaluate_fn(self.surface_path)
        if new_score is None:
            # Dependency unavailable — revert silently
            self.surface_path.write_text(original_content)
            return TrialOutcome.SKIP

        delta = new_score - self.baseline_score
        # Extract one-line hypothesis from diff header
        hypothesis = self._extract_hypothesis(diff)

        if new_score > self.baseline_score:
            outcome = TrialOutcome.WIN
            self.baseline_score = new_score
            result = ExperimentResult(
                track=self.track_name,
                trial=trial_num,
                score=new_score,
                baseline=self.baseline_score,
                delta=delta,
                outcome=outcome.value,
                hypothesis=hypothesis,
            )
            self.obsidian.log_result(result)
            self.obsidian.update_best(result)
            logger.info(
                f"[{self.track_name}] Trial {trial_num}: WIN "
                f"{new_score:.4f} (+{delta:.4f}) — {hypothesis}"
            )
        else:
            # Revert
            self.surface_path.write_text(original_content)
            outcome = TrialOutcome.LOSS
            result = ExperimentResult(
                track=self.track_name,
                trial=trial_num,
                score=new_score,
                baseline=self.baseline_score,
                delta=delta,
                outcome=outcome.value,
                hypothesis=hypothesis,
            )
            self.obsidian.log_result(result)
            logger.info(
                f"[{self.track_name}] Trial {trial_num}: LOSS "
                f"{new_score:.4f} ({delta:.4f}) — reverted"
            )

        return outcome

    def run(self, max_trials: int = 50) -> dict:
        """Run up to max_trials trials. Returns summary dict."""
        wins, losses, skips, errors = 0, 0, 0, 0
        for i in range(1, max_trials + 1):
            outcome = self.run_one_trial(i)
            if outcome == TrialOutcome.WIN:
                wins += 1
            elif outcome == TrialOutcome.LOSS:
                losses += 1
            elif outcome == TrialOutcome.SKIP:
                skips += 1
            else:
                errors += 1
        return {
            "track": self.track_name,
            "trials": max_trials,
            "wins": wins,
            "losses": losses,
            "skips": skips,
            "errors": errors,
            "best_score": self.baseline_score,
        }

    def _propose_diff(self) -> str:
        """Call Claude API to propose a unified diff for surface.py."""
        import anthropic

        surface_code = self.surface_path.read_text()
        program_guidance = self.program_md_path.read_text()

        client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"# Guidance\n{program_guidance}\n\n"
                        f"# Current surface.py\n```python\n{surface_code}\n```\n\n"
                        "Propose ONE targeted change to improve the metric. "
                        "Return ONLY a unified diff (--- a/surface.py / +++ b/surface.py format). "
                        "No explanation, no markdown fences."
                    ),
                }
            ],
        )
        return message.content[0].text.strip()

    def _apply_diff(self, diff: str) -> None:
        """Apply a unified diff to surface_path using the `patch` CLI tool."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".patch", delete=False
        ) as f:
            f.write(diff)
            patch_file = f.name
        result = subprocess.run(
            ["patch", str(self.surface_path), patch_file],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"patch failed: {result.stderr}"
            )

    def _extract_hypothesis(self, diff: str) -> str:
        """Extract a one-line description from the first +/- lines of a diff."""
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                return line[1:].strip()[:120]
        return diff[:120]
