"""
collect_ntis.py — 핵심 품목별 NTIS R&D 과제 데이터 자동 수집

data_collection/keywords/keywords_flat.xlsx 의 "전체" 시트(산업별 핵심 품목 + OR
검색식)를 읽어서, 핵심 품목마다 NTIS "국가R&D 과제검색 서비스(전체용)" API를 호출하고
결과를 output/ntis/ 에 저장한다.

수집 설계 (회의록/팀 확정 방침 반영):
  - searchFd: TI(과제명), KW(키워드) 둘 다 검색해서 합침 (회의록: "검색 위치: 제목,
    키워드 다 해봐야 할 것 같다")
  - 연도(PY): 2022~2026 각 연도를 별도로 호출해서 카운팅 (회의록 확정: "연구 진행
    기간 전부 카운팅 - 2025~2027 과제는 각 연도별로 한 번씩 카운팅됨" -> 굳이 range
    연산자 문법을 추측할 필요 없이, 연도별로 PY=YYYY/SAME 호출을 5번 하는 게 가장
    명확하고 검증하기 쉬움)
  - 키워드 OR 쿼리가 너무 길면(문항이 많은 핵심품목) 청크로 나눠서 여러 번 호출 후 병합
  - 페이지네이션: totalCount 넘을 때까지 자동 반복

사용법:
    (1) .env에 NTIS_API_KEY 설정 후 먼저 아래로 스키마 확인:
        python ntis_client.py --selftest
    (2) 전체 수집 실행:
        python collect_ntis.py                  # 전체 산업/전체 핵심품목
        python collect_ntis.py --industry 반도체  # 특정 산업만
        python collect_ntis.py --limit 3         # 핵심품목 3개만 (테스트용)
        python collect_ntis.py --dry-run         # 실제 호출 없이 요청 목록만 출력
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from ntis_client import fetch_all_pages, NtisApiError

HERE = Path(__file__).resolve().parent
KEYWORDS_XLSX = HERE.parent / "keywords" / "keywords_flat.xlsx"
OUT_DIR = HERE.parent / "output" / "ntis"
RAW_DIR = OUT_DIR / "raw"

YEARS = [2022, 2023, 2024, 2025, 2026]
SEARCH_FIELDS = ["TI", "KW"]  # 과제명, 키워드
KEYWORD_CHUNK_SIZE = 30  # SRWR 쿼리 하나에 들어가는 최대 키워드 수 (URL 길이 안전장치)

def chunk_keywords(keywords: list[str], size: int):
    for i in range(0, len(keywords), size):
        yield keywords[i:i + size]


def dedup_key(row: dict):
    # ntis_client.HIT_FIELD_MAP 기준 과제고유번호(project_number) + 기준년도(project_year)
    # 조합이 실제 고유키. (같은 과제라도 연도별 검색이라 project_year가 다르면 별개 레코드로
    # 취급해야 "연도별 카운팅" 방침과 맞음 — 완전 동일한 과제/연도 중복만 제거)
    pn = row.get("project_number")
    py = row.get("project_year")
    if pn:
        return ("project_number+year", pn, py)
    # 혹시 project_number가 비어있으면(예상 밖 스키마) 전체 값을 키로 사용해 완전중복만 제거
    return tuple(sorted(row.items()))


def collect_for_item(industry: str, item: str, section: str, large_category: str,
                      keywords_kr: list[str], keywords_en: list[str],
                      dry_run: bool = False):
    all_keywords = [k for k in (keywords_kr + keywords_en) if k]
    if not all_keywords:
        return []

    results = []
    seen = set()

    for field_name in SEARCH_FIELDS:
        for year in YEARS:
            for chunk in chunk_keywords(all_keywords, KEYWORD_CHUNK_SIZE):
                query = "|".join(chunk)

                if dry_run:
                    print(f"[DRY-RUN] industry={industry} item={item} field={field_name} "
                          f"year={year} n_keywords={len(chunk)} query_preview={query[:60]}...")
                    continue

                try:
                    items, raw_pages, total_count = fetch_all_pages(
                        query=query, search_fd=field_name, year=year,
                    )
                except NtisApiError as e:
                    print(f"  [ERROR] {industry}/{item} field={field_name} year={year}: {e}")
                    continue
                except Exception as e:  # noqa: BLE001
                    print(f"  [ERROR] {industry}/{item} field={field_name} year={year}: {e!r}")
                    continue

                # raw XML 저장 (감사/디버그용)
                safe_item = "".join(c if c.isalnum() else "_" for c in item)[:40]
                raw_path = RAW_DIR / industry / f"{safe_item}__{field_name}__{year}.xml"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text("\n<!-- PAGE BREAK -->\n".join(raw_pages), encoding="utf-8")

                for row in items:
                    key = dedup_key(row)
                    if key in seen:
                        continue
                    seen.add(key)
                    enriched = dict(row)
                    enriched.update({
                        "_industry": industry,
                        "_section": section,
                        "_large_category": large_category,
                        "_item": item,
                        "_search_field": field_name,
                        "_year": year,
                    })
                    results.append(enriched)

                print(f"  {industry}/{item} field={field_name} year={year}: "
                      f"totalCount={total_count} 수집={len(items)}건 (누적 dedup={len(results)})")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--industry", help="특정 산업만 수집 (반도체/디스플레이/이차전지/로봇)")
    ap.add_argument("--limit", type=int, help="핵심품목 N개만 (테스트용)")
    ap.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 요청 목록만 출력")
    args = ap.parse_args()

    df = pd.read_excel(KEYWORDS_XLSX, sheet_name="전체")
    if args.industry:
        df = df[df["industry"] == args.industry]
    if args.limit:
        df = df.head(args.limit)

    print(f"대상 핵심품목/카테고리 {len(df)}건")

    all_results = []
    for _, row in df.iterrows():
        kr = [k.strip() for k in str(row["keywords_kr"]).split(",") if k.strip()]
        en = [k.strip() for k in str(row["keywords_en"]).split(",") if k.strip()]
        res = collect_for_item(
            industry=row["industry"], item=row["item"],
            section=row["section"], large_category=row["large_category"],
            keywords_kr=kr, keywords_en=en, dry_run=args.dry_run,
        )
        all_results.extend(res)

    if args.dry_run:
        print("\n[DRY-RUN] 완료 (실제 데이터 수집 없음)")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = OUT_DIR / "ntis_collected_raw.json"
    out_json.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    if all_results:
        result_df = pd.DataFrame(all_results)
        out_xlsx = OUT_DIR / "ntis_collected.xlsx"
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
            result_df.to_excel(writer, sheet_name="raw", index=False)
            pivot = result_df.groupby(["_industry", "_item", "_year"]).size().reset_index(name="건수")
            pivot.to_excel(writer, sheet_name="연도별_집계", index=False)
        print(f"\n총 {len(result_df)}건 수집 완료")
        print(f"저장(통합본): {out_xlsx}")
    else:
        print("\n수집된 데이터가 없습니다. (API 키 확인 또는 --selftest로 스키마 재확인 필요)")

    print(f"원본 JSON: {out_json}")
    print(f"조건별 raw XML(감사용): {RAW_DIR}")

    # 산업 단위 + 메타데이터 태깅 구조로도 재정리 (교수님 코멘트 반영 —
    # 검색조건별 폴더 대신, 산업별 파일 하나에 분류기준표 태그 컬럼으로 관리)
    if all_results:
        import subprocess
        subprocess.run([sys.executable, str(HERE / "reorganize_by_industry.py")], check=False)


if __name__ == "__main__":
    main()
