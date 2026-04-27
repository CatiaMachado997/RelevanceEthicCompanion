# Prompt Optimisation — Experiment Program

## Goal

Improve the mean quality score of the ORCHESTRATOR_SYSTEM_PROMPT and ESL_EVALUATION_PROMPT
as judged by a Groq LLM evaluator across 30 synthetic user conversations.

## Metric

Mean judge score [0, 1] over 30 test conversations.
Current baseline is established on first trial.

## What to optimise

File: `backend/autolab/tracks/prompt_opt/surface.py`

Mutable fields:
- `ORCHESTRATOR_SYSTEM_PROMPT` — the system prompt sent to the assistant model
- `ESL_EVALUATION_PROMPT` — the prompt used to judge proposed actions
- `config` dict — model parameters (temperature, max_tokens)

## Rules

1. Return ONLY a unified diff (--- a/surface.py / +++ b/surface.py format).
2. Make ONE targeted change per trial.
3. Do NOT change the file structure or remove any exported names.
4. Do NOT change `config["model"]` or `config["judge_model"]`.

## Hypotheses to explore

- Clearer role definition in ORCHESTRATOR_SYSTEM_PROMPT
- More specific evaluation criteria in ESL_EVALUATION_PROMPT
- Lower temperature for more consistent outputs
- Adding few-shot examples to the evaluation prompt
- Explicit chain-of-thought instructions
