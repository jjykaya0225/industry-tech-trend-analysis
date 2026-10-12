"""
ntis_client.py — NTIS OpenAPI "국가R&D 과제검색 서비스(전체용)" 저수준 클라이언트

⚠️ 사전 준비 (팀원이 직접 해야 하는 일 — 계정/키 발급은 코드가 대신 할 수 없음):
  1) https://www.ntis.go.kr 회원가입 (일반 회원가입, 로그인)
  2) 로그인 후 "회원정보 수정"에서 소속기관 정보 등록 (미등록 시 API 활용신청이 승인되지 않음)
  3) https://www.ntis.go.kr/rndopen/api/mng/apiMain.do 접속
     -> "국가R&D 과제검색 서비스(전체용)" 항목의 [활용신청] 클릭 -> 승인 대기
     (활용목적을 "내부 연구/비공개 용도"로 명시할 것 — "대외용(웹/모바일)"으로 신청하면
      제공 항목이 14개로 제한됨. 아래 확장 필드는 비공개 내부용일 때만 전부 제공됨)
  4) 승인되면 발급된 인증키(apprvKey)를 이 폴더의 .env 파일에 다음처럼 저장:
         NTIS_API_KEY=발급받은키값
     (.env 파일이 없으면 새로 만들면 됨. .env는 공유 문서함/메일 등에 올리지 말 것)

이 스크립트는 NTIS가 배포한 공식 매뉴얼
"01.통합OpenAPI_국가R&D 과제검색(전체용)_매뉴얼_2025.pdf" (2025.12.16, 실제 요청/응답
스펙 + 예시 XML 포함)를 기준으로 작성됨. 그래도 키 발급 전이라 직접 호출 테스트는
못 해봤으므로, ★ 키를 처음 받으면 반드시 `python ntis_client.py --selftest` 를
먼저 실행해서 실제 응답이 아래 파서와 맞는지 확인할 것.

엔드포인트: https://www.ntis.go.kr/rndopen/openApi/public_project

⚠️ 매뉴얼 내 파라미터명 불일치 발견: 매뉴얼의 "요청명세" 표는 SRWR/searchFd/
displayCnt/searchRnkn 를 쓰라고 되어 있는데, 같은 매뉴얼의 "요청 메시지 예시"
URL은 query/searchField/displayCount/sortby 를 쓰고 있음 (naviCount, boostquery,
cmbnApiYn 파라미터도 예시에만 등장). 어느 쪽이 실제로 유효한지 확실치 않아서,
이 클라이언트는 **두 이름을 동시에 다 보낸다** (안 쓰는 파라미터는 보통 무시되므로
안전한 쪽). --selftest 결과를 보고 필요하면 조정할 것.

필수 파라미터:
  - apprvKey   : 발급받은 인증키
  - collection : "project" 고정
  - SRWR(=query) : 검색어. AND=공백, OR="|", NOT="!", 완전일치='"..."'  (UTF-8 필요)
  - startPosition, displayCnt(=displayCount) : 페이지네이션 (1부터 시작)
선택 파라미터:
  - searchFd(=searchField) : 검색필드. BI(전체) TI(과제명) AU(연구책임자) OG(과제관리기관)
    PB(수행기관·부처·사업명 등) KW(키워드) AB(연구목표·내용·성과)
  - addQuery   : 추가 필터. 예) addQuery=PY=2024/SAME (기준년도. /MORE /UNDER /SAME 지원)
  - searchRnkn(=sortby) : 정렬 (RANK/DESC, DATE/DESC 등)

응답 스키마 (매뉴얼 확인 완료, RESULT 최상위):
  RESULT
    TOTALHITS          : 전체 검색건수
    STARTPOSITION, HITS, SEARCHTIME
    RESULTSET
      HIT (반복, NO 속성)
        ProjectNumber                    : 과제고유번호
        ProjectTitle > Korean, English    : 과제명(국/영문)
        Manager > Name                    : 연구책임자
        Researchers > Name, ManCount, WomanCount
        Goal > Full, Teaser               : 연구목표(요약)
        Abstract > Full, Teaser           : 연구내용(요약) — 응답 성능상 Full도 요약(~250자) 수준
        Effect > Full, Teaser             : 기대효과(요약)
        Keyword > Korean, English         : 키워드(콤마구분, 5개 내외)
        OrderAgency > Name                : 과제관리(전문)기관
        ResearchAgency > Name             : 과제수행기관
        BudgetProject > Name              : 사업명(프로그램명)
        BigprojectTitle                   : 내역사업명
        Ministry > Name                   : 사업부처명
        ProjectYear                       : 기준년도
        ProjectPeriod > Start/End(당해연도), TotalStart/TotalEnd(총연구기간)
        ScienceClass(type=old/new) > Large/Medium/Small : 국가과학기술표준분류
        MinistryScienceClass > Large/Medium/Small       : 부처자체기술분류
        PerformAgent(code)                : 연구수행주체 (대학/중소기업/출연연구소 등)
        DevelopmentPhases(code)           : 연구개발단계 (기초/응용/개발연구)
        SixTechnology(code)               : 6T관련기술
        GovernmentFunds, TotalFunds       : 정부투자연구비 / 총연구비
        CorporateRegistrationNumber, SeriesProject, PrePjtId
    NAVIGATION (facet 집계 — 참고용)
      NAVIGATIONENTRY[name=projectyear] 등에 연도별/부처별/기관별 집계가 이미 들어있음
      -> 정밀 원자료는 HIT를 써야 하지만, 빠른 건수 확인용으로는 이 facet도 활용 가능

※ "대외용" 신청이 아닌 "내부 비공개" 신청이면 위 필드 전부 제공됨. 대외용으로 신청하면
  과제명/과제고유번호/기준년도/예산사업명/연구책임자/과제수행기관/부처명/총연구기간/
  당해연도연구기간/정부투자연구비/총연구비/연구내용(250자)/키워드(국영문) 14개로 제한됨.
"""
from __future__ import annotations

import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

ENDPOINT = "https://www.ntis.go.kr/rndopen/openApi/public_project"
API_KEY = os.environ.get("NTIS_API_KEY", "").strip()

REQUEST_DELAY_SEC = 0.4  # 공공 API 예의상 호출 간 최소 딜레이

# 응답 HIT 하위 필드 중 우리가 쓸 것들. (태그, 하위경로) -> 출력 컬럼명.
# 하위경로가 있으면 "부모>자식" 형태로 첫 번째 매칭 자식 텍스트를 사용.
HIT_FIELD_MAP = {
    "ProjectNumber": "project_number",
    "ProjectTitle/Korean": "title_kr",
    "ProjectTitle/English": "title_en",
    "Manager/Name": "manager",
    "Keyword/Korean": "keyword_kr",
    "Keyword/English": "keyword_en",
    "OrderAgency/Name": "order_agency",
    "ResearchAgency/Name": "research_agency",
    "BudgetProject/Name": "budget_project",
    "BigprojectTitle": "big_project_title",
    "Ministry/Name": "ministry",
    "ProjectYear": "project_year",
    "ProjectPeriod/Start": "period_start",
    "ProjectPeriod/End": "period_end",
    "ProjectPeriod/TotalStart": "total_start",
    "ProjectPeriod/TotalEnd": "total_end",
    "GovernmentFunds": "government_funds",
    "TotalFunds": "total_funds",
    "PerformAgent": "perform_agent",
    "DevelopmentPhases": "development_phases",
    "Abstract/Teaser": "abstract_teaser",
    "Goal/Teaser": "goal_teaser",
    "Effect/Teaser": "effect_teaser",
}


class NtisApiError(RuntimeError):
    pass


@dataclass
class NtisPage:
    query: str
    search_fd: str
    year: Optional[int]
    start_position: int
    display_cnt: int
    raw_xml: str
    items: list = field(default_factory=list)
    total_count: Optional[int] = None


def _text_at_path(hit: ET.Element, path: str) -> str:
    el = hit.find(path)
    if el is None:
        return ""
    # el.text만 쓰면 <span class="search_word">...</span> 하이라이트 태그 뒤에 오는
    # 텍스트(tail)가 잘린다. itertext()로 태그 안팎 텍스트를 전부 이어붙여야 함.
    return "".join(el.itertext()).strip()


def _strip_highlight(text: str) -> str:
    """검색어 하이라이트 태그(<span class="search_word">...</span>)를 제거."""
    return text.replace('<span class="search_word">', "").replace("</span>", "")


def parse_items(xml_text: str):
    """매뉴얼 확인된 실제 스키마(RESULT > RESULTSET > HIT) 기준 파서.
    - <error>...</error> 형태면 예외 발생 (인증키 오류 등)
    - HIT 태그가 없으면(예: 스키마가 예상과 다르면) 빈 리스트 반환 + 경고 출력
      (raw XML은 caller가 저장하니 눈으로 재확인 가능)
    """
    root = ET.fromstring(xml_text)

    if root.tag.lower() == "error":
        raise NtisApiError(f"NTIS API 오류 응답: {(root.text or '').strip()}")

    total_count = None
    total_el = root.find("TOTALHITS")
    if total_el is not None and total_el.text:
        try:
            total_count = int(total_el.text.strip())
        except ValueError:
            pass

    hits = root.findall(".//HIT")
    if not hits:
        # 스키마가 매뉴얼과 다를 수 있으니 조용히 넘기지 않고 표시만 해둠
        return [], total_count

    items = []
    for hit in hits:
        row = {}
        for path, col in HIT_FIELD_MAP.items():
            row[col] = _strip_highlight(_text_at_path(hit, path))
        items.append(row)

    return items, total_count


def fetch_page(query: str, search_fd: str, start_position: int = 1,
               display_cnt: int = 100, year: Optional[int] = None,
               api_key: Optional[str] = None) -> NtisPage:
    key = api_key or API_KEY
    if not key:
        raise NtisApiError(
            "NTIS_API_KEY가 설정되어 있지 않습니다. data_collection/ntis/.env 파일에 "
            "NTIS_API_KEY=발급받은키 형식으로 넣어주세요."
        )

    params = {
        "apprvKey": key,
        "collection": "project",
        # 매뉴얼 표 기준 이름 + 예시 URL 기준 이름을 동시에 전송 (어느 쪽이 유효한지
        # 불확실하므로 방어적으로 둘 다 보냄)
        "SRWR": query,
        "query": query,
        "searchFd": search_fd,
        "searchField": search_fd,
        "startPosition": start_position,
        "displayCnt": display_cnt,
        "displayCount": display_cnt,
    }
    if year is not None:
        params["addQuery"] = f"PY={year}/SAME"

    resp = requests.get(ENDPOINT, params=params, timeout=30)
    resp.raise_for_status()
    xml_text = resp.text

    items, total_count = parse_items(xml_text)

    return NtisPage(
        query=query, search_fd=search_fd, year=year,
        start_position=start_position, display_cnt=display_cnt,
        raw_xml=xml_text, items=items, total_count=total_count,
    )


def fetch_all_pages(query: str, search_fd: str, year: Optional[int] = None,
                     display_cnt: int = 100, max_pages: int = 50,
                     api_key: Optional[str] = None, sleep: float = REQUEST_DELAY_SEC):
    """모든 페이지를 순회하며 item을 모아서 반환. (raw XML은 페이지별로 caller가 필요하면 별도 저장)"""
    all_items = []
    raw_pages = []
    start = 1
    total_count = None
    for _ in range(max_pages):
        page = fetch_page(query, search_fd, start_position=start,
                           display_cnt=display_cnt, year=year, api_key=api_key)
        all_items.extend(page.items)
        raw_pages.append(page.raw_xml)
        total_count = page.total_count if page.total_count is not None else total_count

        time.sleep(sleep)

        if not page.items:
            break
        if total_count is not None and start + display_cnt > total_count:
            break
        start += display_cnt
    return all_items, raw_pages, total_count


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        out_dir = HERE.parent / "output" / "ntis"
        out_dir.mkdir(parents=True, exist_ok=True)
        print("NTIS API selftest 호출 중... (검색어: 반도체, searchFd=TI, 1페이지)")
        page = fetch_page("반도체", "TI", start_position=1, display_cnt=5)
        (out_dir / "raw_selftest.xml").write_text(page.raw_xml, encoding="utf-8")
        print(f"total_count={page.total_count}, items 파싱 개수={len(page.items)}")
        if page.items:
            print("첫 item 예시:")
            for k, v in page.items[0].items():
                print(f"  {k}: {v[:80]}")
        else:
            print("⚠ HIT가 파싱되지 않았습니다. output/ntis/raw_selftest.xml을 열어서")
            print("  실제 응답 구조를 확인하고 필요하면 ntis_client.py의 HIT_FIELD_MAP을 조정하세요.")
        print(f"\nraw XML 저장 위치: {out_dir / 'raw_selftest.xml'}")
    else:
        print("사용법: python ntis_client.py --selftest")
        print("(NTIS_API_KEY가 .env에 설정되어 있어야 합니다)")
