"""SilverForge 사용 예제

PDF 파일을 구조화된 Markdown으로 변환합니다.

사용법:
    python example.py <pdf_path>
    python example.py paper.pdf
"""

import sys
from pathlib import Path

from silverforge import process, parse_pdf, refine_headings


def main():
    if len(sys.argv) < 2:
        print("사용법: python example.py <pdf_path>")
        print("예시: python example.py paper.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    if not Path(pdf_path).exists():
        print(f"파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    print(f"PDF 파싱 중: {pdf_path}")
    print("-" * 50)

    # 방법 1: 한 번에 처리
    # result = process(pdf_path)

    # 방법 2: 단계별 처리 (디버깅용)
    print("1. Upstage Document Parse API 호출 중...")
    raw_md = parse_pdf(pdf_path)
    print(f"   -> Raw markdown: {len(raw_md)} chars")

    print("2. Heading hierarchy 복원 중...")
    refined_md = refine_headings(raw_md)
    print(f"   -> Refined markdown: {len(refined_md)} chars")

    # 결과 저장
    output_path = Path(pdf_path).stem + "_silver.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(refined_md)

    print("-" * 50)
    print(f"완료! 결과 저장: {output_path}")

    # 미리보기
    print("\n[미리보기 - 처음 500자]")
    print(refined_md[:500])


if __name__ == "__main__":
    main()
