"""SilverForge - PDF를 구조화된 Markdown으로 변환

Upstage Document Parse API를 사용하여 PDF를 파싱하고,
Rule-based 방식으로 heading hierarchy를 복원합니다.
"""

import base64
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일을 명시적으로 로드
# src/silverforge/core.py -> src/silverforge -> src -> project_root
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)

UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY")
UPSTAGE_API_URL = "https://api.upstage.ai/v1/document-ai/document-parse"


@dataclass
class ParseResult:
    """PDF 파싱 결과"""
    markdown: str
    images: dict[str, str] = field(default_factory=dict)  # {image_id: base64_data}
    raw_response: Optional[dict] = None

    def to_markdown_with_images(self) -> str:
        """이미지가 포함된 마크다운 반환 (base64 inline)"""
        result = self.markdown

        # 이미지 참조를 base64 data URI로 변환
        for img_id, img_data in self.images.items():
            # ![image](image_id) 패턴을 찾아서 base64로 변환
            patterns = [
                f"!\\[([^\\]]*)\\]\\({img_id}\\)",
                f"!\\[([^\\]]*)\\]\\({img_id.replace('.', '\\.')}\\)",
                f"!\\[\\]\\({img_id}\\)",
            ]

            for pattern in patterns:
                result = re.sub(
                    pattern,
                    f'![\\1](data:image/png;base64,{img_data})',
                    result
                )

        return result


def parse_pdf(pdf_path: str, extract_images: bool = True) -> str:
    """
    PDF -> Raw Markdown (Upstage Document Parse)

    Args:
        pdf_path: PDF 파일 경로
        extract_images: 이미지 추출 여부 (기본: True)

    Returns:
        Raw markdown 텍스트 (이미지 포함)

    Raises:
        ValueError: API KEY가 없거나 파일이 없는 경우
        RuntimeError: API 호출 실패 시
    """
    result = parse_pdf_with_images(pdf_path, extract_images)
    return result.to_markdown_with_images()


def parse_pdf_with_images(pdf_path: str, extract_images: bool = True) -> ParseResult:
    """
    PDF -> ParseResult (마크다운 + 이미지 분리)

    Args:
        pdf_path: PDF 파일 경로
        extract_images: 이미지 추출 여부

    Returns:
        ParseResult 객체 (markdown, images)
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

        # 이미지 추출 옵션
        if extract_images:
            data["base64_encoding"] = "['figure']"

        response = requests.post(
            UPSTAGE_API_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=180,
        )

    if response.status_code != 200:
        raise RuntimeError(f"API 오류: {response.status_code} - {response.text}")

    result = response.json()

    # 마크다운 추출
    content = result.get("content", {})
    markdown = content.get("markdown", "") or content.get("text", "")

    # 이미지 추출
    images = {}
    elements = result.get("elements", [])

    for element in elements:
        if element.get("category") in ["figure", "chart", "diagram", "image"]:
            element_id = element.get("id", "")
            base64_data = element.get("base64_encoding", "")

            if base64_data:
                images[element_id] = base64_data

                # 마크다운에 이미지 참조가 없으면 추가
                img_ref = f"![{element_id}]"
                if img_ref not in markdown and element_id not in markdown:
                    # 해당 위치에 이미지 삽입 (bounding_box 기반)
                    page = element.get("page", 1)
                    markdown += f"\n\n![Figure {element_id}](data:image/png;base64,{base64_data})\n"

    return ParseResult(
        markdown=markdown,
        images=images,
        raw_response=result,
    )


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


def process(pdf_path: str, extract_images: bool = True) -> str:
    """
    PDF -> 최종 Markdown (편의 함수)

    parse_pdf()와 refine_headings()를 순차적으로 실행합니다.

    Args:
        pdf_path: PDF 파일 경로
        extract_images: 이미지 추출 여부 (기본: True)

    Returns:
        구조화된 markdown 텍스트 (이미지 포함)
    """
    raw = parse_pdf(pdf_path, extract_images)
    return refine_headings(raw)


def process_with_images(pdf_path: str) -> ParseResult:
    """
    PDF -> ParseResult (마크다운 + 이미지 분리)

    이미지를 별도로 관리해야 할 때 사용합니다.

    Args:
        pdf_path: PDF 파일 경로

    Returns:
        ParseResult 객체
    """
    result = parse_pdf_with_images(pdf_path, extract_images=True)
    result.markdown = refine_headings(result.markdown)
    return result
