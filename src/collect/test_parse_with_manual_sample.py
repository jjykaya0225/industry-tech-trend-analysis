"""매뉴얼(PDF) 안의 실제 응답 예시 XML로 parse_items()를 검증하는 테스트 스크립트.
API 키 없이도 파서 로직만 확인 가능."""
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from ntis_client import parse_items

SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<RESULT>
<TOTALHITS>87122</TOTALHITS>
<STARTPOSITION>1</STARTPOSITION>
<HITS>1</HITS>
<SEARCHTIME>0.303</SEARCHTIME>
<RESULTSET>
 <HIT NO="1">
 <ProjectNumber>1711041912</ProjectNumber>
<ProjectTitle>
 <Korean>스마트 센서 응용을 위한 <span class="search_word">나노</span> 멤브레인 공정 플랫폼 개발</Korean>
 <English>Platform development of nano membrane process for smart sensor application</English>
 </ProjectTitle>
<Manager>
 <Name>이종근</Name>
 </Manager>
<Keyword>
 <Korean><span class="search_word">나노</span> 멤브레인,NEMS,가스 센서, 적외선 센서,공정플랫폼,마이크로 히터</Korean>
<English>Nanomembrane,NEMS,Gassensor,Infraredsensor,Processplatform,Microheater</English>
 </Keyword>
<OrderAgency>
 <Name>한국연구재단</Name>
 </OrderAgency>
<ResearchAgency>
 <Name>한국<span class="search_word">나노</span>기술원</Name>
 </ResearchAgency>
<BudgetProject>
 <Name><span class="search_word">나노</span>·소재기술개발</Name>
 </BudgetProject>
 <BigprojectTitle>선행공정·플랫폼기술연구개발</BigprojectTitle>
<Ministry>
 <Name>미래창조과학부</Name>
 </Ministry>
<ProjectYear>2016</ProjectYear>
<ProjectPeriod>
 <Start>20160701</Start>
<End>20170630</End>
<TotalStart>2015-10-01 00:00:00.0</TotalStart>
<TotalEnd>2020-06-30 00:00:00.0</TotalEnd>
 </ProjectPeriod>
<PerformAgent code="99">기타</PerformAgent>
<DevelopmentPhases code="03">개발연구</DevelopmentPhases>
<GovernmentFunds>300000000</GovernmentFunds>
<TotalFunds>475000000</TotalFunds>
 </HIT>
 </RESULTSET>
</RESULT>"""


def main():
    items, total = parse_items(SAMPLE_XML)
    print(f"total_count={total}")
    print(f"parsed items={len(items)}")
    assert total == 87122, f"total 파싱 실패: {total}"
    assert len(items) == 1, f"item 개수 파싱 실패: {len(items)}"

    row = items[0]
    checks = {
        "project_number": "1711041912",
        "title_kr": "스마트 센서 응용을 위한 나노 멤브레인 공정 플랫폼 개발",
        "title_en": "Platform development of nano membrane process for smart sensor application",
        "manager": "이종근",
        "keyword_kr": "나노 멤브레인,NEMS,가스 센서, 적외선 센서,공정플랫폼,마이크로 히터",
        "order_agency": "한국연구재단",
        "research_agency": "한국나노기술원",
        "budget_project": "나노·소재기술개발",
        "big_project_title": "선행공정·플랫폼기술연구개발",
        "ministry": "미래창조과학부",
        "project_year": "2016",
        "period_start": "20160701",
        "period_end": "20170630",
        "government_funds": "300000000",
        "total_funds": "475000000",
    }

    all_ok = True
    for key, expected in checks.items():
        actual = row.get(key)
        ok = actual == expected
        all_ok = all_ok and ok
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {key}: {actual!r} (expected {expected!r})")

    if all_ok:
        print("\n✅ 전체 통과 — parse_items()가 매뉴얼 실제 응답 스키마와 일치함")
    else:
        print("\n❌ 일부 실패 — HIT_FIELD_MAP 점검 필요")


if __name__ == "__main__":
    main()
