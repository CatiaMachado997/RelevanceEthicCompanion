from orchestrator.nodes.context import bound_conversation_history


def test_history_budget_keeps_newest_complete_turns():
    history = [
        {"role": "user", "content": "a" * 80},
        {"role": "assistant", "content": "b" * 80},
        {"role": "user", "content": "latest"},
    ]
    bounded = bound_conversation_history(history, max_chars=100)
    assert bounded == [{"role": "user", "content": "latest"}]


def test_single_oversized_turn_is_truncated_from_the_front():
    bounded = bound_conversation_history(
        [{"role": "user", "content": "old" + "x" * 20 + "new"}], max_chars=10
    )
    assert bounded[0]["content"].endswith("new")
    assert len(bounded[0]["content"]) == 10
