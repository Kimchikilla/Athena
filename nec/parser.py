"""검색 결과 HTML 에서 후보자 행을 lxml 로 추출."""
import re
from typing import Iterable

from lxml import html as lxml_html

HUBO_RE = re.compile(r"popupPreHBJ\(\s*'[^']+'\s*,\s*'(\d+)'\s*\)")
SPACES_RE = re.compile(r"[ \t\xa0]+")
NL_RE = re.compile(r"\n{2,}")


def _text(elem) -> str:
    """엘리먼트 안의 모든 텍스트를 줄바꿈 보존하며 추출."""
    if elem is None:
        return ""
    # <br> 를 줄바꿈으로 보존하기 위해 직렬화 후 다시 파싱하기보단,
    # itertext() 로 모으면서 br 위치를 \n 으로 변환
    parts: list[str] = []
    for el in elem.iter():
        if el.tag == "br":
            parts.append("\n")
        if el.text:
            parts.append(el.text)
        if el is not elem and el.tail:
            parts.append(el.tail)
    txt = "".join(parts)
    txt = SPACES_RE.sub(" ", txt)
    txt = NL_RE.sub("\n", txt)
    return txt.strip()


def parse_candidates(html: str) -> list[dict]:
    if "조회 자료가 없습니다" in html or "조회된 자료가 없습니다" in html:
        return []

    root = lxml_html.fromstring(html)

    # 후보자 결과 테이블: thead 의 첫 th 텍스트가 '선거구명'
    target = None
    for tbl in root.iter("table"):
        head_ths = tbl.xpath(".//thead//th")
        if not head_ths:
            continue
        head_texts = [_text(th) for th in head_ths]
        if any("선거구" in h for h in head_texts) or any("성명" in h for h in head_texts):
            target = tbl
            target_headers = head_texts
            break
    if target is None:
        return []

    # 헤더 정규화 (예: '소속\n정당명' → '소속정당명')
    headers = [h.replace("\n", "") for h in target_headers]
    rows: list[dict] = []
    for tr in target.xpath(".//tbody/tr"):
        tds = tr.findall("td")
        if not tds:
            continue
        values = [_text(td) for td in tds]
        if len(values) < 3:
            continue

        # 컬럼 수가 헤더보다 적으면 앞에서부터 매핑, 남는 헤더는 빈값
        rec: dict = {}
        for h, v in zip(headers, values):
            rec[h] = v
        # popupPreHBJ huboId
        raw = lxml_html.tostring(tr, encoding="unicode")
        m = HUBO_RE.search(raw)
        rec["huboId"] = m.group(1) if m else ""

        # 성명을 popupPreHBJ a 태그 텍스트에서 직접 추출 (보강)
        a = tr.xpath(".//a[contains(@href,'popupPreHBJ')]")
        if a:
            name = _text(a[0]).split("\n")[0].strip()
            # 성명 키 후보: '성명(한자)' 또는 '성명'
            for k in list(rec.keys()):
                if k.startswith("성명"):
                    if not rec[k] or len(rec[k]) <= 1:
                        rec[k] = name
                    break

        rows.append(rec)
    return rows
