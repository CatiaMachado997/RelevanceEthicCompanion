import importlib


def test_tracing_is_noop_by_default(monkeypatch):
    monkeypatch.delenv("DEEPEVAL_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    module = importlib.import_module("services.deepeval_tracing")

    def retrieve():
        return "ok"

    assert module.observe_retriever(retrieve) is retrieve


def test_langsmith_requires_api_key(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    module = importlib.import_module("services.deepeval_tracing")

    def retrieve():
        return "ok"

    assert module.observe_retriever(retrieve) is retrieve
