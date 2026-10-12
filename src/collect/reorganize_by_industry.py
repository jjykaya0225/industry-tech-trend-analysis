"""
reorganize_by_industry.py — 이미 수집된 NTIS 원자료를 "산업 단위 + 메타데이터 태깅"
구조로 재정리한다.

## 배경 (교수님 코멘트 반영)

기존 방식: output/ntis/raw/{industry}/{item}__{field}__{year}.xml
  -> 검색 조건(품목×필드×연도)마다 파일이 따로 나뉘어 있어서 분석하기 어려움.

개선 방식: output/ntis/by_industry/{industry}.xlsx
  -> 산업 단위로 파일 1개씩만 두고, 그 안에서 각 레코드(행)에 분류 기준표
     (섹션/중분류/핵심품목/검색필드/연도) 메타데이터를 컬럼으로 "태깅"해서 관리.
     -> 폴더를 뒤질 필요 없이 Excel/pandas 필터 한 번으로 원하는 조합을 뽑을 수 있음.
  -> NTIS와 WoS는 각각 output/ntis/, output/wos/ 로 완전히 분리 유지
     (보고서 작성 시 두 데이터가 따로 쓰이기 때문).

원본 raw XML(output/ntis/raw/)은 감사·디버그용으로 그대로 남겨두되, **분석은
이제 by_industry/ 밑의 태깅된 파일을 기준으로 한다.**

## 태깅 스키마 (분류 기준표 = keywords_flat.xlsx 체계를 그대로 따름)

  industry       : 산업 (반도체/디스플레이/이차전지/로봇)
  section        : 본산업/후방산업/전방산업/내부가치사슬/사용후 배터리 순환이용/BaaS
  large_category : 중분류
  item           : 핵심품목(소분류)
  search_field   : 검색에 사용한 필드 (TI=과제명, KW=키워드)
  year           : 기준년도(PY)
  + NTIS 원본 필드들 (과제명, 키워드, 부처명, 예산 등)

사용법:
    python reorganize_by_industry.py
    (ntis_collected_raw.json 이 이미 있어야 함 — collect_ntis.py 실행 결과물)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
IN_JSON = HERE.parent / "output" / "ntis" / "ntis_collected_raw.json"
OUT_DIR = HERE.parent / "output" / "ntis" / "by_industry"

# 태깅 컬럼을 맨 앞으로, 사람이 읽기 좋은 이름으로 정리
TAG_RENAME = {
    "_industry": "industry",
    "_section": "section",
    "_large_category": "large_category",
    "_item": "item",
    "_search_field": "search_field",
    "_year": "year",
}
TAG_COLS = list(TAG_RENAME.values())


def main():
    if not IN_JSON.exists():
        print(f"입력 파일이 없습니다: {IN_JSON}")
        print("먼저 collect_ntis.py 를 실행해서 데이터를 수집하세요.")
        return

    data = json.loads(IN_JSON.read_text(encoding="utf-8"))
    df = pd.DataFrame(data)
    df = df.rename(columns=TAG_RENAME)
    df.insert(0, "source", "NTIS")

    # 태깅 컬럼을 맨 앞으로 정렬
    other_cols = [c for c in df.columns if c not in TAG_COLS and c != "source"]
    df = df[["source"] + TAG_COLS + other_cols]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"전체 {len(df)}건 -> 산업별로 분리 저장")
    for industry, sub in df.groupby("industry"):
        out_path = OUT_DIR / f"{industry}.xlsx"
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            sub.to_excel(writer, sheet_name="raw_tagged", index=False)

            year_pivot = sub.groupby(["section", "large_category", "item", "year"]).size() \
                             .reset_index(name="건수")
            year_pivot.to_excel(writer, sheet_name="연도별_집계", index=False)

            if "ministry" in sub.columns:
                ministry_pivot = sub.groupby(["item", "ministry"]).size() \
                                     .reset_index(name="건수") \
                                     .sort_values("건수", ascending=False)
                ministry_pivot.to_excel(writer, sheet_name="부처별_집계", index=False)

            section_pivot = sub.groupby(["section", "large_category"]).size() \
                                .reset_index(name="건수")
            section_pivot.to_excel(writer, sheet_name="구분별_집계", index=False)

        print(f"  {industry}: {len(sub)}건 -> {out_path}")

    print(f"\n완료. 산업별 태깅 데이터: {OUT_DIR}")
    print("(기존 output/ntis/raw/ 의 조건별 XML은 감사용으로 남아있지만, 분석은 여기 기준)")


if __name__ == "__main__":
    main()
