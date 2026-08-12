from services.feature_flags import rag_rollout_config, rollout_variant


def test_rollout_assignment_is_stable(monkeypatch):
    monkeypatch.setenv("RAG_ROLLOUT_PERCENT", "50")
    first = rollout_variant(
        "RAG_ROLLOUT", "user-123", percent_env="RAG_ROLLOUT_PERCENT"
    )
    assert first == rollout_variant(
        "RAG_ROLLOUT", "user-123", percent_env="RAG_ROLLOUT_PERCENT"
    )


def test_rollout_can_be_forced_for_evaluation(monkeypatch):
    monkeypatch.setenv("RAG_ROLLOUT_FORCE_VARIANT", "treatment")
    monkeypatch.setenv("RAG_ROLLOUT_TOP_K", "3")
    config = rag_rollout_config("any-user")
    assert config["variant"] == "treatment"
    assert config["top_k"] == 3
