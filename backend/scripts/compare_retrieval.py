import argparse
from pathlib import Path
import re
import sys

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = BASE_DIR / "data" / "reports" / "retrieval_compare.md"
sys.path.append(str(BASE_DIR))

from app.evals.fixed_questions import FIXED_RETRIEVAL_QUESTIONS
from app.services.embeddings import embed_query
from app.services.vector_store import query_similarity_k, query_top_k


def _safe_score(distance: object) -> float | None:
    if isinstance(distance, (int, float)):
        return max(0.0, min(1.0, 1.0 - float(distance)))
    return None


def _normalize_text(text: str, max_len: int = 90) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= max_len:
        return flat
    return flat[:max_len].rstrip() + "..."


def _extract_rows(result: dict, top_n: int) -> list[dict]:
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    rows: list[dict] = []
    for idx, doc in enumerate(docs[:top_n]):
        meta = metas[idx] if idx < len(metas) and isinstance(metas[idx], dict) else {}
        dist = dists[idx] if idx < len(dists) else None
        rows.append(
            {
                "title": str(meta.get("filename", "")) or None,
                "page": meta.get("page") if isinstance(meta.get("page"), int) else None,
                "score": _safe_score(dist),
                "snippet": _normalize_text(str(doc)),
            }
        )
    return rows


def _page_signature(rows: list[dict]) -> str:
    pages: list[str] = []
    for row in rows:
        page = row.get("page")
        pages.append(f"p.{page}" if isinstance(page, int) else "p.?")
    return ", ".join(pages) if pages else "-"


def _unique_page_count(rows: list[dict]) -> int:
    return len({row["page"] for row in rows if isinstance(row.get("page"), int)})


def _avg_score(rows: list[dict]) -> float:
    vals = [row["score"] for row in rows if isinstance(row.get("score"), float)]
    return (sum(vals) / len(vals)) if vals else 0.0


def run_compare(sim_k: int, mmr_k: int) -> tuple[str, str]:
    # Load backend/.env so embedding API key/model are available.
    load_dotenv(BASE_DIR / ".env")

    summary_lines = [
        "# Retrieval Comparison",
        "",
        f"- Baseline: similarity_search(k={sim_k})",
        f"- Current: MMR search(k={mmr_k})",
        "",
        "| # | Question | Similarity pages | MMR pages | Unique pages (sim->mmr) | Avg score (sim->mmr) |",
        "|---|---|---|---|---|---|",
    ]

    detail_lines = ["", "## Details", ""]

    sim_unique_total = 0
    mmr_unique_total = 0
    sim_score_total = 0.0
    mmr_score_total = 0.0

    for idx, question in enumerate(FIXED_RETRIEVAL_QUESTIONS, start=1):
        embedding = embed_query(question)
        sim_result = query_similarity_k(embedding, k=sim_k)
        mmr_result = query_top_k(embedding, k=mmr_k)

        sim_rows = _extract_rows(sim_result, top_n=sim_k)
        mmr_rows = _extract_rows(mmr_result, top_n=mmr_k)

        sim_unique = _unique_page_count(sim_rows)
        mmr_unique = _unique_page_count(mmr_rows)
        sim_avg = _avg_score(sim_rows)
        mmr_avg = _avg_score(mmr_rows)

        sim_unique_total += sim_unique
        mmr_unique_total += mmr_unique
        sim_score_total += sim_avg
        mmr_score_total += mmr_avg

        summary_lines.append(
            f"| {idx} | {question} | {_page_signature(sim_rows)} | {_page_signature(mmr_rows)} | "
            f"{sim_unique} -> {mmr_unique} | {sim_avg:.3f} -> {mmr_avg:.3f} |"
        )

        detail_lines.append(f"### Q{idx}. {question}")
        detail_lines.append("")
        detail_lines.append("**Similarity top-k**")
        for row in sim_rows:
            detail_lines.append(
                f"- `{row['title'] or 'unknown'}` / `p.{row['page'] or '?'}` / score `{(row['score'] or 0.0):.3f}`"
            )
            detail_lines.append(f"  - {row['snippet']}")
        detail_lines.append("")
        detail_lines.append("**MMR top-k**")
        for row in mmr_rows:
            detail_lines.append(
                f"- `{row['title'] or 'unknown'}` / `p.{row['page'] or '?'}` / score `{(row['score'] or 0.0):.3f}`"
            )
            detail_lines.append(f"  - {row['snippet']}")
        detail_lines.append("")

    count = len(FIXED_RETRIEVAL_QUESTIONS)
    summary_lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Avg unique pages per question: `{sim_unique_total / count:.2f}` -> `{mmr_unique_total / count:.2f}`",
            f"- Avg similarity-like score per question: `{sim_score_total / count:.3f}` -> `{mmr_score_total / count:.3f}`",
            "",
            "> Interpretation tip: MMR should usually increase page diversity and reduce near-duplicate sources.",
        ]
    )

    return "\n".join(summary_lines), "\n".join(detail_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare similarity retrieval vs MMR retrieval.")
    parser.add_argument("--sim-k", type=int, default=3, help="Top-k for baseline similarity retrieval")
    parser.add_argument("--mmr-k", type=int, default=5, help="Top-k for current MMR retrieval")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Markdown report output path",
    )
    args = parser.parse_args()

    summary, details = run_compare(sim_k=args.sim_k, mmr_k=args.mmr_k)
    report = f"{summary}\n{details}\n"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    try:
        print(report)
    except UnicodeEncodeError:
        # Windows console(cp949) fallback: keep report file intact and print a safe version.
        print(report.encode("cp949", errors="ignore").decode("cp949", errors="ignore"))
    print(f"\nSaved report: {args.output}")


if __name__ == "__main__":
    main()
