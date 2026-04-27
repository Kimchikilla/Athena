"""LLM 투표 시뮬레이션 프롬프트 템플릿."""
from textwrap import dedent


SYSTEM = dedent("""\
    당신은 한국 유권자 페르소나를 정확히 연기하는 시뮬레이터입니다.
    주어진 페르소나 정보를 바탕으로 그 사람의 입장에서 사고하고 투표 결정을 내리세요.
    개인의 성향, 직업, 학력, 거주지, 가치관을 종합 고려해야 합니다.
    답변은 반드시 지정된 JSON 형식만 출력하고 다른 설명을 덧붙이지 마세요.
""").strip()


def candidate_block(candidates: list[dict]) -> str:
    """후보자 정보 블록. candidates 는 nec/crawler 결과 dict 리스트."""
    lines: list[str] = []
    for i, c in enumerate(candidates, 1):
        # 성명(한자) 에서 한자 제거
        name = (c.get("성명(한자)") or "").splitlines()[0].strip()
        name = name.replace(" ", "")
        party = c.get("소속정당명", "")
        career = (c.get("경력") or "").replace("\n", " · ")
        edu = c.get("학력", "")
        age_line = c.get("생년월일(연령)", "").replace("\n", " ")
        job = c.get("직업", "")
        lines.append(
            f"[후보 {i}] {name} ({party})\n"
            f"  - 직업: {job}\n"
            f"  - 학력: {edu}\n"
            f"  - 생년월일: {age_line}\n"
            f"  - 주요 경력: {career[:200]}"
        )
    return "\n".join(lines)


def persona_block(p: dict) -> str:
    """Nemotron 페르소나 dict → 핵심 정보 텍스트."""
    sex = p.get("sex", "")
    age = p.get("age", "")
    edu = p.get("education_level", "")
    job = p.get("occupation", "")
    district = p.get("district", "")
    house = p.get("housing_type", "")
    family = p.get("family_type", "")
    persona = p.get("persona", "")
    professional = p.get("professional_persona", "")
    cultural = p.get("cultural_background", "")
    return dedent(f"""\
        ◆ 인구통계
          - 성별/나이: {sex} / {age}세
          - 거주지: {district}
          - 학력: {edu}  / 직업: {job}
          - 가구: {family}  / 주택: {house}

        ◆ 페르소나 요약
        {persona}

        ◆ 직업 및 가치관
        {professional}

        ◆ 문화적 배경
        {cultural}
    """).strip()


def build_prompt(persona: dict, sido_name: str, candidates: list[dict]) -> str:
    """전체 사용자 프롬프트 생성. JSON 응답을 강제."""
    cand_lines = candidate_block(candidates)
    p_lines = persona_block(persona)
    indices = ", ".join(str(i + 1) for i in range(len(candidates)))
    return dedent(f"""\
        다음은 2026년 6월 3일 제9회 전국동시지방선거 {sido_name} 시·도지사 선거의 예비후보자입니다.

        {cand_lines}

        다음은 당신이 연기할 유권자입니다.

        {p_lines}

        지시사항:
        1) 위 후보들의 정당·경력·이력만 참고해 이 유권자가 가장 투표할 가능성이 높은 한 명을 선택.
        2) 선택할 후보 번호({indices}) 한 개와, 그 사람의 입장에서 결정을 내린 한 줄 이유를 출력.
        3) 정말 어느 후보도 지지하기 어려우면 number 를 0 (기권/무효) 으로 표시.

        반드시 아래 JSON 형식만 출력하세요. 추가 설명/마크다운 금지.
        {{"choice": <number>, "reason": "<한 문장 한국어>"}}
    """).strip()
