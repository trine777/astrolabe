"""End-to-end tests for Metric service integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xingtu import XingTuService
from xingtu.config import XingTuConfig, StoreConfig, EmbeddingConfig
from xingtu.metrics import FormulaError


@pytest.fixture
def service(tmp_path: Path):
    config = XingTuConfig(
        store=StoreConfig(db_path=str(tmp_path)),
        embedding=EmbeddingConfig(provider="none"),
    )
    s = XingTuService(config)
    s.initialize()
    return s


def test_create_metric_with_validation(service):
    """Valid formula accepted, invalid rejected."""
    metric = service.create_metric(
        name="test_count",
        formula={"op": "count", "source": "any"},
        kind="scalar",
        unit="count",
        tags=["test"],
    )
    assert metric["name"] == "test_count"
    assert metric["status"] == "active"

    # Invalid formula → FormulaError
    with pytest.raises(FormulaError):
        service.create_metric(
            name="bad",
            formula={"op": "unknown_op"},
        )


def test_calculate_metric_end_to_end(service):
    """Create collection + docs + metric + calculate → correct value."""
    col = service.create_collection(name="e2e_col", collection_type="structured")
    # Add 5 docs manually via store (service.add_documents wraps differently)
    docs = [
        {
            "id": f"d{i}",
            "collection_id": col["id"],
            "content": f"item {i}",
            "content_type": "text",
            "tags": ["x"] if i < 3 else ["y"],
            "metadata_json": json.dumps({"category": "a" if i % 2 == 0 else "b"}),
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
            "created_by": "test",
        }
        for i in range(5)
    ]
    service.store.add_documents(docs)

    metric = service.create_metric(
        name="e2e_counter",
        formula={"op": "count", "source": col["id"]},
    )

    out = service.calculate_metric(metric["id"])
    assert out["result"]["value_numeric"] == 5.0
    assert out["result"]["error"] is None


def test_calculate_metric_persists_and_history(service):
    col = service.create_collection(name="hist_col")
    service.store.add_documents([
        {
            "id": "d1",
            "collection_id": col["id"],
            "content": "x",
            "content_type": "text",
            "tags": [],
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
            "created_by": "test",
        }
    ])

    metric = service.create_metric(
        name="hist_metric",
        formula={"op": "count", "source": col["id"]},
    )

    # Calculate 3 times
    for _ in range(3):
        service.calculate_metric(metric["id"])

    history = service.get_metric_history(metric["id"])
    assert len(history) == 3


def test_update_metric_validates_formula(service):
    metric = service.create_metric(
        name="upd",
        formula={"op": "count", "source": "x"},
    )

    # Valid update
    updated = service.update_metric(
        metric["id"], formula={"op": "sum", "source": "x", "field": "metadata.amount"}
    )
    assert updated is not None
    assert '"sum"' in updated["formula_json"]

    # Invalid update rejected
    with pytest.raises(FormulaError):
        service.update_metric(metric["id"], formula={"op": "garbage"})


def test_calculate_emits_inferred_event(service):
    col = service.create_collection(name="evt_col")
    service.store.add_documents([
        {
            "id": "e1",
            "collection_id": col["id"],
            "content": "test",
            "content_type": "text",
            "tags": [],
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
            "created_by": "test",
        }
    ])
    metric = service.create_metric(
        name="evt_metric",
        formula={"op": "count", "source": col["id"]},
    )
    service.calculate_metric(metric["id"])

    # Check events
    events = service.store.get_events(target_id=metric["id"])
    event_types = [e["event_type"] for e in events]
    assert "inferred" in event_types


def test_batch_calculate_handles_failures(service):
    col = service.create_collection(name="batch_col")
    service.store.add_documents([
        {
            "id": "b1",
            "collection_id": col["id"],
            "content": "x",
            "content_type": "text",
            "tags": [],
            "created_at": "2026-04-16T10:00:00Z",
            "updated_at": "2026-04-16T10:00:00Z",
            "created_by": "test",
        }
    ])

    m1 = service.create_metric(
        name="good", formula={"op": "count", "source": col["id"]}
    )

    results = service.calculate_metrics_batch([m1["id"], "nonexistent-id"])
    assert len(results) == 2
    # First succeeds
    assert results[0]["result"]["error"] is None
    # Second fails gracefully
    assert results[1]["result"].get("error") is not None


def test_delete_metric_removes_events_target(service):
    metric = service.create_metric(
        name="to_del", formula={"op": "count", "source": "x"}
    )
    assert service.delete_metric(metric["id"]) is True
    assert service.get_metric(metric["id"]) is None
