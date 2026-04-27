# Athena

> 2026 한국 제9회 전국동시지방선거 NEC 예비후보 크롤러 + Nemotron-Personas-Korea × Gemma 4 LLM 투표 시뮬레이션

이 레포는 두 가지 일을 합니다.

1. **NEC 예비후보자 명부 크롤링** — `info.nec.go.kr`에서 6종 선거(시도지사·교육감·구시군장·시도의원·구시군의원·국회의원) × 17 시도 예비후보자 약 8,300명 수집.
2. **LLM 페르소나 투표 시뮬레이션** — NVIDIA Nemotron-Personas-Korea의 합성 한국 페르소나 4,800명에게 Gemma 4 e4b로 시도지사 투표를 시켜 결과 집계.

> ⚠️ **중요**: 이 시뮬레이션 결과는 **당선 예측이 아닙니다**. LLM이 인구통계를 어떻게 정치적으로 해석하는지 보는 실험이며, 현직 프리미엄 과대평가, 후보 인지도 편향 등 명확한 한계가 있습니다. 자세한 내용은 [한계](#한계--편향) 섹션 참조.

---

## 시뮬레이션 결과 (2026-04-27 기준 예비후보 명부)

16개 시도 시도지사 4,800표 시뮬레이션 1위 후보:

| 시도 | 1위 (득표율) | 특이사항 |
|---|---|---|
| 강원 | 김진태 (국힘) 100.0% | 현직 도지사 |
| 경기 | 양기대 (민주) 64.3% | |
| 경남 | 김경수 (민주) 59.8% | |
| 경북 | 이철우 (국힘) 99.3% | 현직 |
| 광주 | 이종욱 (진보) 61.3% | |
| **대구** | **김한구 (무소속) 90.5%** | **김부겸 1.4% — LLM 편향 사례** |
| 대전 | 허태정 (민주) 63.9% | |
| 부산 | 이재성 (민주) 68.3% | 기권 51% |
| 서울 | 정원오 (민주) 35.2% | 8명 경합 |
| 세종 | 최민호 (국힘) 67.2% | |
| 울산 | 박맹우 (무소속) 92.8% | |
| 인천 | 이기붕 (개혁) 단독 출마 | 기권 93% |
| 전북 | 김성수 (무소속) 88.6% | |
| 제주 | 문성유 (국힘) 77.0% | |
| 충남 | 양승조 (민주) 53.5% | |
| 충북 | 한범덕 (민주) 35.8% | 기권 73% |

> 전라남도는 시도지사 예비후보 0명이라 제외 (그래서 17×300=5,100이 아닌 16×300=4,800).

전체 결과: [`data/vote_summary.csv`](data/vote_summary.csv) · [`data/vote_report.txt`](data/vote_report.txt) · [`data/vote_results.jsonl`](data/vote_results.jsonl)

---

## 한계 / 편향

LLM 페르소나 시뮬레이션은 **여론조사 대체재가 아닙니다**. 이번 실행에서 관찰된 명확한 편향:

1. **현직 프리미엄 과대평가**: 강원 김진태 100%, 경북 이철우 99.3% — LLM이 "현직" 키워드에 거의 결정론적으로 끌림
2. **노동자 페르소나 단순 매칭**: 대구 김부겸(전 국무총리·4선 의원)이 1.4%로 나오고, 무소속 노동자 후보 김한구가 90.5% — 페르소나의 직업 라벨이 LLM의 추론을 과도하게 지배
3. **후보 정보 부실 시 기권 폭증**: 충북 73%, 인천 93%가 "기권" 선택 — 후보 경력 정보가 짧으면 LLM이 결정 회피
4. **정당지지 라벨 부재**: 데이터셋에 정치성향 필드가 없어 LLM이 페르소나 텍스트에서 추론. 추론 과정에 학습 편향(언론 노출, 후보 인지도)이 그대로 반영됨

요컨대 이 결과는 **"LLM이 인구통계 → 정치 선택을 어떻게 매핑하는가"** 의 시뮬레이션이지 실제 유권자 행동의 예측이 아닙니다.

---

## 구조

```
nec/                       # NEC 예비후보 크롤러
├── codes.py               # 시도(17)·선거유형(6) 코드 매핑
├── cascade.py             # selectbox JSON endpoint 직접 호출 → 시도→시군구 옵션 캐싱
├── crawler.py             # form-POST + 결과 파싱 → CSV 저장
└── parser.py              # lxml 기반 후보 테이블 파싱 (br/nbsp 정규화)

sim/                       # 시뮬레이션 파이프라인
├── sample_personas.py     # HF streaming reservoir sampling (시도별 300명)
├── prompt.py              # 페르소나 + 후보 정보 → JSON 응답 강제 프롬프트
├── runner.py              # Ollama Chat API 병렬 호출 + 재개 로직
└── aggregate.py           # JSONL → 시도별 후보 득표율 표 + CSV

data/                      # 결과물
├── cascade.json           # 시도→시군구 옵션 캐시
├── 시도지사.csv 등        # NEC 크롤링 결과 (6종 선거)
├── vote_results.jsonl     # 시뮬 raw 결과 (4,800행)
├── vote_summary.csv       # 시도별 후보 득표율 표
└── vote_report.txt        # 텍스트 리포트
```

---

## 재현 방법

### 0. 의존성

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m playwright install chromium  # cascade 정찰용 (선택)
```

Ollama 설치 (Windows):

```powershell
winget install --id=Ollama.Ollama --silent
ollama pull gemma4:e4b   # 9.6GB
```

### 1. 후보 데이터 크롤링

```bash
# cascade endpoint 매핑 캐시 (한 번만)
.venv/Scripts/python.exe -m nec.cascade

# 6종 선거 × 17 시도 풀 크롤링 (~5분, 약 800 요청)
.venv/Scripts/python.exe -m nec.crawler
```

→ `data/{시도지사,교육감,구시군장,시도의원,구시군의원,국회의원}.csv`

### 2. 페르소나 샘플링

```bash
# Hugging Face 에서 1M 페르소나 streaming + 시도별 reservoir 300명 = 5,100명
.venv/Scripts/python.exe -m sim.sample_personas
```

→ `data/personas_sample.json` (~23MB, gitignore)

### 3. 시뮬레이션 실행

```bash
# RTX 5060 8GB 기준 약 3시간 (4.4초/호출 × 4,800 / num_parallel=2)
.venv/Scripts/python.exe -m sim.runner
```

→ `data/vote_results.jsonl` (재개 가능 — 중단 후 재실행 시 완료된 uuid skip)

### 4. 집계

```bash
.venv/Scripts/python.exe -m sim.aggregate
```

→ `data/vote_summary.csv` + 콘솔 리포트

---

## 시스템 요구사항

- **OS**: Windows 11 (검증 환경) — Linux/macOS도 동작할 가능성 높음 (path 처리만 확인)
- **Python**: 3.11+
- **GPU**: 8GB VRAM 이상 권장 (Gemma 4 e4b 양자화 모델). e2b 사용 시 6GB도 가능하나 한국어 추론 약함
- **디스크**: 약 15GB (모델 9.6GB + 페르소나 샘플 23MB + 의존성 + 결과)
- **네트워크**: NEC 사이트 + Hugging Face + Ollama 모델 다운로드

---

## 데이터 출처 / 라이선스

- **후보 데이터**: 중앙선거관리위원회 [info.nec.go.kr](https://info.nec.go.kr) 예비후보자 명부 (공공정보)
- **페르소나 데이터**: NVIDIA [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) — CC BY 4.0
- **LLM**: Google [Gemma 4](https://ollama.com/library/gemma4) e4b — Gemma Terms of Use
- **이 레포의 코드**: MIT (자유롭게 사용/수정/배포)

NVIDIA Nemotron-Personas-Korea는 인공 합성 데이터이며 실명 인물과의 유사성은 우연입니다.

---

## 향후 작업

- [ ] 정식 후보 등록 마감(2026-05-15) 후 동일 파이프라인 재실행 → 예비후보 vs 정식후보 비교
- [ ] 베이스라인 비교: 갤럽/리얼미터 인구통계별 정당지지율로 LLM 편향 정량화
- [ ] 다른 LLM 비교: Qwen3, Solar 등으로 동일 페르소나 시뮬 → 모델별 편향 차이 분석
- [ ] 교육감·구시군장까지 확장 (기초단체장 1,044명 시뮬은 약 30시간)
