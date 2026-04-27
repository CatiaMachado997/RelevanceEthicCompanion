# ESL Tuning — Program Guidance

## Objective
Maximize macro F1-score across three ESL decision classes: APPROVED, VETOED, MODIFIED.
A score of 1.0 means perfect classification on all 200 benchmark scenarios.
Current baseline is logged in Obsidian at EthicCompanion/Experiments/esl_tuning/best.md.

## Constraints
- Only edit threshold float/int values in the ESLConfig dataclass
- Do NOT add new fields or change field names
- Do NOT import anything not already in the file
- Each change should be a single threshold adjustment (one diff hunk)

## What Each Threshold Does
- `engagement_score_threshold` (0.0–1.0): higher = harder to trigger VETO for engagement
- `goal_relevance_min` (0.0–1.0): higher = stricter goal relevance requirement before VETO
- `manipulation_signal_threshold` (int): higher = more signals required before flagging
- `quiet_hours_start` / `quiet_hours_end` (0–23): quiet hour window
- `critical_urgency_relevance_min` (0.0–1.0): higher = stricter for CRITICAL urgency MODIFIED

## Hypothesis Format
State what you changed and why: "raised engagement_score_threshold 0.7→0.75 to reduce false VETO rate"
