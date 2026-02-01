# SilverForge Agent 리팩토링 계획

## 목표
현재 고정 파이프라인을 **OmniDocBench(CVPR 2025) 메트릭 기반으로 품질을 판단하고, 도구를 선택하여 반복 개선하는 AI Agent**로 전환

## 현재 vs 목표

```
현재: PDF → parse → refine → curate(Solar Pro 점수만) → 끝
      고정 순서, 자의적 기준, 피드백 루프 없음

목표: PDF → parse → Agent Loop:
                      ├─ evaluate (OmniDocBench 메트릭 or rule-based 진단)
                      ├─ decide (Solar Pro가 메트릭 기반으로 다음 행동 결정)
                      ├─ act (도구 실행)
                      ├─ re-evaluate (메트릭 변화 확인)
                      └─ rollback (악화 시 이전 버전 복원)
                    → Silver Markdown + 액션 히스토리 + 메트릭 변화 리포트
```

## Phase 0: 기존 자산 복사 (test-vlm-document-parsing → SilverForge)

이미 복사된 것:
- `benchmark/eval_parsers.py` — CER/WER/Structure F1/TEDS
- `benchmark/dataset/` — arXiv 데이터셋 빌더
- `results/test_arxiv_001~039/` — 39편 베이스라인 결과

추가로 복사할 것:
```
src/adapters/omnidocbench.py → silverforge/benchmark/adapters/omnidocbench.py
src/adapters/__init__.py     → silverforge/benchmark/adapters/__init__.py
data/omnidocbench/           → data/omnidocbench/ (OmniDocBench.json + images)
tests/test_parsing_cli.py    → tests/test_benchmark.py (TEDS/F1 유닛테스트)
```

**import 경로 점검**: eval_parsers.py 내부의 import 경로를 `silverforge.benchmark.*`로 수정

## Phase 1: 2-Track 평가 엔진 — `evaluator.py` (신규)

### Track A: 벤치마크 모드 (GT 있을 때)
OmniDocBench 논문의 공식 메트릭:

```python
@dataclass
class QualityReport:
    # 텍스트 품질 — NED (Normalized Edit Distance)
    text_ned: float       # 1 - ED(pred, gt) / max(|pred|, |gt|)  [0~1]
    text_bleu: float      # BLEU score

    # 테이블 품질 — TEDS
    table_teds: float     # HTML 트리 구조 유사도 [0~1]
    table_count: int
    per_table_scores: list[float]

    # 수식 품질 — NED on LaTeX (CDM 대체)
    formula_ned: float    # LaTeX 문자열 NED [0~1]
    # NOTE: CDM(이미지 기반)은 구현 복잡도 극히 높아 future work로 분류
    # OmniDocBench도 보조 메트릭으로 NED 사용

    # 구조 품질 — Structure F1
    structure_f1: float
    structure_detail: dict

    # 종합 (OmniDocBench 공식 변형)
    overall: float        # (text_ned + table_teds + formula_ned) / 3 * 100

    # Agent용
    issues: list[str]
    actionable: list[str]
    mode: str             # "benchmark" | "production"
```

### Track B: 프로덕션 모드 (GT 없을 때)
사용자가 PDF만 업로드하는 실제 사용 시나리오:

```python
# GT 없이 측정 가능한 메트릭:
# 1. 구조 검증 (rule-based): heading 계층, 테이블 구문, 수식 쌍
# 2. Solar Pro semantic: 논리성/완전성/일관성 (기존 curator.py)
# 3. 자기 일관성: parse 결과 내부의 구조적 정합성

# Agent는 Track B 기반으로도 판단 가능
# → evaluate_structure() + evaluate_semantic() 결과를 issues로 변환
```

## Phase 2: 도구(Tools) 정의 — `tools.py` (신규)

```python
TOOLS = {
    "fix_heading_hierarchy": {
        "target_metric": "structure_f1",
        "description": "Heading 레벨 복원 (1→1.1→1.1.1 패턴 감지)",
        "implementation": "기존 refine_headings() 확장",
    },
    "fix_table_structure": {
        "target_metric": "table_teds",
        "description": "파이프 카운트 불일치/구분선 누락 수정",
        "implementation": "신규 구현",
    },
    "fix_equation_blocks": {
        "target_metric": "formula_ned",
        "description": "$$...$$ 미닫힘, 인라인 수식 정리",
        "implementation": "신규 구현",
    },
    "remove_artifacts": {
        "target_metric": "text_ned",
        "description": "페이지 번호, 러닝 헤더, 빈 줄 정리",
        "implementation": "신규 구현",
    },
}
# NOTE: reparse_section 제거 — Upstage API는 전체 PDF 입력만 지원, 섹션 단위 불가
```

## Phase 3: Agent 루프 — `agent.py` (신규)

LangGraph StateGraph 기반, **3-node 구조**:

```python
class AgentState(TypedDict):
    markdown: str
    previous_markdown: str      # rollback용
    quality_report: QualityReport
    action_history: list[dict]
    iteration: int
    blacklisted_tools: list[str]  # 악화시킨 도구 재사용 방지

# 3 Nodes (evaluate + re_evaluate 통합)
# 1. evaluate_node: 메트릭 측정 + 종료/계속 판단
# 2. decide_node: Solar Pro가 다음 행동 결정
# 3. execute_node: 도구 실행 + rollback 체크

# Edges
# evaluate → overall 충분 OR iteration >= MAX → END
# evaluate → 개선 필요 → decide → execute → evaluate (루프)
```

### Rollback 메커니즘
```python
# execute_node 내부:
previous_markdown = state["markdown"]
new_markdown = tool.execute(state["markdown"])
new_report = evaluate(new_markdown, gt)

if new_report.overall < state["quality_report"].overall:
    # 악화 → rollback
    state["markdown"] = previous_markdown
    state["blacklisted_tools"].append(tool_name)
    state["action_history"].append({
        "tool": tool_name, "result": "ROLLBACK", "reason": "메트릭 악화"
    })
else:
    state["markdown"] = new_markdown
    state["quality_report"] = new_report
```

### Fallback 전략
```python
# Agent 실행 중 오류 발생 시:
try:
    result = agent.run(silver_md, original_text)
except (APIError, JSONDecodeError, Exception):
    # 기존 curate() fallback
    result = curate(silver_md, original_text)
    result["agent_fallback"] = True
```

### Solar Pro 프롬프트 (메트릭 기반 의사결정):
```
당신은 학술 문서 품질 개선 Agent입니다.

[품질 리포트 — OmniDocBench 메트릭 기준]
- Text NED: {text_ned:.3f} (목표: > 0.85)
- Table TEDS: {table_teds:.3f} (목표: > 0.80)
- Formula NED: {formula_ned:.3f} (목표: > 0.85)
- Structure F1: {structure_f1:.3f} (목표: > 0.70)
- Overall: {overall:.1f} (목표: > 70)

[감지된 문제]
{issues}

[사용 불가 도구 (이전에 악화 유발)]
{blacklisted_tools}

[사용 가능한 도구]
1. fix_heading_hierarchy → Structure F1 개선
2. fix_table_structure → Table TEDS 개선
3. fix_equation_blocks → Formula NED 개선
4. remove_artifacts → Text NED 개선
5. DONE → 충분히 개선됨 또는 더 이상 개선 불가

가장 큰 메트릭 개선이 예상되는 액션 1개를 선택하세요.
JSON: {"action": "도구명", "reason": "이유", "target_metric": "개선 대상"}
```

## Phase 4: 기존 코드 통합

### 수정 대상 파일

| 파일 | 변경 |
|------|------|
| `src/silverforge/evaluator.py` | **신규** — 2-Track 평가 엔진 |
| `src/silverforge/tools.py` | **신규** — Agent 도구 함수 4개 |
| `src/silverforge/agent.py` | **신규** — LangGraph 3-node Agent + rollback |
| `src/silverforge/benchmark/adapters/omnidocbench.py` | **복사** — OmniDocBench 어댑터 |
| `src/silverforge/curator.py` | 기존 유지 + `curate_with_agent()` 추가 |
| `src/silverforge/__init__.py` | 새 함수 export |
| `src/silverforge/app.py` | Agent 결과 UI + 메트릭 변화 차트 + 액션 히스토리 |
| `pyproject.toml` | `langgraph>=0.2.0,<1.0`, `apted>=1.0.3`, `mistletoe>=1.4.0` 추가 |
| `tests/test_benchmark.py` | **복사+수정** — 기존 TEDS/F1 테스트 이식 |

### curator.py 변경
```python
def curate_with_agent(silver_md, original_text=None, max_iterations=3):
    """OmniDocBench 메트릭 기반 Agent 품질 평가 + 자동 수정

    original_text 있으면 Track A (벤치마크), 없으면 Track B (프로덕션)
    Agent 실패 시 기존 curate()로 fallback
    """
    # Returns: {
    #   "markdown": improved_md,
    #   "metrics_before": {"text_ned": 0.62, "table_teds": 0.45, ...},
    #   "metrics_after":  {"text_ned": 0.88, "table_teds": 0.82, ...},
    #   "actions": [
    #     {"tool": "fix_headings", "result": "OK", "metric_delta": {"structure_f1": +0.55}},
    #     {"tool": "fix_tables",   "result": "ROLLBACK", "reason": "메트릭 악화"},
    #   ],
    #   "iterations": 2,
    #   "mode": "benchmark" | "production",
    #   "pass": True
    # }
```

### app.py 변경
- Agent 결과 UI: 메트릭 before/after 차트 + 액션 히스토리 타임라인
- `quality_details` JSONB에 `agent_actions` 키로 히스토리 저장

## Phase 5: 검증

1. **유닛 테스트**: 각 도구가 메트릭을 실제로 개선하는지
2. **Rollback 테스트**: 의도적으로 악화시키는 도구 → rollback 동작 확인
3. **Track B 테스트**: GT 없이 Agent가 구조 개선하는지
4. **OmniDocBench 5페이지**: Track A 종단 검증
5. **arXiv 39편**: Agent 적용 전/후 메트릭 비교
6. **Fallback 테스트**: Solar Pro API 모킹 실패 → curate() fallback 확인

```bash
pytest tests/ -v
python scripts/example.py paper.pdf --agent
python scripts/run_benchmark.py --data-dir data/ --agent
```

## 의존성 추가 (pyproject.toml)
```toml
langgraph>=0.2.0,<1.0
apted>=1.0.3
mistletoe>=1.4.0
```

## 핵심 원칙
- **메트릭 = 논문 근거**: OmniDocBench(CVPR 2025)의 NED/TEDS/F1
- **CDM → NED 대체**: 이미지 기반 CDM은 future work, LaTeX NED로 대체
- **2-Track**: GT 있으면 정량 벤치마크, 없으면 rule-based + semantic
- **Rollback**: 도구 실행 후 악화 시 복원 + 해당 도구 blacklist
- **Fallback**: Agent 실패 시 기존 curate()로 안전하게 복귀
- **3-node 루프**: evaluate → decide → execute (단순화)
- **MAX 3회 반복**: API 비용 제한
- **하위 호환**: 기존 `curate()` 유지
