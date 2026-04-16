"""
MetricCalculator - 指标计算引擎（纯计算，无副作用）

Formula DSL (JSON):
  {"op":"count", "source":"<col_id_or_name>", "filter":{...}}
  {"op":"count_distinct", "source":"...", "field":"metadata.category"}
  {"op":"sum", "source":"...", "field":"metadata.score", "filter":{...}}
  {"op":"avg", "source":"...", "field":"...", "filter":{...}}
  {"op":"ratio", "numerator":<formula>, "denominator":<formula>}
  {"op":"distribution", "source":"...", "group_by":"tags", "top_k":20}

Filter DSL (nested):
  {"tag":"x"}                          -> has tag "x"
  {"tags":["a","b"]}                   -> has ALL tags
  {"content_type":"text"}
  {"created_by":"ai"}
  {"created_after":"2026-01-01T00:00:00Z"}
  {"created_before":"2026-12-31T23:59:59Z"}
  {"metadata":{"category":"web3"}}     -> metadata.category == "web3"
  {"and":[<filter>, <filter>]}
  {"or":[<filter>, <filter>]}
  {"not":<filter>}
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter
from typing import Any, Optional

from .models import MetricCalculationResult, MetricKind
from .store import XingkongzuoStore

logger = logging.getLogger(__name__)


class FormulaError(ValueError):
    """Formula DSL 结构或语义错误"""


SUPPORTED_OPS = {"count", "count_distinct", "sum", "avg", "ratio", "distribution"}

# Filter keys that can be pushed down to query_documents (SQL prefilter)
SQL_PUSHDOWN_KEYS = {
    "content_type",
    "created_by",
    "created_after",
    "created_before",
}


class MetricCalculator:
    """纯计算引擎：读 store，返回 MetricCalculationResult"""

    def __init__(self, store: XingkongzuoStore):
        self.store = store

    # ---- Public API ----

    def calculate(
        self,
        formula: dict,
        tenant_id: str = "default",
        metric_id: str = "",
    ) -> MetricCalculationResult:
        """执行 formula，返回计算结果。失败时 error 字段非空。"""
        if not isinstance(formula, dict):
            raise FormulaError("formula must be a dict")

        # Structural validation first — catches missing fields before dispatch
        self._validate_formula(formula)

        start = time.perf_counter()
        try:
            value_numeric, value_json, sample_count, kind = self._dispatch(
                formula, tenant_id
            )
        except FormulaError:
            raise
        except Exception as e:
            logger.exception("metric calc failed")
            duration = int((time.perf_counter() - start) * 1000)
            return MetricCalculationResult(
                metric_id=metric_id,
                kind=MetricKind.scalar.value,
                value_numeric=0.0,
                sample_count=0,
                duration_ms=duration,
                error=f"{type(e).__name__}: {e}",
            )

        duration = int((time.perf_counter() - start) * 1000)
        return MetricCalculationResult(
            metric_id=metric_id,
            kind=kind,
            value_numeric=float(value_numeric),
            value_json=value_json,
            sample_count=sample_count,
            duration_ms=duration,
        )

    def validate(self, formula: dict) -> None:
        """结构校验（不执行）。失败抛 FormulaError。"""
        self._validate_formula(formula)

    # ---- Dispatch ----

    def _dispatch(self, formula: dict, tenant_id: str) -> tuple:
        """分发到具体 op，返回 (value_numeric, value_json, sample_count, kind)"""
        op = formula.get("op")
        if op not in SUPPORTED_OPS:
            raise FormulaError(f"unknown op: {op!r}; supported: {sorted(SUPPORTED_OPS)}")

        if op == "count":
            v, c = self._op_count(formula, tenant_id)
            return v, None, c, MetricKind.scalar.value
        if op == "count_distinct":
            v, c = self._op_count_distinct(formula, tenant_id)
            return v, None, c, MetricKind.scalar.value
        if op == "sum":
            v, c = self._op_sum(formula, tenant_id)
            return v, None, c, MetricKind.scalar.value
        if op == "avg":
            v, c = self._op_avg(formula, tenant_id)
            return v, None, c, MetricKind.scalar.value
        if op == "ratio":
            v, vj, c = self._op_ratio(formula, tenant_id)
            return v, vj, c, MetricKind.ratio.value
        if op == "distribution":
            v, vj, c = self._op_distribution(formula, tenant_id)
            return v, vj, c, MetricKind.distribution.value
        raise FormulaError(f"dispatch fell through: {op}")

    # ---- Validation ----

    def _validate_formula(self, formula: Any) -> None:
        if not isinstance(formula, dict):
            raise FormulaError("formula must be a dict")
        op = formula.get("op")
        if op not in SUPPORTED_OPS:
            raise FormulaError(f"unknown op: {op!r}")

        if op == "ratio":
            if "numerator" not in formula or "denominator" not in formula:
                raise FormulaError("ratio requires numerator + denominator")
            self._validate_formula(formula["numerator"])
            self._validate_formula(formula["denominator"])
            return

        if "source" not in formula or not formula["source"]:
            raise FormulaError(f"{op} requires non-empty source")

        if op in {"count_distinct", "sum", "avg"}:
            if not formula.get("field"):
                raise FormulaError(f"{op} requires field")

        if op == "distribution":
            if not formula.get("group_by"):
                raise FormulaError("distribution requires group_by")

    # ---- Op implementations ----

    def _op_count(self, f: dict, tenant_id: str) -> tuple[float, int]:
        docs = self._load_source_docs(f.get("source"), f.get("filter"), tenant_id)
        return float(len(docs)), len(docs)

    def _op_count_distinct(self, f: dict, tenant_id: str) -> tuple[float, int]:
        field = f["field"]
        docs = self._load_source_docs(f.get("source"), f.get("filter"), tenant_id)
        values = set()
        for d in docs:
            v = self._resolve_field(d, field)
            if v is None:
                continue
            if isinstance(v, list):
                for item in v:
                    values.add(item)
            else:
                values.add(v)
        return float(len(values)), len(docs)

    def _op_sum(self, f: dict, tenant_id: str) -> tuple[float, int]:
        field = f["field"]
        docs = self._load_source_docs(f.get("source"), f.get("filter"), tenant_id)
        total = 0.0
        for d in docs:
            v = self._resolve_field(d, field)
            if v is None:
                continue
            try:
                total += float(v)
            except (TypeError, ValueError):
                continue
        return total, len(docs)

    def _op_avg(self, f: dict, tenant_id: str) -> tuple[float, int]:
        field = f["field"]
        docs = self._load_source_docs(f.get("source"), f.get("filter"), tenant_id)
        total = 0.0
        n = 0
        for d in docs:
            v = self._resolve_field(d, field)
            if v is None:
                continue
            try:
                total += float(v)
                n += 1
            except (TypeError, ValueError):
                continue
        avg = (total / n) if n > 0 else 0.0
        return avg, len(docs)

    def _op_ratio(self, f: dict, tenant_id: str) -> tuple[float, Optional[str], int]:
        numerator = f.get("numerator")
        denominator = f.get("denominator")
        if not numerator or not denominator:
            raise FormulaError("ratio requires numerator + denominator")

        num_v, _, num_c, _ = self._dispatch(numerator, tenant_id)
        den_v, _, den_c, _ = self._dispatch(denominator, tenant_id)

        if den_v == 0:
            return 0.0, json.dumps({"error": "division_by_zero"}), num_c + den_c
        ratio = num_v / den_v
        return ratio, None, num_c + den_c

    def _op_distribution(
        self, f: dict, tenant_id: str
    ) -> tuple[float, str, int]:
        field = f["group_by"]
        top_k = int(f.get("top_k", 20))
        docs = self._load_source_docs(f.get("source"), f.get("filter"), tenant_id)

        counter: Counter = Counter()
        for d in docs:
            v = self._resolve_field(d, field)
            if v is None:
                counter["__null__"] += 1
            elif isinstance(v, list):
                if not v:
                    counter["__null__"] += 1
                for item in v:
                    counter[str(item)] += 1
            else:
                counter[str(v)] += 1

        top = counter.most_common(top_k)
        top_keys = {k for k, _ in top}
        result: dict = {k: v for k, v in top}
        # Others bucket
        others = sum(v for k, v in counter.items() if k not in top_keys)
        if others > 0:
            result["__others__"] = others

        # value_numeric = unique bucket count, value_json = full distribution
        return float(len(counter)), json.dumps(result, ensure_ascii=False), len(docs)

    # ---- Helpers ----

    def _load_source_docs(
        self,
        source: Optional[str],
        filter_dsl: Optional[dict],
        tenant_id: str,
    ) -> list[dict]:
        """Resolve source to collection_id, load docs, apply filter."""
        if not source:
            raise FormulaError("source is required")

        # Resolve source: if UUID-like or exact id match, use directly;
        # otherwise look up by name.
        collection_id = source
        col = self.store.get_collection(source)
        if not col:
            col = self.store.get_collection_by_name(source, tenant_id=tenant_id)
            if col:
                collection_id = col["id"]
            else:
                raise FormulaError(f"source not found: {source}")

        # Split filter: SQL-pushdown vs Python post-filter
        pushdown, post_filter = self._split_filter(filter_dsl or {})

        docs = self.store.query_documents(
            collection_id=collection_id,
            content_type=pushdown.get("content_type"),
            created_by=pushdown.get("created_by"),
            created_after=pushdown.get("created_after"),
            created_before=pushdown.get("created_before"),
            limit=100000,
        )

        if post_filter:
            docs = [d for d in docs if self._apply_filter(d, post_filter)]
        return docs

    def _split_filter(self, f: dict) -> tuple[dict, dict]:
        """Split filter dsl into SQL pushdown keys and Python post-filter.
        Only flat top-level filter supports pushdown; and/or/not always post-filter.
        """
        if not f or any(k in f for k in ("and", "or", "not")):
            return {}, f
        pushdown = {k: v for k, v in f.items() if k in SQL_PUSHDOWN_KEYS}
        post = {k: v for k, v in f.items() if k not in SQL_PUSHDOWN_KEYS}
        return pushdown, post

    def _apply_filter(self, doc: dict, f: dict) -> bool:
        """Recursively evaluate filter DSL against a single doc."""
        if not f:
            return True
        if "and" in f:
            return all(self._apply_filter(doc, sub) for sub in f["and"])
        if "or" in f:
            return any(self._apply_filter(doc, sub) for sub in f["or"])
        if "not" in f:
            return not self._apply_filter(doc, f["not"])

        for key, expected in f.items():
            if key == "tag":
                tags = doc.get("tags") or []
                if expected not in tags:
                    return False
            elif key == "tags":
                tags = set(doc.get("tags") or [])
                if not set(expected).issubset(tags):
                    return False
            elif key == "metadata":
                if not isinstance(expected, dict):
                    return False
                meta = self._parse_metadata(doc)
                for mk, mv in expected.items():
                    if meta.get(mk) != mv:
                        return False
            elif key in SQL_PUSHDOWN_KEYS:
                if doc.get(key) != expected:
                    return False
            else:
                # Dotpath field match
                actual = self._resolve_field(doc, key)
                if actual != expected:
                    return False
        return True

    def _resolve_field(self, doc: dict, field: str) -> Any:
        """Resolve dotpath. First segment in top-level dict; 'metadata.xxx' goes into metadata_json."""
        if not field:
            return None
        parts = field.split(".")
        if parts[0] == "metadata":
            meta = self._parse_metadata(doc)
            cursor: Any = meta
            for p in parts[1:]:
                if isinstance(cursor, dict) and p in cursor:
                    cursor = cursor[p]
                else:
                    return None
            return cursor

        cursor = doc.get(parts[0])
        for p in parts[1:]:
            if isinstance(cursor, dict) and p in cursor:
                cursor = cursor[p]
            else:
                return None
        return cursor

    @staticmethod
    def _parse_metadata(doc: dict) -> dict:
        raw = doc.get("metadata_json")
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
