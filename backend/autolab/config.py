"""AutoResearch environment configuration."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AutolabSettings:
    budget_secs: int = field(default_factory=lambda: int(os.getenv("AUTOLAB_BUDGET_SECS", "300")))
    obsidian_api_key: str = field(default_factory=lambda: os.getenv("OBSIDIAN_API_KEY", ""))
    obsidian_base_url: str = field(
        default_factory=lambda: os.getenv("OBSIDIAN_BASE_URL", "https://127.0.0.1:27124")
    )
    obsidian_vault_path: str = field(
        default_factory=lambda: os.getenv("OBSIDIAN_VAULT_PATH", "EthicCompanion")
    )
    fallback_dir: str = field(
        default_factory=lambda: os.getenv(
            "AUTOLAB_FALLBACK_DIR",
            str(Path(__file__).parent / "results"),
        )
    )
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))


settings = AutolabSettings()
