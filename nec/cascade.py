"""각 (선거유형, 시도) 조합의 sggCityCode/townCode 옵션을 NEC selectbox JSON 으로 직접 호출.

Playwright 없이 100여 회 POST 로 끝남.
"""
import json
import sys
from pathlib import Path

from curl_cffi import requests as cc

from nec.codes import SIDO, ELECTIONS, ELECTION_ID

INDEX = f"https://info.nec.go.kr/main/showDocument.xhtml?electionId={ELECTION_ID}&topMenuId=PC&secondMenuId=PCRI03"
ENDPOINT_BASE = "https://info.nec.go.kr/bizcommon/selectbox/"
OUT = Path(__file__).resolve().parent.parent / "data" / "cascade.json"


def fetch_options(session, endpoint: str, election_code: str, city_code: str) -> list[dict]:
    """selectbox JSON endpoint 를 호출해 옵션 리스트를 반환."""
    if endpoint is None:
        return []
    r = session.post(
        ENDPOINT_BASE + endpoint,
        data={"electionId": ELECTION_ID, "electionCode": election_code, "cityCode": city_code},
        headers={"Referer": INDEX, "X-Requested-With": "XMLHttpRequest", "Origin": "https://info.nec.go.kr"},
        timeout=20,
    )
    r.raise_for_status()
    js = r.json()
    body = js.get("jsonResult", {}).get("body", []) or []
    return [
        {"code": str(item["CODE"]), "name": item["NAME"]}
        for item in body
        if str(item.get("CODE", "-1")) not in ("-1", "0")
    ]


def fetch_cascade() -> dict:
    out: dict = {}
    with cc.Session(impersonate="chrome120") as s:
        s.get(INDEX, timeout=30)  # 쿠키 워밍업

        for elec_code, elec_name, level, endpoint in ELECTIONS:
            out[elec_code] = {}
            print(f"\n[{elec_code}] {elec_name} (level={level} endpoint={endpoint})", flush=True)

            for city_code, city_name in SIDO.items():
                opts: list[dict] = []
                if endpoint:
                    try:
                        opts = fetch_options(s, endpoint, elec_code, city_code)
                    except Exception as e:  # noqa: BLE001
                        print(f"  ! {city_code} {city_name}: {e}")
                        opts = []

                entry = {"name": city_name, "sgg": [], "town": []}
                if level == "city+sgg":
                    entry["sgg"] = opts
                elif level == "city+town":
                    entry["town"] = opts
                out[elec_code][city_code] = entry
                print(f"  {city_code} {city_name:<10} options={len(opts):>3}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ saved: {OUT}")
    return out


def load_or_fetch() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return fetch_cascade()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fetch_cascade()
