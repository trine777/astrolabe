"""Tests for MetricCalculator — covers 6 ops + nested + error cases."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from xingtu.metrics import FormulaError, MetricCalculator
from xingtu.store import XingkongzuoStore


@pytest.fixture
def store(tmp_path: Path):
    s = XingkongzuoStore(tmp_path)
    s.initialize()
    return s


@pytest.fixture
def collection_with_docs(store):
    col = store.create_collection(
        id=str(uuid.uuid4()),
        name="sales",
        collection_type="structured",
    )
    # Create 10 docs with varied metadata
    docs = []
    for i in range(10):
        category = "web3" if i < 3 else ("ai" if i < 7 else "other")
        amount = float(i * 10 + 5)  # 5, 15, 25, ..., 95
        docs.append(
            {
                "id": f"doc-{i}",
                "collection_id": col["id"],
                "content": f"record {i}",
                "content_type": "text",
                "tags": ["active"] if i % 2 == 0 else ["archived"],
                "metadata_json": json.dumps(
                    {"category": category, "amount": amount, "flag": i < 5}
                ),
                "created_at": "2026-04-16T10:00:00Z",
                "updated_at": "2026-04-16T10:00:00Z",
                "created_by": "test",
            }
        )
    store.add_documents(docs)
    return col


@pytest.fixture
def calc(store):
    return MetricCalculator(store)


# ---- count ----

def test_count_all(calc, collection_with_docs):
    result = calc.calculate(
        {"op": "count", "source": collection_with_docs["id"]}
    )
    assert result.value_numeric == 10.0
    assert result.sample_count == 10
    assert result.error is None


def test_count_with_tag_filter(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count",
            "source": collection_with_docs["id"],
            "filter": {"tag": "active"},
        }
    )
    assert result.value_numeric == 5.0


def test_count_with_metadata_filter(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count",
            "source": collection_with_docs["id"],
            "filter": {"metadata": {"category": "web3"}},
        }
    )
    assert result.value_numeric == 3.0


# ---- count_distinct ----

def test_count_distinct_metadata_field(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count_distinct",
            "source": collection_with_docs["id"],
            "field": "metadata.category",
        }
    )
    assert result.value_numeric == 3.0  # web3, ai, other


# ---- sum ----

def test_sum_metadata_field(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "sum",
            "source": collection_with_docs["id"],
            "field": "metadata.amount",
        }
    )
    # 5 + 15 + ... + 95 = 500
    assert result.value_numeric == 500.0


# ---- avg ----

def test_avg_metadata_field(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "avg",
            "source": collection_with_docs["id"],
            "field": "metadata.amount",
        }
    )
    assert result.value_numeric == 50.0  # 500/10


# ---- ratio (nested) ----

def test_ratio_nested(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "ratio",
            "numerator": {
                "op": "count",
                "source": collection_with_docs["id"],
                "filter": {"metadata": {"category": "web3"}},
            },
            "denominator": {
                "op": "count",
                "source": collection_with_docs["id"],
            },
        }
    )
    assert result.value_numeric == 0.3  # 3/10
    assert result.kind == "ratio"


def test_ratio_division_by_zero(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "ratio",
            "numerator": {"op": "count", "source": collection_with_docs["id"]},
            "denominator": {
                "op": "count",
                "source": collection_with_docs["id"],
                "filter": {"metadata": {"category": "nonexistent"}},
            },
        }
    )
    assert result.value_numeric == 0.0
    assert result.value_json is not None
    assert "division_by_zero" in result.value_json


# ---- distribution ----

def test_distribution_by_metadata(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "distribution",
            "source": collection_with_docs["id"],
            "group_by": "metadata.category",
        }
    )
    assert result.value_numeric == 3.0  # 3 unique buckets
    dist = json.loads(result.value_json)
    assert dist["web3"] == 3
    assert dist["ai"] == 4
    assert dist["other"] == 3


def test_distribution_top_k_with_others(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "distribution",
            "source": collection_with_docs["id"],
            "group_by": "metadata.category",
            "top_k": 2,
        }
    )
    dist = json.loads(result.value_json)
    assert "ai" in dist  # largest bucket (4)
    assert "__others__" in dist


# ---- filter DSL ----

def test_and_filter(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count",
            "source": collection_with_docs["id"],
            "filter": {
                "and": [
                    {"tag": "active"},
                    {"metadata": {"flag": True}},
                ]
            },
        }
    )
    # active (i even: 0,2,4,6,8) and flag (i<5): i=0,2,4 → 3
    assert result.value_numeric == 3.0


def test_or_filter(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count",
            "source": collection_with_docs["id"],
            "filter": {
                "or": [
                    {"metadata": {"category": "web3"}},
                    {"metadata": {"category": "ai"}},
                ]
            },
        }
    )
    assert result.value_numeric == 7.0  # 3 + 4


def test_not_filter(calc, collection_with_docs):
    result = calc.calculate(
        {
            "op": "count",
            "source": collection_with_docs["id"],
            "filter": {"not": {"metadata": {"category": "other"}}},
        }
    )
    assert result.value_numeric == 7.0  # 10 - 3


# ---- source resolution ----

def test_source_by_name(calc, collection_with_docs):
    """source can be collection name, not just UUID."""
    result = calc.calculate({"op": "count", "source": "sales"})
    assert result.value_numeric == 10.0


# ---- errors ----

def test_unknown_op_raises(calc):
    with pytest.raises(FormulaError, match="unknown op"):
        calc.calculate({"op": "bogus", "source": "anything"})


def test_missing_source_raises(calc):
    with pytest.raises(FormulaError):
        calc.calculate({"op": "count"})


def test_source_not_found_raises(calc):
    with pytest.raises(FormulaError, match="source not found"):
        calc.calculate({"op": "count", "source": "nonexistent_collection"})


def test_count_distinct_missing_field_raises(calc):
    with pytest.raises(FormulaError):
        calc.calculate({"op": "count_distinct", "source": "x"})


def test_validate_only(calc):
    """validate() checks structure without executing."""
    calc.validate({"op": "count", "source": "any"})  # ok
    with pytest.raises(FormulaError):
        calc.validate({"op": "unknown"})


# ---- duration tracking ----

def test_duration_recorded(calc, collection_with_docs):
    result = calc.calculate({"op": "count", "source": collection_with_docs["id"]})
    assert result.duration_ms >= 0
