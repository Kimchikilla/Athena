"""중앙선관위 코드 매핑."""

ELECTION_ID = "0020260603"  # 제9회 전국동시지방선거 (2026-06-03)

# 17개 시·도
SIDO = {
    "1100": "서울특별시",
    "2600": "부산광역시",
    "2700": "대구광역시",
    "2800": "인천광역시",
    "2900": "광주광역시",
    "3000": "대전광역시",
    "3100": "울산광역시",
    "5100": "세종특별자치시",
    "4100": "경기도",
    "5200": "강원특별자치도",
    "4300": "충청북도",
    "4400": "충청남도",
    "5300": "전북특별자치도",
    "4600": "전라남도",
    "4700": "경상북도",
    "4800": "경상남도",
    "4900": "제주특별자치도",
}

# (electionCode, name, level, cascade_endpoint)
# level: city / city+sgg / city+town
# cascade_endpoint: cityCode 변경 시 호출되는 NEC selectbox JSON endpoint (없으면 None)
ELECTIONS: list[tuple[str, str, str, str | None]] = [
    ("3",  "시도지사",   "city",      None),
    ("11", "교육감",     "city",      None),
    ("4",  "구시군장",   "city+sgg",  "selectbox_getSggCityCodeJson.json"),
    ("5",  "시도의원",   "city+town", "selectbox_townCodeByCityIntgSgJson.json"),
    ("6",  "구시군의원", "city+town", "selectbox_townCodeBySgJson.json"),
    ("2",  "국회의원",   "city",      None),  # 페이지가 cityCode 만으로 검색
]
