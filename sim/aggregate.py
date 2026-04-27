"""투표 시뮬레이션 결과(JSONL) 를 집계해 CSV/리포트 생성."""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = DATA / "vote_results.jsonl"
SIDO_CSV = DATA / "시도지사.csv"


def load_results() -> list[dict]:
    if not RESULTS.exists():
        return []
    return [json.loads(l) for l in RESULTS.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_candidates() -> dict[str, list[dict]]:
    rows = list(csv.DictReader(SIDO_CSV.read_text(encoding="utf-8-sig").splitlines()))
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["시도"], []).append(r)
    return out


def candidate_label(c: dict) -> str:
    name = (c.get("성명(한자)") or "").splitlines()[0].strip().replace(" ", "")
    return f"{name}({c.get('소속정당명','')})"


def report() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cand_map = load_candidates()
    rows = load_results()
    if not rows:
        print("결과 없음")
        return

    by_sido: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_sido[r["sido"]].append(r)

    print(f"총 투표 시뮬레이션: {len(rows):,}건\n")
    print("=" * 90)

    summary_rows: list[dict] = []
    for sido in sorted(by_sido.keys()):
        votes = by_sido[sido]
        cands = cand_map.get(sido, [])
        if not cands:
            continue
        labels = [candidate_label(c) for c in cands]
        counter = Counter(v["choice"] for v in votes)
        total = len(votes)
        valid_total = sum(n for c, n in counter.items() if 1 <= c <= len(cands))
        invalid = counter.get(-1, 0)
        abstain = counter.get(0, 0)

        print(f"\n■ {sido}  (시뮬 {total:,}명, 유효 {valid_total:,}명, 기권 {abstain}, 파싱실패 {invalid})")
        ranked = sorted(
            [(i, labels[i - 1], counter.get(i, 0)) for i in range(1, len(cands) + 1)],
            key=lambda x: -x[2],
        )
        for rank, (idx, label, n) in enumerate(ranked, 1):
            pct = n / valid_total * 100 if valid_total else 0
            print(f"  {rank}위  [{idx}] {label:<30}  {n:>4}표  ({pct:5.1f}%)")
            summary_rows.append({
                "시도": sido, "후보번호": idx, "후보": label,
                "득표": n, "득표율": round(pct, 2),
                "전체시뮬": total, "유효": valid_total, "기권": abstain, "파싱실패": invalid,
            })

    # CSV 저장
    out = DATA / "vote_summary.csv"
    if summary_rows:
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader(); w.writerows(summary_rows)
        print(f"\n→ CSV 저장: {out}")


if __name__ == "__main__":
    report()
