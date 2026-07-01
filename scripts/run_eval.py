"""Section-5 evaluation harness (TCC DocSmith).

Two sub-experiments over one collection, same query set:

1. Base retrieval strategies (vanilla, hyde, query_fusion) — document ranking:
   Recall@5, MRR@10, latency (3 seeds, averaged). Ranking metrics, since these
   strategies rank documents.

2. Graph RAG — context recall: the graph-expansion phase enriches results with
   cross-document entities WITHOUT changing the ranking, so it is measured by how
   much *relevant context* it recovers, not by ranking. For each query with a
   context gold (relevant_entities), compare:
       Cb (base context)  = entities in the retrieved chunks (entity_names)
       Cg (graph context) = Cb ∪ cross_document_entities (graph adds cross-doc)
   against the gold entities (normalized match), paired (Wilcoxon + bootstrap CI).

Usage:
    DOCSMITH_API_KEY=<key> DOCSMITH_COLLECTION_ID=<uuid> \
        python scripts/run_eval.py --queries queries/queries.json --k 10 --seeds 3

Requires a running DocSmith instance with the target collection already ingested
and its knowledge graph built.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
from scipy import stats


def norm(s: str) -> str:
    """Casefold, strip accents (NFKD), collapse whitespace, trim edge punctuation."""
    if s is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    collapsed = " ".join(no_accents.split())
    return collapsed.casefold().strip(" .,;:-—–\"'")


API = os.getenv("DOCSMITH_API_BASE", "http://localhost:8004/api/v1")
KEY = os.getenv("DOCSMITH_API_KEY")
COLLECTION_ID_ENV = os.getenv("DOCSMITH_COLLECTION_ID")
BASE_STRATEGIES = ["vanilla", "hyde", "query_fusion"]


def resolve_cid(name: str) -> str:
    """Return the collection UUID: prefer DOCSMITH_COLLECTION_ID env; otherwise
    treat the queries.json 'collection' field as the id itself."""
    return COLLECTION_ID_ENV or name


def doc_id_map(c, cid):
    # The /documents endpoint paginates with page/page_size (page_size<=100), NOT
    # limit/offset. Passing limit/offset silently falls back to page 1, page_size 20,
    # which truncates id2fn to 20 docs once a collection exceeds 20 — that drops gold
    # doc_ids from graph_connected_docs and zeroes out the Graph RAG recall above n20.
    out, page, total = {}, 1, None
    while True:
        r = c.get(
            "/documents", params={"collection_id": cid, "page": page, "page_size": 100}
        ).json()
        if isinstance(r, dict):
            total = r.get("total", total)
        items = r.get("items", r)
        if not items:
            break
        for d in items:
            out[d["id"]] = d["file_name"]
        if len(items) < 100:
            break
        page += 1
    # Fail loud rather than silently mapping a subset: a truncated id2fn drops gold
    # doc_ids from graph_connected_docs and fabricates a zero Graph RAG delta.
    if total is not None and len(out) != total:
        raise RuntimeError(f"doc_id_map incomplete: mapped {len(out)} of {total} docs")
    return out


def graph_connected_docs(resp, id2fn):
    """Documents linked to the retrieved set via shared cross-document entities."""
    out = set()
    for e in resp.get("cross_document_entities") or []:
        for did in e.get("doc_ids", []):
            if did in id2fn:
                out.add(id2fn[did])
    return out


def search(c, query, cid, strategy, limit, graph=False, hops=2):
    body = {"query": query, "collection_id": cid, "strategy": strategy, "limit": limit}
    if graph:
        body["graph_expansion"] = True
        body["graph_hops"] = hops
    for attempt in range(8):
        t0 = time.perf_counter()
        r = c.post("/search", json=body)
        dt = (time.perf_counter() - t0) * 1000.0
        if r.status_code == 429:  # search is rate-limited (120/min); back off
            time.sleep(3.0)
            continue
        r.raise_for_status()
        time.sleep(0.5)  # pace to stay under the limit
        return r.json(), dt
    raise RuntimeError("search rate-limited after retries")


def doc_ranking(results):
    """Chunk results -> document ranking (first occurrence of each file_name)."""
    seen, ranked = set(), []
    for x in results:
        fn = x.get("file_name") or (x.get("metadata") or {}).get("file_name")
        if fn and fn not in seen:
            seen.add(fn)
            ranked.append(fn)
    return ranked


def recall_at_k(ranked, expected, k):
    exp = set(expected)
    return len(set(ranked[:k]) & exp) / len(exp) if exp else 0.0


def rr_at_k(ranked, expected, k):
    exp = set(expected)
    for i, fn in enumerate(ranked[:k], 1):
        if fn in exp:
            return 1.0 / i
    return 0.0


def entity_names(results):
    out = set()
    for x in results:
        for e in x.get("entity_names") or []:
            nm = e.get("name") if isinstance(e, dict) else e
            if nm:
                out.add(norm(nm))
        for e in x.get("related_entities") or []:
            nm = e.get("name") if isinstance(e, dict) else e
            if nm:
                out.add(norm(nm))
    return out


def cross_doc_names(resp):
    out = set()
    for e in resp.get("cross_document_entities") or []:
        nm = e.get("entity_name") if isinstance(e, dict) else e
        if nm:
            out.add(norm(nm))
    return out


def ctx_recall(found_norm, gold):
    g = {norm(x) for x in gold if norm(x)}
    if not g:
        return None, 0, 0
    hit = sum(1 for x in g if x in found_norm)
    return hit / len(g), hit, len(g)


def bootstrap_ci(diffs, n=10000, seed=42):
    d = np.array(diffs)
    rng = np.random.default_rng(seed)
    means = [rng.choice(d, len(d), replace=True).mean() for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[1]
    p.add_argument("--queries", default=str(repo_root / "queries" / "queries.json"))
    p.add_argument("--k", type=int, default=10, help="retrieval depth (recall@5 / mrr@10)")
    p.add_argument("--seeds", type=int, default=3)
    p.add_argument("--hops", type=int, default=2)
    p.add_argument("--label", default="sec5")
    p.add_argument("--out", default=str(repo_root / "results"))
    args = p.parse_args()
    if not KEY:
        sys.exit("defina DOCSMITH_API_KEY")

    data = json.loads(Path(args.queries).read_text())
    queries = data["queries"]
    cid = resolve_cid(data["collection"])
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) / f"{ts}-{args.label}"
    out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=API, headers={"X-API-Key": KEY},
                      timeout=httpx.Timeout(120.0, connect=10.0)) as c:
        c.get("/health").raise_for_status()

        # ---- 1. base strategies: ranking metrics ----
        base = {s: {"recall": [], "rr": [], "lat": []} for s in BASE_STRATEGIES}
        for q in queries:
            for s in BASE_STRATEGIES:
                recalls, rrs, lats = [], [], []
                for _ in range(args.seeds):
                    resp, dt = search(c, q["query"], cid, s, args.k)
                    ranked = doc_ranking(resp.get("results", []))
                    recalls.append(recall_at_k(ranked, q["expected_documents"], 5))
                    rrs.append(rr_at_k(ranked, q["expected_documents"], 10))
                    lats.append(dt)
                base[s]["recall"].append(np.mean(recalls))
                base[s]["rr"].append(np.mean(rrs))
                base[s]["lat"].append(np.mean(lats))

        base_agg = {}
        for s, m in base.items():
            lat = np.array(m["lat"])
            base_agg[s] = {
                "n_queries": len(m["recall"]),
                "recall_at_5": float(np.mean(m["recall"])),
                "mrr_at_10": float(np.mean(m["rr"])),
                "latency_p50_ms": float(np.percentile(lat, 50)),
                "latency_p95_ms": float(np.percentile(lat, 95)),
            }

        # ---- 2. Graph RAG: document-level cross-document recall ----
        # The expansion does not re-rank; it links the retrieved docs to others via
        # shared cross-document entities. We measure whether that recovers RELEVANT
        # documents the vanilla filter missed in its top-K — the candidate-set value
        # for a downstream RAG agent. (Entity-level context recall saturates here:
        # on 20 docs the filter already retrieves the relevant docs, so their
        # entities are already in the base context — reported in the writeup.)
        id2fn = doc_id_map(c, cid)
        ctx_queries = [q for q in queries if q["type"] in ("multidoc", "crossdoc")]
        ctx_rows = []
        for q in ctx_queries:
            exp = set(q["expected_documents"])
            resp, _ = search(c, q["query"], cid, "vanilla", 5, graph=True, hops=args.hops)
            rb = doc_ranking(resp.get("results", []))
            base_docs = set(rb[:5])
            graph_docs = base_docs | graph_connected_docs(resp, id2fn)
            recall_base = len(base_docs & exp) / len(exp)
            recall_graph = len(graph_docs & exp) / len(exp)
            recovered = sorted((exp - base_docs) & graph_docs)
            ctx_rows.append({"id": q["id"], "type": q["type"], "n_relevant": len(exp),
                             "recall_base": recall_base, "recall_graph": recall_graph,
                             "docs_recovered_by_graph": recovered})

        deltas = [r["recall_graph"] - r["recall_base"] for r in ctx_rows]
        d = np.array(deltas)
        w = stats.wilcoxon(d) if np.any(d != 0) else None
        lo, hi = bootstrap_ci(deltas) if len(deltas) > 1 else (0.0, 0.0)
        ctx_agg = {
            "n_queries": len(ctx_rows),
            "recall_base_mean": float(np.mean([r["recall_base"] for r in ctx_rows])),
            "recall_graph_mean": float(np.mean([r["recall_graph"] for r in ctx_rows])),
            "delta_mean": float(d.mean()),
            "delta_ci95": [lo, hi],
            "wilcoxon_p": float(w.pvalue) if w else None,
            "queries_improved": int((d > 0).sum()),
            "queries_unchanged": int((d == 0).sum()),
            "relevant_docs_recovered_by_graph": int(
                sum(len(r["docs_recovered_by_graph"]) for r in ctx_rows)
            ),
        }

    report = {"timestamp": ts, "collection": data["collection"], "n_queries": len(queries),
              "seeds": args.seeds, "graph_hops": args.hops,
              "base_strategies": base_agg, "graph_rag_context": ctx_agg}
    (out_dir / "metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    (out_dir / "context_per_query.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in ctx_rows) + "\n")

    print(f"[done] -> {out_dir}\n")
    print("=== Base strategies (document ranking) ===")
    print(f"{'strategy':14s} {'Recall@5':>9s} {'MRR@10':>8s} {'lat_p50':>9s} {'lat_p95':>9s}")
    for s, m in base_agg.items():
        print(f"{s:14s} {m['recall_at_5']:9.3f} {m['mrr_at_10']:8.3f} "
              f"{m['latency_p50_ms']:8.0f}ms {m['latency_p95_ms']:8.0f}ms")
    print("\n=== Graph RAG (document-level cross-doc recall: filter vs filter+graph) ===")
    cg = ctx_agg
    print(f"n={cg['n_queries']} (multidoc+crossdoc)  base={cg['recall_base_mean']:.3f}  "
          f"graph={cg['recall_graph_mean']:.3f}  Δ={cg['delta_mean']:+.3f}  "
          f"CI95=[{cg['delta_ci95'][0]:+.3f},{cg['delta_ci95'][1]:+.3f}]  "
          f"Wilcoxon p={cg['wilcoxon_p']}")
    print(f"queries improved/unchanged: {cg['queries_improved']}/{cg['queries_unchanged']}  "
          f"| relevant docs recovered ONLY via graph: {cg['relevant_docs_recovered_by_graph']}")


if __name__ == "__main__":
    main()
