"""
wos_playwright.py — Web of Science 데이터 수집 자동화 (Playwright)

✅ 2026-08-13, 실제 로그인된 화면에서 검색/집계/내보내기 UI를 직접 확인하고 작성함
   (Advanced Search > Fielded Search, Analyze Results, Export to Excel 흐름 확인 완료).
   다만 셀렉터는 눈으로 클릭해본 좌표 기준으로 유추한 것이라, WoS가 UI를 바꾸면 깨질 수
   있음 — 처음 실행할 때는 headless=False로 돌려서 눈으로 한 번 확인할 것.

## 설계 개요

핵심 아이디어: 회의록/NTIS 설계처럼 연도별로 5번씩 검색을 반복하지 않는다.
WoS Advanced Search 결과 화면에는 **"Analyze Results" 기능**이 있고, 여기서
"Publication Years" / "Countries/Regions" 등을 선택하면 **집계 결과를 바로
다운로드**할 수 있다 (검색 결과 전체를 1000건씩 끊어서 다운로드할 필요 없음).
그래서:

  1. 핵심품목 하나당 검색은 "1회"만 한다 (연도 필터 없이 전체 기간으로 검색 —
     Analyze Results가 어차피 연도별로 다 쪼개서 보여주기 때문).
  2. 검색 필드는 NTIS와 동일하게 Title / Author Keywords 두 번 따로 검색
     (TI/KW 상응 개념).
  3. 결과 화면에서 "Analyze Results" → "Publication Years" 선택 → Download
     → 연도별 건수 파일 확보. 필요하면 "Countries/Regions"도 동일하게 반복
     (국가별 연구 점유율 분석용).
  4. 논문 제목/키워드 등 실제 메타데이터까지 필요한 소수 핵심품목에 한해서만,
     추가로 "Export to Excel" (Full Record, 최대 1000건/회)로 원자료를 받는다
     (전체 핵심품목에 대해 이걸 다 하면 매우 오래 걸리므로 기본은 꺼둠).

## 사전 준비

1. 이 폴더에서 최초 1회 로그인 세션을 만들어야 함 (Playwright 전용 브라우저로,
   평소 쓰는 Chrome과는 별개의 세션이라 다시 로그인해야 함):

       python wos_playwright.py --login-only

   브라우저 창이 뜨면 평소처럼 (학교 도서관 경유 등으로) 로그인 → 검색 화면이
   보이면 터미널로 돌아와서 Enter. wos_session.json 에 세션이 저장됨.

2. 이후 실행은 저장된 세션을 재사용:

       python wos_playwright.py --dry-run                 # 요청 목록만 확인
       python wos_playwright.py --industry 반도체 --limit 2  # 소규모 테스트
       python wos_playwright.py                             # 전체 수집
       python wos_playwright.py --with-full-records --limit 2  # 실제 논문 메타데이터까지

세션은 시간이 지나면 만료될 수 있음 — 로그인 페이지로 튕기면 --login-only 재실행.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

HERE = Path(__file__).resolve().parent
SESSION_FILE = HERE / "wos_session.json"
KEYWORDS_XLSX = HERE.parent / "keywords" / "keywords_flat.xlsx"
OUT_DIR = HERE.parent / "output" / "wos"
RAW_DIR = OUT_DIR / "raw"

WOS_URL = "https://www.webofscience.com/wos/woscc/basic-search"
TARGET_YEARS = list(range(2022, 2027))  # 2022~2026
SEARCH_FIELDS = ["Title", "Author Keywords"]  # NTIS의 TI/KW에 해당


def build_query(keywords: list[str]) -> str:
    """키워드 리스트를 WoS 검색식(OR)으로 변환. 공백 포함 키워드는 따옴표로 묶음."""
    parts = []
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        if " " in kw or "-" in kw:
            parts.append(f'"{kw}"')
        else:
            parts.append(kw)
    return " OR ".join(parts)


def do_login_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(WOS_URL)

        print("\n브라우저 창에서 평소처럼 로그인하세요 (학교 도서관 경유 등).")
        print("로그인 완료 후 Advanced Search 화면이 보이면 이 터미널로 돌아와서 Enter.")
        input("로그인 완료했으면 Enter >> ")

        context.storage_state(path=str(SESSION_FILE))
        print(f"세션 저장 완료: {SESSION_FILE}")
        browser.close()


def select_search_field(page, field_label: str):
    """Fielded Search의 첫 번째 필드 드롭다운에서 field_label(예: 'Title',
    'Author Keywords')을 선택한다."""
    page.locator("text=Advanced Search").first.click()
    page.wait_for_timeout(500)
    # 필드 드롭다운(기본값 'Topic') 클릭 후 목록에서 검색해서 선택
    dropdown = page.locator("text=Topic").first
    dropdown.click()
    page.wait_for_timeout(300)
    search_box = page.locator('input[placeholder="Search"]')
    if search_box.count() > 0:
        search_box.fill(field_label)
        page.wait_for_timeout(300)
    page.get_by_text(field_label, exact=True).first.click()


def run_search(page, field_label: str, query: str) -> int:
    """검색 실행 후 총 결과 건수를 반환. 실패 시 -1."""
    select_search_field(page, field_label)
    query_box = page.locator('input[placeholder*="Example"]').first
    query_box.fill(query)
    page.get_by_role("button", name="Search").click()
    page.wait_for_timeout(2000)

    try:
        heading = page.locator("text=/[\\d,]+ results from/").first
        text = heading.inner_text(timeout=10000)
        digits = "".join(c for c in text.split(" ")[0] if c.isdigit())
        return int(digits) if digits else 0
    except PlaywrightTimeoutError:
        return -1


def download_analysis(page, analyze_by: str, save_path: Path) -> bool:
    """검색 결과 화면에서 'Analyze Results' -> analyze_by(예: 'Publication Years',
    'Countries/Regions') 선택 -> Download. save_path에 저장."""
    page.get_by_role("button", name="Analyze Results").click()
    page.wait_for_timeout(1500)

    field_dropdown = page.locator("text=Web of Science Categories").first
    if field_dropdown.count() == 0:
        # 이미 다른 필드가 선택되어 있을 수 있음 -> 현재 선택된 드롭다운 버튼을 찾음
        field_dropdown = page.locator("button:has-text('Publication Years'), button:has-text('Web of Science')").first
    field_dropdown.click()
    page.wait_for_timeout(300)
    page.get_by_text(analyze_by, exact=True).first.click()
    page.wait_for_timeout(1000)

    save_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with page.expect_download(timeout=15000) as dl_info:
            page.get_by_role("button", name="DOWNLOAD").click()
        download = dl_info.value
        download.save_as(str(save_path))
        return True
    except PlaywrightTimeoutError:
        print(f"    [WARN] '{analyze_by}' 다운로드 실패 (타임아웃) — 화면 구조가 바뀌었을 수 있음")
        return False


def export_full_records(page, save_dir: Path, prefix: str, total_count: int, batch_size: int = 1000):
    """Full Record Excel 내보내기 (1000건씩 나눠서). 필요할 때만 호출할 것 —
    시간이 오래 걸림."""
    save_dir.mkdir(parents=True, exist_ok=True)
    n_batches = (min(total_count, 10000) + batch_size - 1) // batch_size  # 안전상 최대 1만건까지만
    for i in range(n_batches):
        start = i * batch_size + 1
        end = min(start + batch_size - 1, total_count)

        page.get_by_role("button", name="Export").click()
        page.wait_for_timeout(300)
        page.get_by_text("Excel", exact=True).click()
        page.wait_for_timeout(500)

        page.get_by_text("Records from:").click()
        page.locator('input').nth(0).fill(str(start))
        page.locator('input').nth(1).fill(str(end))

        content_dropdown = page.locator("text=Author, Title, Source").first
        content_dropdown.click()
        page.wait_for_timeout(300)
        page.get_by_text("Full Record", exact=True).click()

        save_path = save_dir / f"{prefix}__{start}-{end}.xlsx"
        try:
            with page.expect_download(timeout=30000) as dl_info:
                page.get_by_role("button", name="Export", exact=True).click()
            download = dl_info.value
            download.save_as(str(save_path))
            print(f"    저장: {save_path.name}")
        except PlaywrightTimeoutError:
            print(f"    [WARN] {start}-{end} 구간 export 실패")
        time.sleep(1)


def parse_year_breakdown_csv(path: Path) -> dict:
    """WoS Analyze Results 다운로드 파일(csv 또는 tsv 형태)을 연도:건수 dict로 파싱.
    실제 파일을 받아봐야 정확한 컬럼 구조를 확정할 수 있어서, 우선 일반적인
    2-column(라벨, 건수) 가정으로 파싱 시도."""
    result = {}
    try:
        with open(path, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue
                label, *rest = row
                label = label.strip()
                if label.isdigit() and len(label) == 4:
                    try:
                        result[int(label)] = int(rest[0].replace(",", ""))
                    except (ValueError, IndexError):
                        pass
    except Exception as e:  # noqa: BLE001
        print(f"    [WARN] 연도별 집계 파일 파싱 실패: {e}")
    return result


def collect_for_item(page, industry: str, item: str, section: str, large_category: str,
                      keywords_kr: list[str], keywords_en: list[str],
                      with_full_records: bool, dry_run: bool):
    query = build_query(keywords_kr + keywords_en)
    if not query:
        return []

    rows = []
    safe_item = "".join(c if c.isalnum() else "_" for c in item)[:40]

    for field_label in SEARCH_FIELDS:
        if dry_run:
            print(f"[DRY-RUN] {industry}/{item} field={field_label} query_preview={query[:60]}...")
            continue

        total = run_search(page, field_label, query)
        print(f"  {industry}/{item} field={field_label}: 총 {total}건")
        if total <= 0:
            continue

        safe_field = field_label.replace(" ", "")
        year_csv = RAW_DIR / industry / f"{safe_item}__{safe_field}__years.csv"
        ok = download_analysis(page, "Publication Years", year_csv)
        year_counts = parse_year_breakdown_csv(year_csv) if ok else {}

        country_csv = RAW_DIR / industry / f"{safe_item}__{safe_field}__countries.csv"
        download_analysis(page, "Countries/Regions", country_csv)

        for year in TARGET_YEARS:
            rows.append({
                "industry": industry, "section": section, "large_category": large_category,
                "item": item, "search_field": field_label,
                "year": year, "count": year_counts.get(year, None),
                "total_all_years": total,
            })

        if with_full_records:
            export_full_records(page, RAW_DIR / industry / "full_records",
                                 f"{safe_item}__{safe_field}", total)

    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login-only", action="store_true")
    ap.add_argument("--industry", help="특정 산업만 (반도체/디스플레이/이차전지/로봇)")
    ap.add_argument("--limit", type=int, help="핵심품목 N개만 (테스트용)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--with-full-records", action="store_true",
                     help="논문 메타데이터(Full Record)까지 Excel로 내려받기 (느림)")
    ap.add_argument("--headed", action="store_true", default=True,
                     help="브라우저 창을 보이게 실행 (기본값 True — 처음엔 눈으로 확인 권장)")
    args = ap.parse_args()

    if args.login_only:
        do_login_flow()
        return

    df = pd.read_excel(KEYWORDS_XLSX, sheet_name="전체")
    if args.industry:
        df = df[df["industry"] == args.industry]
    if args.limit:
        df = df.head(args.limit)
    print(f"대상 핵심품목/카테고리 {len(df)}건")

    # dry-run은 브라우저/세션 없이 바로 요청 목록만 출력
    if args.dry_run:
        for _, row in df.iterrows():
            kr = [k.strip() for k in str(row["keywords_kr"]).split(",") if k.strip()]
            en = [k.strip() for k in str(row["keywords_en"]).split(",") if k.strip()]
            collect_for_item(
                None, industry=row["industry"], item=row["item"],
                section=row["section"], large_category=row["large_category"],
                keywords_kr=kr, keywords_en=en,
                with_full_records=args.with_full_records, dry_run=True,
            )
        print("\n[DRY-RUN] 완료 (실제 수집 없음)")
        return

    if not SESSION_FILE.exists():
        print("저장된 로그인 세션이 없습니다. 먼저 실행하세요: python wos_playwright.py --login-only")
        return

    all_rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(SESSION_FILE), accept_downloads=True)
        page = context.new_page()
        page.goto(WOS_URL)
        page.wait_for_timeout(2000)

        if "login" in page.url.lower() or page.locator("text=Sign in").count() > 0:
            print("⚠ 세션이 만료된 것 같습니다. python wos_playwright.py --login-only 로 재로그인하세요.")
            browser.close()
            return

        for _, row in df.iterrows():
            kr = [k.strip() for k in str(row["keywords_kr"]).split(",") if k.strip()]
            en = [k.strip() for k in str(row["keywords_en"]).split(",") if k.strip()]
            res = collect_for_item(
                page, industry=row["industry"], item=row["item"],
                section=row["section"], large_category=row["large_category"],
                keywords_kr=kr, keywords_en=en,
                with_full_records=args.with_full_records, dry_run=False,
            )
            all_rows.extend(res)

        browser.close()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if all_rows:
        result_df = pd.DataFrame(all_rows)
        result_df.insert(0, "source", "WoS")
        out_xlsx = OUT_DIR / "wos_collected.xlsx"
        result_df.to_excel(out_xlsx, index=False)
        print(f"\n총 {len(result_df)}행 저장(통합본): {out_xlsx}")

        # 산업 단위 + 메타데이터 태깅 구조로 재정리 (NTIS와 동일한 방식 —
        # 검색조건별 폴더 대신 산업별 파일 하나에 분류기준표 태그 컬럼으로 관리.
        # NTIS 데이터와는 output/wos/ vs output/ntis/ 로 완전히 분리 보관함)
        by_industry_dir = OUT_DIR / "by_industry"
        by_industry_dir.mkdir(parents=True, exist_ok=True)
        for industry, sub in result_df.groupby("industry"):
            out_path = by_industry_dir / f"{industry}.xlsx"
            with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
                sub.to_excel(writer, sheet_name="raw_tagged", index=False)
                section_pivot = sub.groupby(["section", "large_category", "item", "search_field"])["count"] \
                                    .sum().reset_index()
                section_pivot.to_excel(writer, sheet_name="구분별_집계", index=False)
            print(f"  {industry}: {len(sub)}행 -> {out_path}")
    else:
        print("\n수집된 데이터가 없습니다.")
    print(f"연도별/국가별 원본 다운로드 파일(감사용): {RAW_DIR}")


if __name__ == "__main__":
    main()
