# SilverForge

## PDF를 구조화된 Markdown으로 변환하는 VLM/SLM 학습용 Ground Truth 데이터 생성 도구

---

## 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 프로젝트명 | SilverForge |
| 한 줄 소개 | PDF → 구조화된 Markdown 변환 도구 |
| 라이브 데모 | [https://silverforge.streamlit.app](https://silverforge.streamlit.app) |
| GitHub | [https://github.com/Hyeongseob91/upstage-silverforge-agent](https://github.com/Hyeongseob91/upstage-silverforge-agent) |
| 개발 기간 | 2026년 1월 |
| 소속 | Upstage Ambassador Season 2 |

---

## 문제 정의

### VLM/SLM 학습에 고품질 Ground Truth 데이터가 필수

기존 방식의 한계:

| 방식 | 커버리지 | 테이블 인식 | 한계 |
| --- | --- | --- | --- |
| LaTeX → Pandoc | 40-50% | 불완전 | LaTeX 소스 필요 |
| PyMuPDF | 60-70% | 미지원 | 구조 손실 |
| **Upstage Document Parse** | **100%** | **완벽** | - |

---

## 솔루션

### SilverForge 파이프라인

```
PDF → parse_pdf() → Raw Markdown → refine_headings() → Silver Markdown
         ↑                              ↑
    Upstage API                   Rule-based (regex)
```

### 핵심 기능

1. **PDF 직접 파싱** - LaTeX 소스 없이 100% 커버리지
2. **완벽한 테이블 인식** - 기존: 0개 → SilverForge: 10개
3. **Heading 계층 복원** - Rule-based 방식으로 95%+ 정확도

---

## 벤치마크 결과

**테스트 문서**: "Attention Is All You Need" (Vaswani et al., 2017)

| 지표 | LaTeX+Pandoc | SilverForge |
| --- | --- | --- |
| 테이블 인식 | 0 | **10** |
| Heading 복원 | 수동 필요 | **95%+ 자동** |
| 수식 보존 | 부분적 | **완벽** |
| 필요 소스 | LaTeX 필요 | **PDF만** |

---

## 주요 기능

### 1. PDF → Markdown 변환

- Upstage Document Parse API 활용
- 이미지, 테이블, 수식 완벽 지원
- Heading 계층 자동 복원

### 2. 품질 분석 (Curator Agent)

- **텍스트 품질**: 문자/단어 수, CER/WER
- **구조 품질**: Heading 계층, 테이블 구조, 수식 블록
- **의미론적 품질**: Solar Pro 기반 논리성/완전성/일관성 평가

### 3. Notion 스타일 UI

- 깔끔하고 미니멀한 디자인
- 이메일/비밀번호 인증
- 다중 PDF 업로드 (드래그 앤 드롭)
- 실시간 처리 진행률 표시
- 개별/일괄 다운로드 (ZIP)

### 4. 클라우드 저장

- Supabase 연동
- 사용자별 문서 저장
- 게스트 모드 지원

---

## 기술 스택

| 영역 | 기술 |
| --- | --- |
| Frontend | Streamlit (Notion-style UI) |
| Backend | Python |
| PDF 파싱 | Upstage Document Parse API |
| 품질 평가 | Upstage Solar Pro |
| 인증 | Supabase Auth |
| 데이터베이스 | Supabase PostgreSQL |
| 배포 | Streamlit Cloud |

---

## 사용 방법

### Python 코드

```python
from silverforge import process, curate

# PDF → Silver Markdown
silver_md = process("paper.pdf")

# 품질 평가
result = curate(silver_md)
print(result["overall_score"])  # 85
```

### 웹 UI

1. [https://silverforge.streamlit.app](https://silverforge.streamlit.app) 접속
2. 이메일로 회원가입 또는 게스트로 시작
3. 사이드바에서 PDF 업로드
4. "변환 시작" 클릭
5. 결과 확인 및 다운로드

---

## 스크린샷

### 로그인 페이지

- Notion 스타일의 깔끔한 로그인/회원가입
- 이메일 + 비밀번호 인증
- 게스트 모드 지원

### 메인 페이지

- 좌측: 대기 목록 (업로드된 PDF)
- 우측: 변환 결과 (품질 점수 포함)
- 사이드바: PDF 업로드, 변환 시작 버튼

### 품질 분석

- Radar Chart: 구조 논리성, 완전성, 일관성
- Bar Chart: 문서 구조 (Heading, Table, Equation)
- Gauge Chart: 전체 점수
- 이슈 및 권장사항 표시

---

## 프로젝트 구조

```
silverforge/
├── src/silverforge/
│   ├── core.py          # PDF 파싱 (parse_pdf, refine_headings)
│   ├── curator.py       # 품질 평가 (curate)
│   ├── database.py      # Supabase 연동
│   └── app.py           # Streamlit UI
├── supabase/
│   └── schema.sql       # DB 스키마
└── requirements.txt     # 의존성
```

---

## 향후 계획

- [ ]  배치 처리 성능 최적화
- [ ]  더 많은 문서 형식 지원 (DOCX, PPTX)
- [ ]  품질 분석 리포트 PDF 출력
- [ ]  API 엔드포인트 제공

---

## 감사의 말

- **Upstage** - Document Parse API, Solar Pro 제공
- **Supabase** - 인증 및 데이터베이스
- **Upstage Ambassador Season 2** 프로그램

---

## 링크

- **라이브 데모**: [https://silverforge.streamlit.app](https://silverforge.streamlit.app)
- **GitHub**: [https://github.com/Hyeongseob91/upstage-silverforge-agent](https://github.com/Hyeongseob91/upstage-silverforge-agent)
- **Upstage Console**: [https://console.upstage.ai](https://console.upstage.ai)
