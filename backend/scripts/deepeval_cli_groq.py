"""Launch DeepEval against Groq's OpenAI-compatible endpoint."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent.parent
load_dotenv(backend_dir / ".env.local", override=False)
load_dotenv(backend_dir / ".env", override=False)

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise SystemExit("GROQ_API_KEY is not configured")

os.environ.update(
    {
        "DEEPEVAL_TELEMETRY_OPT_OUT": "1",
        "DEEPEVAL_UPDATE_WARNING_OPT_IN": "0",
        "ERROR_REPORTING": "0",
        "USE_LOCAL_MODEL": "1",
        "LOCAL_MODEL_API_KEY": api_key,
        "LOCAL_MODEL_NAME": os.environ.get("GROQ_EVAL_MODEL", "openai/gpt-oss-20b"),
        "LOCAL_MODEL_BASE_URL": "https://api.groq.com/openai/v1",
        "LOCAL_MODEL_FORMAT": "json",
    }
)

# DeepEval 4.1's LocalModel stores LOCAL_MODEL_FORMAT but does not forward it
# to OpenAI-compatible chat completions. Groq requires prompts to mention JSON
# when JSON Object Mode is enabled, while DeepEval also sends plain-text
# evolution prompts. Enable JSON mode only for prompts that request it.
from deepeval.models.llms.local_model import LocalModel  # noqa: E402

_local_model_generate = LocalModel.generate
_local_model_a_generate = LocalModel.a_generate


def _needs_json_mode(prompt, schema) -> bool:
    return schema is not None or "json" in str(prompt).lower()


def _generate_with_conditional_json(self, prompt, schema=None):
    original_kwargs = self.generation_kwargs
    self.generation_kwargs = dict(original_kwargs)
    if _needs_json_mode(prompt, schema):
        self.generation_kwargs.setdefault("response_format", {"type": "json_object"})
    try:
        return _local_model_generate(self, prompt, schema)
    finally:
        self.generation_kwargs = original_kwargs


async def _a_generate_with_conditional_json(self, prompt, schema=None):
    original_kwargs = self.generation_kwargs
    self.generation_kwargs = dict(original_kwargs)
    if _needs_json_mode(prompt, schema):
        self.generation_kwargs.setdefault("response_format", {"type": "json_object"})
    try:
        return await _local_model_a_generate(self, prompt, schema)
    finally:
        self.generation_kwargs = original_kwargs


LocalModel.generate = _generate_with_conditional_json
LocalModel.a_generate = _a_generate_with_conditional_json

from deepeval.cli.main import app  # noqa: E402

if __name__ == "__main__":
    app()
