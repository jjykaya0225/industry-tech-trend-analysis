"""
parse_hwpx_keywords.py

★2027년 산업기술 환경예측 정량 분석 키워드_최종.hwpx 파일의 표(table)를 파싱해서
산업별 키워드 계층구조(JSON)로 변환한다.

hwpx는 zip 컨테이너이고, Contents/section0.xml 안에 표(hp:tbl > hp:tr > hp:tc)가
들어있다. 병합된 셀(rowSpan/colSpan)은 XML 상에서 병합된 만큼의 tc가 생략되어
있으므로, cellAddr(rowAddr,colAddr)와 cellSpan(rowSpan,colSpan)을 이용해 2차원
그리드를 직접 복원(forward-fill)한다.

사용법:
    python parse_hwpx_keywords.py [hwpx경로] [출력json경로]
    (인자 없이 실행하면 기본 경로 사용)
"""
import sys
import json
import zipfile
from pathlib import Path

if sys.platform == "win32":
    # Windows 콘솔 기본 코드페이지(cp949)에서 한글이 깨져 보이는 문제 방지
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from lxml import etree

NS = {
    "hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
}

# 표 순서 = 문서에 등장하는 순서와 동일 (1.반도체 2.디스플레이 3.이차전지 4.로봇)
TABLE_INDUSTRY_ORDER = ["반도체", "디스플레이", "이차전지", "로봇"]

# ★최종.hwpx 원본 자체에 편집 과정에서 잘린 것으로 보이는 카테고리 라벨들.
# ★2027년 산업기술 환경예측 분석범위(안)_최종.pdf 의 표와 대조해서 확인한 정정값.
# (문장 끝이 "·" 로 끝나는 등 명백히 미완성인 라벨만 보정. 필요시 팀에 원본 재확인 요청할 것)
LABEL_FIXES = {
    "안전·재난·": "안전·재난·국방 로봇",
    "국방·재난·": "국방·재난·공공",
    "SW·": "SW·데이터",
    "패키징·": "패키징·테스트",
    "AI 서버·": "AI 서버·데이터센터",
    "로봇·": "로봇·스마트공장",
    "모바일·": "모바일·가전",
    "자동차·": "자동차·모빌리티",
    "후공정·": "후공정·패키징 장비",
    "디스산업": "디스플레이 산업",
    "사용 후배터리 순환이용": "사용후 배터리 순환이용",
    "내부 가치": "내부 가치사슬",
}

DEFAULT_HWPX = Path(__file__).resolve().parents[2] / "★2027년 산업기술 환경예측 정량 분석 키워드_최종.hwpx"
DEFAULT_OUT = Path(__file__).resolve().parent / "keywords_final.json"


def cell_text(tc: etree._Element) -> str:
    """hp:tc 하위의 모든 hp:t 텍스트를 구분자 없이 그대로 이어붙인다.
    (hwp 편집 과정에서 서식 경계로 인해 한 단어가 여러 hp:t 런으로 쪼개지는 경우가
    있어서, 공백을 추가하지 않고 그대로 concat 해야 원문이 복원된다.)
    """
    parts = []
    for t in tc.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}t"):
        parts.append(t.text or "")
    return "".join(parts).strip()


def parse_table(tbl: etree._Element):
    row_cnt = int(tbl.get("rowCnt"))
    col_cnt = int(tbl.get("colCnt"))
    grid = [[None for _ in range(col_cnt)] for _ in range(row_cnt)]

    for tc in tbl.iter("{http://www.hancom.co.kr/hwpml/2011/paragraph}tc"):
        addr = tc.find("hp:cellAddr", NS)
        span = tc.find("hp:cellSpan", NS)
        if addr is None or span is None:
            continue
        col_addr = int(addr.get("colAddr"))
        row_addr = int(addr.get("rowAddr"))
        col_span = int(span.get("colSpan"))
        row_span = int(span.get("rowSpan"))
        text = cell_text(tc)

        for r in range(row_addr, min(row_addr + row_span, row_cnt)):
            for c in range(col_addr, min(col_addr + col_span, col_cnt)):
                grid[r][c] = text

    return grid


def split_kr_en(keyword_text: str):
    """'국문키워드... / english keywords...' 형태를 국문/영문으로 분리.
    ' / ' 구분자가 없으면 전체를 국문으로 취급.
    """
    if " / " in keyword_text:
        idx = keyword_text.index(" / ")
        kr = keyword_text[:idx].strip()
        en = keyword_text[idx + 3:].strip()
    else:
        kr = keyword_text.strip()
        en = ""
    kr_list = [k.strip() for k in kr.split(",") if k.strip()]
    en_list = [k.strip() for k in en.split(",") if k.strip()]
    return kr_list, en_list


def build_industry_records(grid):
    """4열 표: [구분1(섹션), 구분2(중분류), 구분3(소분류/핵심품목), 키워드]
    5열 표(로봇): [구분1(섹션), 구분2(중분류), 구분3, 구분4(소분류), 키워드]
    맨 마지막 열은 항상 키워드 텍스트, 그 앞 열들은 계층 라벨.
    헤더 행(구분/필수 포함 키워드)과 각주 행은 건너뛴다.
    """
    records = []
    for row in grid:
        if row[-1] is None:
            continue
        *levels, keyword_text = row
        levels = [(lv or "").strip() for lv in levels]
        keyword_text = (keyword_text or "").strip()

        # 헤더 행 스킵
        if keyword_text in ("필수 포함 키워드", ""):
            continue
        if levels and levels[0] == "구분":
            continue
        # 표 컬럼 수가 계층 깊이보다 많은 경우(예: 로봇 표 5열), 병합 셀 복원 과정에서
        # 같은 텍스트가 연속된 두 컬럼에 중복될 수 있으므로 연속 중복 레벨은 제거
        dedup_levels = []
        for lv in levels:
            if not dedup_levels or dedup_levels[-1] != lv:
                dedup_levels.append(lv)
        levels = [LABEL_FIXES.get(lv, lv) for lv in dedup_levels]

        # 각주(*로 시작하는 설명행, "※"로 시작하는 주석행)는 keywords가 아니라 note로 별도 저장
        if keyword_text.startswith("※") or keyword_text.startswith("*"):
            records.append({"note": keyword_text, "levels": levels})
            continue

        kr, en = split_kr_en(keyword_text)
        records.append({
            "levels": levels,        # 예: ["반도체 설계·생산(본산업)", "메모리반도체", "HBM"]
            "keywords_kr": kr,
            "keywords_en": en,
            "raw": keyword_text,
        })
    return records


def main():
    hwpx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_HWPX
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

    z = zipfile.ZipFile(hwpx_path)
    xml_bytes = z.read("Contents/section0.xml")
    root = etree.fromstring(xml_bytes)

    tables = root.findall(".//hp:tbl", NS)
    print(f"발견된 표 개수: {len(tables)}")

    result = {}
    for industry, tbl in zip(TABLE_INDUSTRY_ORDER, tables):
        grid = parse_table(tbl)
        records = build_industry_records(grid)
        result[industry] = records
        print(f"  - {industry}: {tbl.get('rowCnt')}행 x {tbl.get('colCnt')}열 -> 레코드 {len(records)}개")

    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장 완료: {out_path}")


if __name__ == "__main__":
    main()
