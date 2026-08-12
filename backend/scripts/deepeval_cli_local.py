"""Launch DeepEval CLI with safe defaults for resource-constrained Ollama.

DeepEval stores LOCAL_MODEL_API_KEY as SecretStr but compares it directly with
the string ``ollama``. Keep the workaround local and removable rather than
patching site-packages or persisting a DeepEval keystore.

DeepEval also evolves every generated scenario by default. Small local models
frequently leak that rewrite prompt or invent a new topic during this extra
pass. The base scenarios have already gone through DeepEval's quality filter,
so local generation disables evolution by default. Set
``DEEPEVAL_NUM_EVOLUTIONS`` to opt back in explicitly.
"""

import os

from deepeval.metrics import utils as metric_utils
from deepeval.synthesizer.config import EvolutionConfig

metric_utils.should_use_ollama_model = lambda: True

from deepeval.cli.generate import command as generate_command  # noqa: E402


class LocalSynthesizer(generate_command.Synthesizer):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "evolution_config",
            EvolutionConfig(
                num_evolutions=int(os.getenv("DEEPEVAL_NUM_EVOLUTIONS", "0"))
            ),
        )
        super().__init__(*args, **kwargs)


generate_command.Synthesizer = LocalSynthesizer

from deepeval.cli.main import app  # noqa: E402


if __name__ == "__main__":
    app()
