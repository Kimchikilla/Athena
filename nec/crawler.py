"""직접 POST 로 후보자 결과 HTML 을 받아 파싱."""
import csv
import logging
import time
from pathlib import Path
from typing import Iterator

from curl_cffi import requests as cc

from nec.codes import ELECTIONS, ELECTION_ID, SIDO
from nec.parser import parse_candidates
from nec.cascade import load_or_fetch

INDEX = f"https://info.nec.go.kr/main/showDocument.xhtml?electionId={ELECTION_ID}&topMenuId=PC&secondMenuId=PCRI03"
POST_URL = "https://info.nec.go.kr/electioninfo/electionInfo_report.xhtml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("crawler")

OUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_form(election_code: str, city_code: str, sgg="-1", town="-1") -> dict:
    return {
        "electionId": ELECTION_ID,
        "requestURI": f"/electioninfo/{ELECTION_ID}/pc/pcri03_ex.jsp",
        "topMenuId": "PC",
        "secondMenuId": "PCRI03",
        "menuId": "PCRI03",
        "statementId": f"PCRI03_#{election_code}",
        "electionCode": election_code,
        "cityCode": city_code,
        "sggCityCode": sgg,
        "townCode": town,
        "sggTownCode": "0",
        "searchKeyword": "",
        "registType": "0",
    }


def post(session, data: dict, retries: int = 3) -> str:
    last = None
    for attempt in range(retries):
        try:
            r = session.post(
                POST_URL,
                data=data,
                headers={"Referer": INDEX, "Origin": "https://info.nec.go.kr"},
                timeout=30,
            )
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("retry %d/%d: %s", attempt + 1, retries, e)
            time.sleep(2 ** attempt)
    raise last  # type: ignore[misc]


def iter_targets(cascade: dict) -> Iterator[tuple[str, str, str, str, str, str]]:
    """(electionCode, electionName, cityCode, cityName, sgg, town) 조합 생성."""
    for elec_code, elec_name, level, _endpoint in ELECTIONS:
        elec_cascade = cascade.get(elec_code, {})
        for city_code, city_name in SIDO.items():
            entry = elec_cascade.get(city_code, {})
            if level == "city":
                yield elec_code, elec_name, city_code, city_name, "-1", "-1"
            elif level == "city+sgg":
                for sgg_opt in entry.get("sgg", []):
                    yield elec_code, elec_name, city_code, city_name, sgg_opt["code"], "-1"
            elif level == "city+town":
                for town_opt in entry.get("town", []):
                    yield elec_code, elec_name, city_code, city_name, "-1", town_opt["code"]


def crawl_all(cascade: dict, sleep_sec: float = 0.3) -> dict[str, list[dict]]:
    """선거유형별로 후보자 dict 리스트를 모은다."""
    by_election: dict[str, list[dict]] = {code: [] for code, *_ in ELECTIONS}
    counts = {code: 0 for code, *_ in ELECTIONS}

    with cc.Session(impersonate="chrome120") as s:
        # 쿠키 워밍업
        s.get(INDEX, timeout=30)

        targets = list(iter_targets(cascade))
        log.info("총 요청 수: %d", len(targets))

        for i, (elec_code, elec_name, city_code, city_name, sgg, town) in enumerate(targets, 1):
            data = make_form(elec_code, city_code, sgg, town)
            try:
                html = post(s, data)
            except Exception as e:  # noqa: BLE001
                log.error("실패 %s/%s/%s/%s: %s", elec_name, city_name, sgg, town, e)
                continue

            rows = parse_candidates(html)
            for r in rows:
                r["선거유형"] = elec_name
                r["시도"] = city_name
                r["조회_시도코드"] = city_code
                r["조회_sggCityCode"] = sgg
                r["조회_townCode"] = town
            by_election[elec_code].extend(rows)
            counts[elec_code] += len(rows)

            if i % 10 == 0 or len(rows):
                log.info(
                    "[%d/%d] %s / %s sgg=%s town=%s → %d명 (누적 %d)",
                    i, len(targets), elec_name, city_name, sgg, town, len(rows), counts[elec_code],
                )
            time.sleep(sleep_sec)

    return by_election


def dedupe(rows: list[dict]) -> list[dict]:
    """huboId 기준 중복 제거 (같은 후보가 여러 검색결과에 잡힐 수 있어서)."""
    seen = set()
    out = []
    for r in rows:
        key = r.get("huboId") or (r.get("성명"), r.get("시도"), r.get("선거구명"))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def save_csv(name: str, rows: list[dict]) -> Path:
    if not rows:
        log.info("[%s] 결과 없음 — CSV 생략", name)
        return OUT_DIR / f"{name}.csv"
    # 모든 키 union
    keys: list[str] = []
    seen = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    path = OUT_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    log.info("[%s] %d행 → %s", name, len(rows), path)
    return path


def main() -> None:
    cascade = load_or_fetch()
    by_election = crawl_all(cascade)
    for elec_code, elec_name, *_ in ELECTIONS:
        rows = dedupe(by_election.get(elec_code, []))
        save_csv(elec_name, rows)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
