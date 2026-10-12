"""
export_flat.py

parse_hwpx_keywords.py 가 만든 keywords_final.json(계층 구조)을
"핵심 품목별로 모두 개별 산출"이라는 팀 방침에 맞게 평면(flat) 테이블로 변환한다.

산출물: keywords_flat.xlsx (industry / section / large_category / item(핵심품목) /
        keywords_kr / keywords_en / query_kr / query_en / n_keywords)

- section: 본산업 / 후방산업 / 전방산업 / 내부가치사슬 / 순환이용·BaaS 등 최상위 구분
- item(핵심품목) = 소분류 (예: HBM, HBF, 대형 OLED 패널 ...) → NTIS/WoS 수집 시
  "핵심 품목별 개별 산출"의 기준 단위
- query_kr/query_en = 국문/영문 키워드를 NTIS의 OR 연산자(|) 로 이어붙인 검색식
  (SRWR 파라미터에 바로 넣을 수 있는 형태)
"""
import sys
import json
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
IN_JSON = HERE / "keywords_final.json"
OUT_XLSX = HERE / "keywords_flat.xlsx"
OUT_NOTES = HERE / "keywords_notes.json"

# industry별 level0 라벨을 표준 section 명칭으로 매핑
SECTION_MAP = {
    "반도체 설계·생산": "본산업",
    "디스플레이 산업": "본산업",
    "이차전지산업": "본산업",
    "로봇산업": "본산업",
    "후방산업": "후방산업",
    "전방산업": "전방산업",
    "사용후 배터리 순환이용": "사용후 배터리 순환이용",
    "BaaS": "BaaS",
}


def section_of(levels):
    if not levels:
        return "기타"
    return SECTION_MAP.get(levels[0], levels[0])


def large_category_of(industry, levels, section):
    """대분류(중분류) 산출: 산업별로 계층 깊이가 달라서 규칙을 개별 처리.
    - 본산업이면서 내부가치사슬인 경우 large_category = '내부가치사슬'
    - 그 외에는 levels[1] (있으면), 없으면 section 자체
    """
    if len(levels) >= 2 and levels[1] == "내부 가치사슬":
        return "내부가치사슬"
    if len(levels) >= 2:
        return levels[1]
    return section


def item_of(levels):
    """핵심 품목(소분류) = levels의 마지막 값. 계층이 2단뿐이면(예: 로봇 후방산업의
    '반도체·전자','통신·데이터') large_category 자체가 곧 item."""
    return levels[-1]


def main():
    data = json.loads(IN_JSON.read_text(encoding="utf-8"))

    rows = []
    notes = {}
    for industry, records in data.items():
        notes[industry] = []
        for rec in records:
            if "note" in rec:
                notes[industry].append(rec["note"])
                continue
            levels = rec["levels"]
            section = section_of(levels)
            large_cat = large_category_of(industry, levels, section)
            item = item_of(levels)

            kr = rec["keywords_kr"]
            en = rec["keywords_en"]
            rows.append({
                "industry": industry,
                "section": section,
                "large_category": large_cat,
                "item": item,
                "levels_full": " > ".join(levels),
                "n_keywords_kr": len(kr),
                "n_keywords_en": len(en),
                "keywords_kr": ", ".join(kr),
                "keywords_en": ", ".join(en),
                "query_kr": "|".join(kr),
                "query_en": "|".join(en),
                "query_all": "|".join(kr + en),
            })

    df = pd.DataFrame(rows)

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="전체", index=False)
        for industry in data.keys():
            sub = df[df["industry"] == industry]
            sheet_name = industry[:31]
            sub.to_excel(writer, sheet_name=sheet_name, index=False)

    OUT_NOTES.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"총 {len(df)}개 핵심품목/카테고리 행 -> {OUT_XLSX}")
    print(f"산업별 각주 -> {OUT_NOTES}")
    print(df.groupby(["industry", "section"]).size())


if __name__ == "__main__":
    main()
