#!/usr/bin/env python3
"""DART 기업 검색 및 재무 요약.

기업명으로 DART 고유번호(corp_code)를 찾고, 주요계정 재무제표와 최근 공시 목록을 가져온다.

중요: DART 공시 의무는 상장사 또는 외부감사대상 법인에만 적용된다.
      일반 스타트업과 소규모 중소기업은 DART에 아무 데이터가 없는 것이 정상이다.
      조회 실패는 오류가 아니라 "DART 미커버" 라는 하나의 분석 결과다.

사전 준비:
    1. opendart.fss.or.kr 회원가입 후 인증키 신청 (개인은 즉시 발급, 무료)
    2. 환경변수 등록

        export DART_API_KEY="40자리키"

사용법:
    python3 dart_lookup.py --search "카카오"
    python3 dart_lookup.py --corp-code 00258801 --year 2024
    python3 dart_lookup.py --corp-code 00258801 --disclosures 365
"""

import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

BASE = "https://opendart.fss.or.kr/api"
TIMEOUT = 30
CACHE_DIR = Path.home() / ".cache" / "company-diligence"
CORP_CODE_CACHE = CACHE_DIR / "corpCode.xml"

# 사업보고서. 반기 11012, 1분기 11013, 3분기 11014
REPRT_ANNUAL = "11011"

# 재무제표보다 선행하는 위험 신호. 공시 제목에서 탐지한다.
DISCLOSURE_RED_FLAGS = [
    ("감사의견", ["의견거절", "부적정", "한정"]),
    ("감사인 교체", ["감사인의선임", "감사인선임", "회계감사인"]),
    ("정정 공시", ["정정"]),
    ("지배구조 변동", ["최대주주변경", "대표이사변경"]),
    ("자금 조달 압박", ["전환사채", "신주인수권부사채", "교환사채"]),
    ("분쟁", ["소송", "가압류", "채무불이행"]),
]


def api_key():
    key = os.environ.get("DART_API_KEY")
    if not key:
        print(
            "DART_API_KEY 환경변수가 없습니다.\n"
            "opendart.fss.or.kr 에서 인증키를 발급받아 등록하세요 (개인 즉시 발급, 무료).\n\n"
            "  export DART_API_KEY=\"40자리키\"\n\n"
            "키가 없어도 실사는 진행 가능합니다. 비상장 스타트업은 어차피 DART에 데이터가 없습니다.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def fetch(path, params):
    url = f"{BASE}/{path}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
        return resp.read()


def load_corp_codes(key, refresh=False):
    """전체 기업 고유번호 목록을 받아 캐시한다. 파일이 커서 최초 1회만 받는다."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if refresh or not CORP_CODE_CACHE.exists():
        raw = fetch("corpCode.xml", {"crtfc_key": key})
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                name = zf.namelist()[0]
                CORP_CODE_CACHE.write_bytes(zf.read(name))
        except zipfile.BadZipFile:
            # 인증 실패 등은 zip 이 아니라 XML 에러 메시지로 돌아온다
            print(raw.decode("utf-8", errors="replace")[:500], file=sys.stderr)
            sys.exit(1)
    return ET.parse(CORP_CODE_CACHE).getroot()


def search(key, name, refresh=False):
    root = load_corp_codes(key, refresh)
    hits = []
    for item in root.iter("list"):
        corp_name = (item.findtext("corp_name") or "").strip()
        if name in corp_name:
            hits.append(
                {
                    "corp_code": (item.findtext("corp_code") or "").strip(),
                    "corp_name": corp_name,
                    "stock_code": (item.findtext("stock_code") or "").strip(),
                    "modify_date": (item.findtext("modify_date") or "").strip(),
                }
            )
    # 상장사(종목코드 보유)를 위로 올린다
    hits.sort(key=lambda h: (not h["stock_code"], h["corp_name"]))
    return hits


def financials(key, corp_code, year):
    raw = fetch(
        "fnlttSinglAcnt.json",
        {
            "crtfc_key": key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": REPRT_ANNUAL,
        },
    )
    return json.loads(raw.decode("utf-8"))


def disclosures(key, corp_code, bgn_de, end_de):
    raw = fetch(
        "list.json",
        {
            "crtfc_key": key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "end_de": end_de,
            "page_count": "100",
        },
    )
    return json.loads(raw.decode("utf-8"))


def to_num(text):
    if not text or text in ("-", ""):
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def summarize_financials(payload):
    """주요계정에서 부채비율, 유동비율, 자본잠식 여부를 계산한다."""
    if payload.get("status") != "000":
        return None, payload.get("message", "조회 실패")

    # 연결재무제표(CFS) 우선, 없으면 개별(OFS)
    accounts = {}
    for row in payload.get("list", []):
        if row.get("fs_div") not in ("CFS", "OFS"):
            continue
        name = (row.get("account_nm") or "").strip()
        current = to_num(row.get("thstrm_amount"))
        prior = to_num(row.get("frmtrm_amount"))
        # CFS 를 먼저 만나면 그 값을 유지한다
        if name not in accounts or row.get("fs_div") == "CFS":
            accounts[name] = {"current": current, "prior": prior}

    def val(name, field="current"):
        entry = accounts.get(name)
        return entry[field] if entry else None

    equity = val("자본총계")
    liabilities = val("부채총계")
    cur_assets = val("유동자산")
    cur_liab = val("유동부채")
    capital = val("자본금")

    summary = {"raw_accounts": sorted(accounts.keys())}
    flags = []

    if equity is not None and liabilities is not None and equity > 0:
        ratio = liabilities / equity * 100
        summary["부채비율"] = round(ratio, 1)
        if ratio > 200:
            flags.append(f"부채비율 {ratio:.1f}% (200% 초과, 경고 신호)")

    if equity is not None and equity < 0:
        flags.append("완전자본잠식 (자본총계 음수). 차단 신호")
    elif equity is not None and capital is not None and equity < capital:
        flags.append("부분자본잠식 (자본총계가 자본금 미만). 경고 신호")

    if cur_assets is not None and cur_liab is not None and cur_liab > 0:
        cur_ratio = cur_assets / cur_liab * 100
        summary["유동비율"] = round(cur_ratio, 1)
        if cur_ratio < 100:
            flags.append(f"유동비율 {cur_ratio:.1f}% (100% 미만, 단기 지급능력 경고)")

    for label in ("매출액", "영업이익", "당기순이익"):
        entry = accounts.get(label)
        if entry and entry["current"] is not None:
            summary[label] = {"당기": entry["current"], "전기": entry["prior"]}
            if entry["prior"] is not None and entry["current"] < entry["prior"]:
                flags.append(f"{label} 전기 대비 감소")

    summary["flags"] = flags
    return summary, None


def scan_disclosures(payload):
    if payload.get("status") != "000":
        return [], payload.get("message", "조회 실패")
    hits = []
    for row in payload.get("list", []):
        title = row.get("report_nm", "")
        for label, keywords in DISCLOSURE_RED_FLAGS:
            if any(kw in title for kw in keywords):
                hits.append({"category": label, "date": row.get("rcept_dt"), "title": title})
                break
    return hits, None


def main():
    parser = argparse.ArgumentParser(description="DART 기업 검색 및 재무 요약")
    parser.add_argument("--search", help="기업명으로 corp_code 검색")
    parser.add_argument("--corp-code", help="DART 고유번호 8자리")
    parser.add_argument("--year", type=int, help="재무제표 사업연도")
    parser.add_argument("--disclosures", type=int, metavar="DAYS", help="최근 N일 공시 스캔")
    parser.add_argument("--refresh-cache", action="store_true", help="corp_code 캐시 갱신")
    args = parser.parse_args()

    key = api_key()

    if args.search:
        hits = search(key, args.search, args.refresh_cache)
        if not hits:
            print(
                f"'{args.search}' 로 등록된 기업이 DART 에 없습니다.\n"
                "비상장 스타트업이거나 외부감사 대상이 아닌 법인일 가능성이 높습니다.\n"
                "이는 오류가 아니라 'DART 미커버' 라는 분석 결과입니다.\n"
                "SKILL.md Phase 3 의 대체 재무 신호 경로로 진행하세요."
            )
            return 0
        print(f"검색 결과 {len(hits)}건 (상장사 우선 정렬)\n")
        for h in hits[:30]:
            listed = f"상장 {h['stock_code']}" if h["stock_code"] else "비상장"
            print(f"  {h['corp_code']}  {h['corp_name']}  [{listed}]  갱신 {h['modify_date']}")
        if len(hits) > 30:
            print(f"\n  ... 외 {len(hits) - 30}건. 검색어를 더 구체적으로 입력하세요.")
        print("\n동명 기업이 여러 개면 references/disambiguation.md 절차로 대상을 확정하세요.")
        return 0

    if not args.corp_code:
        parser.error("--search 또는 --corp-code 중 하나가 필요합니다")

    if args.year:
        payload = financials(key, args.corp_code, args.year)
        summary, err = summarize_financials(payload)
        if err:
            print(f"{args.year}년 재무제표 조회 실패: {err}")
            print("해당 연도 사업보고서가 없거나 공시 의무 대상이 아닐 수 있습니다.")
        else:
            print(f"=== {args.year}년 주요계정 요약 ===")
            for k, v in summary.items():
                if k in ("flags", "raw_accounts"):
                    continue
                print(f"  {k}: {v}")
            if summary["flags"]:
                print("\n  점등된 신호:")
                for f in summary["flags"]:
                    print(f"    - {f}")
            else:
                print("\n  주요계정 기준 점등 신호 없음")

    if args.disclosures:
        from datetime import date, timedelta

        end = date.today()
        bgn = end - timedelta(days=args.disclosures)
        payload = disclosures(key, args.corp_code, bgn.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        hits, err = scan_disclosures(payload)
        print(f"\n=== 최근 {args.disclosures}일 공시 위험 신호 스캔 ===")
        if err:
            print(f"  조회 실패: {err}")
        elif not hits:
            print("  탐지된 위험 신호 공시 없음")
        else:
            for h in hits:
                print(f"  [{h['category']}] {h['date']}  {h['title']}")
            print("\n  주의: 키워드 매칭 결과이므로 실제 내용은 원문 공시로 확인하세요.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
