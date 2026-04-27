"""Ollama 로컬 호출 + 응답 파싱 + 결과 누적 저장."""
import csv
import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

import httpx

from sim.prompt import build_prompt
from nec.codes import SIDO

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PERSONAS = DATA / "personas_sample.json"
SIDO_CSV = DATA / "시도지사.csv"
RESULTS = DATA / "vote_results.jsonl"
PROGRESS = DATA / "vote_progress.json"

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "gemma4:e4b"
NUM_PARALLEL = 2
TIMEOUT = 120.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("sim")

JSON_RE = re.compile(r"\{[^{}]*\"choice\"[^{}]*\}", re.S)


def load_candidates_by_sido() -> dict[str, list[dict]]:
    rows = list(csv.DictReader(SIDO_CSV.read_text(encoding="utf-8-sig").splitlines()))
    by_sido: dict[str, list[dict]] = {}
    for r in rows:
        by_sido.setdefault(r["시도"], []).append(r)
    return by_sido


def load_personas() -> list[dict]:
    return json.loads(PERSONAS.read_text(encoding="utf-8"))


def load_done() -> set[str]:
    """이미 처리한 페르소나 uuid (중단 후 재개용)."""
    if not RESULTS.exists():
        return set()
    done = set()
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        try:
            done.add(json.loads(line)["uuid"])
        except Exception:  # noqa: BLE001
            continue
    return done


def call_ollama(client: httpx.Client, system: str, user: str) -> str:
    # Gemma 4 의 thinking 모드를 끄고 (think=False) num_predict 충분히
    r = client.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0.6, "num_predict": 1000},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def parse_choice(text: str, n_candidates: int) -> tuple[int, str]:
    """LLM 응답에서 choice 번호와 이유 추출."""
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = JSON_RE.search(text)
        if not m:
            return -1, text[:200]
        try:
            obj = json.loads(m.group())
        except json.JSONDecodeError:
            return -1, text[:200]
    choice = obj.get("choice")
    reason = obj.get("reason", "")
    try:
        idx = int(choice)
    except (TypeError, ValueError):
        return -1, str(reason)[:300]
    # 범위 검증: 0(기권) 또는 1..n
    if idx < 0 or idx > n_candidates:
        return -1, str(reason)[:300]
    return idx, str(reason)[:300]


def vote_one(client: httpx.Client, persona: dict, sido: str, candidates: list[dict], system: str) -> dict:
    user = build_prompt(persona, sido, candidates)
    t0 = time.time()
    try:
        raw = call_ollama(client, system, user)
        choice, reason = parse_choice(raw, len(candidates))
    except Exception as e:  # noqa: BLE001
        return {
            "uuid": persona["uuid"],
            "sido": sido,
            "choice": -1,
            "reason": f"ERROR: {e}",
            "elapsed": time.time() - t0,
        }
    return {
        "uuid": persona["uuid"],
        "sido": sido,
        "age": persona.get("age"),
        "sex": persona.get("sex"),
        "district": persona.get("district"),
        "education_level": persona.get("education_level"),
        "choice": choice,
        "reason": reason,
        "elapsed": round(time.time() - t0, 2),
    }


def run() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    from sim.prompt import SYSTEM as SYSTEM_PROMPT
    candidates_map = load_candidates_by_sido()
    personas = load_personas()
    done = load_done()
    log.info("페르소나 %d명 / 이미 완료 %d명 / 시도 %d개", len(personas), len(done), len(candidates_map))

    todo = []
    for p in personas:
        if p["uuid"] in done:
            continue
        sido_name = (
            p.get("province")
            and {
                "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
                "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
                "경기": "경기도", "강원": "강원특별자치도", "충청북": "충청북도", "충청남": "충청남도",
                "전북": "전북특별자치도", "전라남": "전라남도", "경상북": "경상북도", "경상남": "경상남도",
                "제주": "제주특별자치도",
            }.get(p["province"], p["province"])
        )
        cands = candidates_map.get(sido_name, [])
        if not cands:
            continue
        todo.append((p, sido_name, cands))

    log.info("실행할 호출 수: %d", len(todo))
    if not todo:
        return

    DATA.mkdir(parents=True, exist_ok=True)
    out_f = RESULTS.open("a", encoding="utf-8")

    t_start = time.time()
    processed = 0
    with httpx.Client(http2=False) as client:
        with ThreadPoolExecutor(max_workers=NUM_PARALLEL) as pool:
            futures = {
                pool.submit(vote_one, client, p, sido, cands, SYSTEM_PROMPT): (p, sido)
                for p, sido, cands in todo
            }
            for fut in as_completed(futures):
                res = fut.result()
                out_f.write(json.dumps(res, ensure_ascii=False) + "\n")
                out_f.flush()
                processed += 1
                if processed % 25 == 0:
                    elapsed = time.time() - t_start
                    rate = processed / elapsed
                    eta = (len(todo) - processed) / rate if rate else 0
                    log.info(
                        "[%d/%d] rate=%.2f/s ETA=%.0fmin last_choice=%s",
                        processed, len(todo), rate, eta / 60, res.get("choice"),
                    )

    out_f.close()
    log.info("완료: %d 건, 총 %.1f분", processed, (time.time() - t_start) / 60)


if __name__ == "__main__":
    run()
