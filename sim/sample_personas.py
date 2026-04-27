"""Nemotron-Personas-Korea 데이터셋에서 시도지사 후보가 있는 17개 시도별 N명 샘플링.

전체 100만 행을 메모리에 안 올리고 streaming 으로 시도별 reservoir sampling.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from datasets import load_dataset

OUT = Path(__file__).resolve().parent.parent / "data" / "personas_sample.json"
N_PER_SIDO = 300
SEED = 42

# Nemotron 의 province 값이 어떻게 표기되는지 한 번 보고 NEC SIDO 명과 매핑.
# 일반적으로 "서울", "서울특별시", "Seoul" 중 하나. 첫 행 봐서 자동 결정.
NEC_SIDO = {
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
    "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도",
    "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도",
    "제주특별자치도",
}


def normalize_province(v: str) -> str | None:
    """Nemotron province → NEC SIDO 풀 명칭."""
    if not v:
        return None
    v = v.strip()
    # 정확 매칭
    if v in NEC_SIDO:
        return v
    # 약어 매핑
    short_map = {
        "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시",
        "인천": "인천광역시", "광주": "광주광역시", "대전": "대전광역시",
        "울산": "울산광역시", "세종": "세종특별자치시", "경기": "경기도",
        "강원": "강원특별자치도", "강원도": "강원특별자치도",
        "충북": "충청북도", "충청북": "충청북도",
        "충남": "충청남도", "충청남": "충청남도",
        "전북": "전북특별자치도", "전라북": "전북특별자치도", "전라북도": "전북특별자치도",
        "전남": "전라남도", "전라남": "전라남도",
        "경북": "경상북도", "경상북": "경상북도",
        "경남": "경상남도", "경상남": "경상남도",
        "제주": "제주특별자치도", "제주도": "제주특별자치도",
    }
    return short_map.get(v)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    print("dataset streaming...", flush=True)
    ds = load_dataset(
        "nvidia/Nemotron-Personas-Korea",
        split="train",
        streaming=True,
    )

    # 첫 행으로 필드 확인
    iterator = iter(ds)
    first = next(iterator)
    print("필드:", list(first.keys())[:30])
    print("province 샘플:", first.get("province"))

    # 시도별 reservoir sampling
    rng = random.Random(SEED)
    bucket: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)  # 본 행 수

    def consider(row):
        prov = normalize_province(row.get("province", ""))
        if prov is None:
            return
        counts[prov] += 1
        b = bucket[prov]
        if len(b) < N_PER_SIDO:
            b.append(row)
        else:
            j = rng.randint(0, counts[prov] - 1)
            if j < N_PER_SIDO:
                b[j] = row

    consider(first)
    for i, row in enumerate(iterator, 2):
        consider(row)
        if i % 50_000 == 0:
            filled = sum(1 for k in NEC_SIDO if len(bucket.get(k, [])) >= N_PER_SIDO)
            print(f"  scanned={i:>7}  17시도 중 {filled} 채움", flush=True)
        # 모든 시도 다 채워졌으면 끝낼 수도 있지만 reservoir 정확성을 위해 끝까지

    sample: list[dict] = []
    for prov in sorted(NEC_SIDO):
        b = bucket.get(prov, [])
        print(f"  {prov:<10} 샘플 {len(b):>3}명 (전체 본 행수 {counts.get(prov, 0):>6})")
        sample.extend(b)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
    print(f"\n→ 저장: {OUT}  총 {len(sample)}명")


if __name__ == "__main__":
    main()
