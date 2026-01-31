# SilverForge

[![English](https://img.shields.io/badge/lang-English-red.svg)](README.md)

**PDF를 구조화된 Markdown으로 변환** - VLM/SLM 학습용 Ground Truth 데이터 생성 도구

> Upstage Ambassador 2기 프로젝트

## 문제 정의

VLM(Vision Language Model)과 SLM(Small Language Model) 학습에는 **고품질 GT(Ground Truth) 데이터**가 필수입니다.
기존 LaTeX → Pandoc 변환 방식은 다음과 같은 한계가 있습니다:

| 방식 | 커버리지 | 테이블 인식 | 한계 |
|------|----------|-------------|------|
| LaTeX → Pandoc | 40-50% | 불완전 | LaTeX 소스 필요 |
| PyMuPDF | 60-70% | 불가 | 구조 손실 |
| **Upstage Document Parse** | **100%** | **완벽** | - |

## 솔루션

**SilverForge**는 [Upstage Document Parse](https://console.upstage.ai/) API를 활용하여:

1. **PDF 직접 파싱** - LaTeX 소스 없이도 100% 커버리지
2. **테이블 완벽 인식** - 기존 방식: 0개 → SilverForge: 10개
3. **Heading Hierarchy 복원** - Rule-based 방식으로 95%+ 정확도

```
PDF → parse_pdf() → Raw Markdown → refine_headings() → Silver Markdown
         ↑                              ↑
    Upstage API                   Rule-based (regex)
```

## 벤치마크 결과

**테스트 문서**: "Attention Is All You Need" (Vaswani et al., 2017)

| 메트릭 | LaTeX+Pandoc | SilverForge |
|--------|--------------|-------------|
| 테이블 인식 | 0개 | **10개** |
| Heading 복원 | 수동 필요 | **95%+ 자동** |
| 수식 보존 | 부분적 | **완전** |
| 소스 필요 | LaTeX 필수 | **PDF만** |

## 빠른 시작

### 설치

```bash
# uv 사용 (권장)
uv pip install -e .

# pip 사용
pip install -e .
```

### 환경 설정

```bash
cp .env.example .env
# .env 파일에 UPSTAGE_API_KEY 입력
```

### 사용법

```python
from silverforge import process

# PDF → Silver Markdown (한 번에)
silver_md = process("paper.pdf")

# 또는 단계별로
from silverforge import parse_pdf, refine_headings

raw_md = parse_pdf("paper.pdf")      # Upstage API 호출
silver_md = refine_headings(raw_md)  # Heading 복원
```

### CLI 예제

```bash
python example.py paper.pdf
# -> paper_silver.md 생성
```

### 웹 UI 콘솔

```bash
# Streamlit UI 실행 (권장)
python run_ui.py
# -> http://localhost:8502

# FastAPI 서버 실행 (API 용도)
python run_ui.py --api
# -> http://localhost:8000
# -> API docs: http://localhost:8000/docs
```

**UI 기능:**
- 여러 PDF 동시 업로드 (Drag & Drop)
- 순차 처리 및 실시간 진행률
- 품질 점수 표시 (Curator Agent)
- 결과 미리보기 (팝업)
- 개별/전체 다운로드 (ZIP)

## Dataset Curator Agent

Silver 데이터의 품질을 자동으로 검사하는 Agent입니다.

```python
from silverforge import curate

result = curate(silver_md)
print(result)
# {
#   "pass": True,
#   "overall_score": 85,
#   "recommendation": "청킹 가능 - 모든 검사 통과"
# }
```

### 품질 검사 항목

1. **텍스트 품질**: CER/WER 계산 (원본 대비)
2. **구조 품질**: Heading hierarchy, 테이블 구조, 수식 블록
3. **의미론적 품질**: Solar Pro2 기반 논리성/완전성/일관성 평가

```bash
python example_curate.py results/attention_paper.md
```

## 프로젝트 구조

```
silverforge/
├── silverforge/
│   ├── __init__.py      # exports
│   ├── core.py          # 파싱 (parse_pdf, refine_headings)
│   ├── curator.py       # 품질 검사 (curate)
│   ├── api.py           # FastAPI 백엔드
│   └── app.py           # Streamlit UI
├── run_ui.py            # UI 실행 스크립트
├── example.py           # 파싱 예제
├── example_curate.py    # 품질 검사 예제
└── results/
    └── attention_paper.md  # PoC 결과물
```

## API 레퍼런스

### Core 함수

#### `parse_pdf(pdf_path: str) -> str`
PDF 파일을 Upstage Document Parse API로 파싱하여 raw markdown 반환

#### `refine_headings(markdown: str) -> str`
Rule-based 방식으로 heading hierarchy 복원

#### `process(pdf_path: str) -> str`
`parse_pdf` + `refine_headings` 편의 함수

### Curator 함수

#### `curate(silver_md: str, original_text: str = None) -> dict`
전체 품질 평가 (텍스트 + 구조 + 의미론)

#### `evaluate_structure(silver_md: str) -> dict`
구조 품질 평가 (heading, 테이블, 수식)

#### `evaluate_semantic(silver_md: str) -> dict`
Solar Pro2 기반 의미론적 품질 평가

## 감사의 말

- [Upstage](https://upstage.ai/) - Document Parse API, Solar Pro2
- Upstage Ambassador 2기 프로그램

## 라이선스

MIT
