import json

from scripts.materialize_legacy_weaviate import materialize


def test_materialize_groups_orders_and_deduplicates(tmp_path):
    export = tmp_path / "objects.json"
    export.write_text(
        json.dumps(
            {
                "objects": [
                    {
                        "properties": {
                            "source": "policy.pdf",
                            "page": 1,
                            "start_index": 2,
                            "text": "second",
                        }
                    },
                    {
                        "properties": {
                            "source": "policy.pdf",
                            "page": 0,
                            "start_index": 1,
                            "text": "first",
                            "title": "Policy",
                        }
                    },
                    {
                        "properties": {
                            "source": "policy.pdf",
                            "page": 1,
                            "start_index": 3,
                            "text": "second",
                        }
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    written = materialize(export, tmp_path / "recovered")

    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "# Policy" in text
    assert "Recovered unique chunks: 2" in text
    assert text.index("first") < text.index("second")
    assert text.count("second") == 1
