"""Dataset Curator Agent - Silver 데이터 품질 검사

SilverForge로 파싱된 Silver 데이터의 품질을 검사하고,
청킹 파이프라인에 바로 사용할 수 있는 데이터인지 판단합니다.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_upstage import ChatUpstage

# 프로젝트 루트의 .env 파일을 명시적으로 로드
# src/silverforge/curator.py -> src/silverforge -> src -> project_root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")


def evaluate_text_quality(silver_md: str, original_text: Optional[str] = None) -> dict:
    """
    텍스트 품질 평가 (CER/WER)

    Args:
        silver_md: Silver markdown 텍스트
        original_text: 원본 텍스트 (비교용, 선택)

    Returns:
        {
            "char_count": int,
            "word_count": int,
            "cer": float (원본 있을 때만),
            "wer": float (원본 있을 때만),
            "pass": bool
        }
    """
    result = {
        "char_count": len(silver_md),
        "word_count": len(silver_md.split()),
        "pass": True,
    }

    if original_text:
        try:
            from jiwer import cer, wer

            result["cer"] = cer(original_text, silver_md)
            result["wer"] = wer(original_text, silver_md)
            # CER < 15% -> Pass
            result["pass"] = result["cer"] < 0.15
        except ImportError:
            pass

    return result


def evaluate_structure(silver_md: str) -> dict:
    """
    구조 품질 평가 (rule-based)

    검사 항목:
    - Heading hierarchy (H1 -> H2 -> H3 순서)
    - 테이블 구조 (| 개수 일관성)
    - 수식 검사 ($$...$$ 짝 맞음)

    Args:
        silver_md: Silver markdown 텍스트

    Returns:
        {
            "heading_count": {"h1": int, "h2": int, "h3": int, "h4": int},
            "heading_order_valid": bool,
            "table_count": int,
            "table_valid": bool,
            "equation_count": int,
            "equation_valid": bool,
            "issues": list[str],
            "pass": bool
        }
    """
    issues = []
    lines = silver_md.split("\n")

    # Heading 분석
    heading_count = {"h1": 0, "h2": 0, "h3": 0, "h4": 0}
    heading_levels = []

    for line in lines:
        if line.startswith("#"):
            match = re.match(r"^(#+)", line)
            if match:
                level = len(match.group(1))
                if level <= 4:
                    heading_count[f"h{level}"] += 1
                    heading_levels.append(level)

    # Heading 순서 검사 (급격한 점프 감지)
    heading_order_valid = True
    for i in range(1, len(heading_levels)):
        if heading_levels[i] > heading_levels[i - 1] + 1:
            heading_order_valid = False
            issues.append(f"Heading 레벨 점프: H{heading_levels[i-1]} -> H{heading_levels[i]}")
            break

    # 테이블 분석
    table_lines = [l for l in lines if l.strip().startswith("|")]
    table_count = 0
    table_valid = True

    if table_lines:
        # 테이블 그룹 카운트 (연속된 | 라인들)
        in_table = False
        for line in lines:
            if line.strip().startswith("|"):
                if not in_table:
                    table_count += 1
                    in_table = True
            else:
                in_table = False

        # 테이블 구조 검사 (| 개수 일관성)
        current_table_cols = None
        for line in table_lines:
            cols = line.count("|")
            if current_table_cols is None:
                current_table_cols = cols
            elif cols != current_table_cols and line.strip() != "|---|":
                # 일관성 없음 (단, separator 라인은 제외)
                if not re.match(r"^\|[\s\-:|]+\|$", line.strip()):
                    table_valid = False
                    issues.append(f"테이블 열 개수 불일치: {current_table_cols} vs {cols}")
                    break

    # 수식 분석
    equation_pattern = r"\$\$"
    equation_matches = re.findall(equation_pattern, silver_md)
    equation_count = len(equation_matches) // 2
    equation_valid = len(equation_matches) % 2 == 0

    if not equation_valid:
        issues.append("수식 블록 ($$$) 짝이 맞지 않음")

    return {
        "heading_count": heading_count,
        "heading_order_valid": heading_order_valid,
        "table_count": table_count,
        "table_valid": table_valid,
        "equation_count": equation_count,
        "equation_valid": equation_valid,
        "issues": issues,
        "pass": heading_order_valid and table_valid and equation_valid,
    }


def evaluate_semantic(silver_md: str, max_chars: int = 3000) -> dict:
    """
    Solar Pro2 semantic 검사 (Agent 핵심)

    Solar Pro2에게 문서 품질을 평가 요청합니다.

    Args:
        silver_md: Silver markdown 텍스트
        max_chars: LLM에 전달할 최대 문자 수

    Returns:
        {
            "structure_score": int (1-10),
            "completeness_score": int (1-10),
            "coherence_score": int (1-10),
            "overall_score": int (0-100),
            "issues": list[str],
            "recommendation": str,
            "pass": bool
        }
    """
    if not UPSTAGE_API_KEY:
        return {
            "structure_score": 0,
            "completeness_score": 0,
            "coherence_score": 0,
            "overall_score": 0,
            "issues": ["UPSTAGE_API_KEY not configured"],
            "recommendation": "API KEY 설정 필요",
            "pass": False,
        }

    llm = ChatUpstage(api_key=UPSTAGE_API_KEY, model="solar-pro", temperature=0.1)

    # 문서 일부만 전달 (토큰 제한)
    truncated_md = silver_md[:max_chars]
    if len(silver_md) > max_chars:
        truncated_md += "\n\n... (문서 일부 생략)"

    prompt = f"""당신은 학술 문서 품질 검사 전문가입니다.
다음 마크다운 문서의 품질을 평가해주세요.

[문서]
{truncated_md}

[평가 항목]
1. 구조 논리성 (1-10): 섹션 순서가 논리적인가?
2. 완전성 (1-10): 학술 논문의 필수 요소가 있는가? (Abstract, Introduction, Method, Results, Conclusion 등)
3. Coherence (1-10): 내용이 일관성 있고 읽기 쉬운가?

[응답 형식]
반드시 JSON으로만 응답하세요:
{{
    "structure_score": 8,
    "completeness_score": 9,
    "coherence_score": 7,
    "overall_score": 80,
    "issues": ["발견된 문제점 1", "발견된 문제점 2"],
    "recommendation": "청킹 가능 - minor 이슈만 있음"
}}"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()

        # JSON 파싱 시도
        # 코드 블록 제거
        if content.startswith("```"):
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines)

        result = json.loads(content)
        result["pass"] = result.get("overall_score", 0) >= 70
        return result

    except json.JSONDecodeError:
        return {
            "structure_score": 0,
            "completeness_score": 0,
            "coherence_score": 0,
            "overall_score": 0,
            "issues": ["LLM 응답 파싱 실패"],
            "recommendation": "수동 검토 필요",
            "pass": False,
            "raw_response": response.content if "response" in dir() else None,
        }
    except Exception as e:
        return {
            "structure_score": 0,
            "completeness_score": 0,
            "coherence_score": 0,
            "overall_score": 0,
            "issues": [f"평가 중 오류: {str(e)}"],
            "recommendation": "수동 검토 필요",
            "pass": False,
        }


def curate(silver_md: str, original_text: Optional[str] = None) -> dict:
    """
    전체 품질 평가 (메인 함수)

    텍스트, 구조, 의미론적 품질을 종합 평가합니다.

    Args:
        silver_md: Silver markdown 텍스트
        original_text: 원본 텍스트 (CER/WER 계산용, 선택)

    Returns:
        {
            "pass": bool,
            "text_quality": {...},
            "structure_quality": {...},
            "semantic_quality": {...},
            "overall_score": int,
            "recommendation": str
        }
    """
    text_quality = evaluate_text_quality(silver_md, original_text)
    structure_quality = evaluate_structure(silver_md)
    semantic_quality = evaluate_semantic(silver_md)

    # 종합 점수 계산
    all_pass = text_quality["pass"] and structure_quality["pass"] and semantic_quality["pass"]

    # 가중 평균 점수
    semantic_score = semantic_quality.get("overall_score", 0)
    structure_bonus = 10 if structure_quality["pass"] else 0
    text_bonus = 10 if text_quality["pass"] else 0
    overall_score = min(100, semantic_score + structure_bonus + text_bonus)

    # 권장사항 결정
    if all_pass:
        recommendation = "청킹 가능 - 모든 검사 통과"
    elif structure_quality["pass"] and text_quality["pass"]:
        recommendation = "청킹 가능 - 의미론적 검토 권장"
    else:
        recommendation = "수정 필요 - 구조/텍스트 문제 발견"

    return {
        "pass": all_pass,
        "text_quality": text_quality,
        "structure_quality": structure_quality,
        "semantic_quality": semantic_quality,
        "overall_score": overall_score,
        "recommendation": recommendation,
    }
