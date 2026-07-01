"""
Métricas de retrieval para o experimento.

- Recall@K: fração das queries em que ao menos 1 documento relevante aparece no top-K.
  (Quando há múltiplos relevantes, definimos como (relevantes ∩ top-K) / relevantes.)
- MRR@K (Mean Reciprocal Rank): média do recíproco do rank do primeiro relevante,
  ou 0 se nenhum relevante aparece no top-K.
- Latência: p50 e p95 em milissegundos.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


@dataclass
class Hit:
    """1 resultado de busca, no nível de documento (não chunk)."""
    document_file_name: str
    score: float


def recall_at_k(retrieved: list[Hit], expected: list[str], k: int) -> float:
    """Fração de relevantes que aparece no top-K."""
    if not expected:
        return 0.0
    top_k_files = {h.document_file_name for h in retrieved[:k]}
    hits = sum(1 for e in expected if e in top_k_files)
    return hits / len(expected)


def reciprocal_rank_at_k(retrieved: list[Hit], expected: list[str], k: int) -> float:
    """1 / rank do primeiro relevante (top-K), ou 0 se nenhum aparece."""
    expected_set = set(expected)
    for i, h in enumerate(retrieved[:k], start=1):
        if h.document_file_name in expected_set:
            return 1.0 / i
    return 0.0


def percentile(values: list[float], p: float) -> float:
    """p ∈ [0, 100]. Implementação simples sem numpy."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    frac = k - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def aggregate(per_query_recalls: list[float], per_query_rrs: list[float],
              per_query_latencies_ms: list[float]) -> dict:
    """Agrega métricas por estratégia."""
    return {
        "n_queries": len(per_query_recalls),
        "recall_at_k_mean": sum(per_query_recalls) / max(len(per_query_recalls), 1),
        "mrr_at_k": sum(per_query_rrs) / max(len(per_query_rrs), 1),
        "latency_ms_p50": median(per_query_latencies_ms) if per_query_latencies_ms else 0,
        "latency_ms_p95": percentile(per_query_latencies_ms, 95),
        "latency_ms_mean": sum(per_query_latencies_ms) / max(len(per_query_latencies_ms), 1),
    }
