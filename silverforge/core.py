"""SilverForge - PDF를 구조화된 Markdown으로 변환

Upstage Document Parse API를 사용하여 PDF를 파싱하고,
Rule-based 방식으로 heading hierarchy를 복원합니다.
"""

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
UPSTAGE_API_URL = "https://api.upstage.ai/v1/document-ai/document-parse"


def parse_pdf(pdf_path: str) -> str:
    """
    PDF -> Raw Markdown (Upstage Document Parse)

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        Raw markdown 텍스트

    Raises:
        ValueError: API KEY가 없거나 파일이 없는 경우
        RuntimeError: API 호출 실패 시
    """
    if not UPSTAGE_API_KEY:
        raise ValueError("UPSTAGE_API_KEY 환경 변수가 설정되지 않았습니다.")

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise ValueError(f"파일을 찾을 수 없습니다: {pdf_path}")

    headers = {
        "Authorization": f"Bearer {UPSTAGE_API_KEY}",
    }

    with open(pdf_path, "rb") as f:
        files = {
            "document": (pdf_path.name, f, "application/pdf"),
        }
        data = {
            "output_format": "markdown",
        }

        response = requests.post(
            UPSTAGE_API_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )

    if response.status_code != 200:
        raise RuntimeError(f"API 오류: {response.status_code} - {response.text}")

    result = response.json()
    content = result.get("content", {})
    markdown = content.get("markdown", "") or content.get("text", "")

    return markdown


def refine_headings(markdown: str) -> str:
    """
    Raw Markdown -> 구조화된 Markdown (heading hierarchy 복원)

    Rule-based 변환:
    - "# 1 Introduction" -> "## 1. Introduction"
    - "# 3.1 Method" -> "### 3.1 Method"
    - "# 3.1.1 Details" -> "#### 3.1.1 Details"

    Args:
        markdown: Raw markdown (H1 flat)

    Returns:
        Refined markdown (proper hierarchy)
    """
    lines = markdown.split("\n")
    refined_lines = []
    title_found = False

    for line in lines:
        if line.startswith("#"):
            match = re.match(r"^(#+)\s*(.+)$", line)
            if match:
                content = match.group(2).strip()
                new_level = _detect_heading_level(content, title_found)

                if new_level == 1:
                    title_found = True

                refined_lines.append(f"{'#' * new_level} {content}")
            else:
                refined_lines.append(line)
        else:
            refined_lines.append(line)

    return "\n".join(refined_lines)


def _detect_heading_level(content: str, title_found: bool) -> int:
    """
    Heading 내용을 분석하여 적절한 레벨을 결정

    Args:
        content: Heading 텍스트 (# 제외)
        title_found: 문서 제목이 이미 발견되었는지 여부

    Returns:
        적절한 heading 레벨 (1-4)
    """
    content_stripped = content.strip()

    # Pattern: X.Y.Z (sub-subsection) -> H4
    if re.match(r"^\d+\.\d+\.\d+", content_stripped):
        return 4

    # Pattern: X.Y (subsection) -> H3
    if re.match(r"^\d+\.\d+", content_stripped):
        return 3

    # Pattern: X or X. (main section) -> H2
    if re.match(r"^\d+\.?\s", content_stripped):
        return 2

    # Special sections (Abstract, Introduction, etc.) -> H2
    special_h2 = [
        "abstract",
        "introduction",
        "conclusion",
        "references",
        "acknowledgments",
        "acknowledgements",
        "appendix",
        "related work",
        "background",
        "methodology",
        "methods",
        "results",
        "discussion",
        "experiments",
        "evaluation",
    ]

    if content_stripped.lower() in special_h2:
        return 2

    # 아직 제목이 없으면 H1 (문서 제목)
    if not title_found:
        return 1

    # 기본값: H2
    return 2


def process(pdf_path: str) -> str:
    """
    PDF -> 최종 Markdown (편의 함수)

    parse_pdf()와 refine_headings()를 순차적으로 실행합니다.

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        구조화된 markdown 텍스트
    """
    raw = parse_pdf(pdf_path)
    return refine_headings(raw)
