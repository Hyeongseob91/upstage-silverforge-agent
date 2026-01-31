"""Dataset Curator Agent 사용 예제

Silver markdown 파일의 품질을 검사합니다.

사용법:
    python example_curate.py <markdown_path>
    python example_curate.py results/attention_paper.md
"""

import json
import sys
from pathlib import Path

from silverforge import curate, evaluate_structure, evaluate_semantic


def main():
    if len(sys.argv) < 2:
        print("사용법: python example_curate.py <markdown_path>")
        print("예시: python example_curate.py results/attention_paper.md")
        sys.exit(1)

    md_path = sys.argv[1]

    if not Path(md_path).exists():
        print(f"파일을 찾을 수 없습니다: {md_path}")
        sys.exit(1)

    print(f"품질 검사 중: {md_path}")
    print("=" * 60)

    # Markdown 파일 읽기
    with open(md_path, "r", encoding="utf-8") as f:
        silver_md = f.read()

    print(f"문서 크기: {len(silver_md)} chars, {len(silver_md.split())} words")
    print("-" * 60)

    # 방법 1: 전체 평가 (권장)
    print("\n[전체 품질 평가]")
    result = curate(silver_md)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 방법 2: 개별 평가 (디버깅용)
    # print("\n[구조 평가]")
    # struct = evaluate_structure(silver_md)
    # print(json.dumps(struct, indent=2, ensure_ascii=False))
    #
    # print("\n[의미론적 평가]")
    # semantic = evaluate_semantic(silver_md)
    # print(json.dumps(semantic, indent=2, ensure_ascii=False))

    print("=" * 60)
    print(f"최종 판정: {'PASS' if result['pass'] else 'FAIL'}")
    print(f"권장사항: {result['recommendation']}")


if __name__ == "__main__":
    main()
