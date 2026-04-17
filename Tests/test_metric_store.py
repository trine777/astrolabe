"""Tests for Metric/MetricResult store CRUD."""

from __future__ import annotations

import json
import tempfile
import uuid
from pathlib import Path

import pytest

from xingtu.store import XingkongzuoStore


@pytest.fixture
def store(tmp_path: Path):
    s = XingkongzuoStore(tmp_path)
    s.initialize()
    return s


def _formula() -> str:
    return json.dumps({"op": "count", "source": "test_collection"})


def test_create_metric_idempotent(store):
    m1 = store.create_metric(
        id=str(uuid.uuid4()),
        name="unique_metric",
        formula_json=_formula(),
        kind="scalar",
        unit="count",
    )
    assert m1["name"] == "unique_metric"
    assert m1["status"] == "active"

    # Same name returns existing
    m2 = store.create_metric(
        id=str(uuid.uuid4()),
        name="unique_metric",
        formula_json=_formula(),
    )
    assert m2["id"] == m1["id"]


def test_list_and_get_metric(store):
    ids = []
    for i in range(3):
        m = store.create_metric(
            id=str(uuid.uuid4()),
            name=f"metric_{i}",
            formula_json=_formula(),
        )
        ids.append(m["id"])

    listed = store.list_metrics()
    assert len(listed) == 3

    got = store.get_metric(ids[0])
    assert got["name"] == "metric_0"


def test_update_metric(store):
    m = store.create_metric(
        id=str(uuid.uuid4()),
        name="m1",
        formula_json=_formula(),
    )
    updated = store.update_metric(m["id"], status="paused", description="paused now")
    assert updated["status"] == "paused"
    assert updated["description"] == "paused now"
    # updated_at bumped
    assert updated["updated_at"] >= m["updated_at"]


def test_metric_results_crud(store):
    m = store.create_metric(
        id=str(uuid.uuid4()),
        name="counter",
        formula_json=_formula(),
    )
    # Save 3 results
    for value in [10.0, 20.0, 30.0]:
        store.save_metric_result(
            {
                "id": str(uuid.uuid4()),
                "metric_id": m["id"],
                "value_numeric": value,
                "sample_count": int(value),
                "formula_snapshot": _formula(),
                "duration_ms": 5,
            }
        )

    results = store.get_metric_results(m["id"])
    assert len(results) == 3
    # Newest first
    values = [r["value_numeric"] for r in results]
    # Order may depend on timestamp granularity but all should be present
    assert set(values) == {10.0, 20.0, 30.0}

    latest = store.get_latest_metric_result(m["id"])
    assert latest is not None


def test_delete_metric_cascades_results(store):
    m = store.create_metric(
        id=str(uuid.uuid4()),
        name="to_delete",
        formula_json=_formula(),
    )
    store.save_metric_result(
        {
            "id": str(uuid.uuid4()),
            "metric_id": m["id"],
            "value_numeric": 42.0,
            "formula_snapshot": _formula(),
        }
    )
    assert store.get_latest_metric_result(m["id"]) is not None

    deleted = store.delete_metric(m["id"])
    assert deleted is True
    assert store.get_metric(m["id"]) is None
    # Results cascade-deleted
    assert store.get_metric_results(m["id"]) == []


def test_delete_nonexistent_metric(store):
    assert store.delete_metric("nonexistent") is False


def test_batch_save_metric_results(store):
    m = store.create_metric(
        id=str(uuid.uuid4()), name="batch", formula_json=_formula()
    )
    results = [
        {
            "id": str(uuid.uuid4()),
            "metric_id": m["id"],
            "value_numeric": float(i),
            "formula_snapshot": _formula(),
        }
        for i in range(5)
    ]
    count = store.save_metric_results(results)
    assert count == 5
    assert len(store.get_metric_results(m["id"])) == 5


def test_table_stats_includes_metrics(store):
    store.create_metric(
        id=str(uuid.uuid4()), name="x", formula_json=_formula()
    )
    stats = store.table_stats()
    assert "metrics" in stats
    assert "metric_results" in stats
    assert stats["metrics"] == 1
    assert stats["metric_results"] == 0
