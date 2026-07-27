#!/usr/bin/env python3
"""국민연금 가입 사업장 조회.

회사명으로 사업장을 찾아 실제 직원 수, 업종, 등록/탈퇴 상태, 인원 증감 추이를 확인한다.

DART에 없는 비상장 소기업에도 적용되기 때문에, 이 스킬에서 가장 실용적인 데이터소스다.
확인할 수 있는 것:

  - 동명 기업 판별: 주소, 업종, 규모로 후보를 좁힌다
  - 실제 직원 수: 회사가 홈페이지에서 주장하는 규모와 대조
  - 인원 증감 추이: 월별 취득자와 상실자로 축소 국면 탐지
  - 사업장 탈퇴 여부: 탈퇴 처리는 폐업이나 휴업의 강한 신호
  - 평균 소득 추정: 당월 고지금액을 가입자 수로 나눠 역산 (오차 큼, 참고용)

한계:
  - 응답의 사업자등록번호는 앞 6자리뿐이다. 국세청 조회에 필요한 10자리는 여기서 못 얻는다
  - 법인 3인 이상, 개인사업장 10인 이상만 수록된다. 초소형 회사는 아예 안 나온다
  - 자료 생성 시점 기준이라 최신 상태와 며칠에서 몇 주 차이가 날 수 있다

사전 준비:
    1. data.go.kr 회원가입
    2. "국민연금공단_국민연금 가입 사업장 내역" 활용신청
    3. 일반 인증키(Decoding) 를 환경변수로 등록

        export ODCLOUD_SERVICE_KEY="발급받은키"

    (국세청 조회와 같은 키를 쓴다. 공공데이터포털 계정당 인증키는 하나다)

사용법:
    python3 lookup_workplace.py --search "예시테크"
    python3 lookup_workplace.py --detail 12345678
    python3 lookup_workplace.py --trend 12345678
    python3 lookup_workplace.py --search "예시테크" --json
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2"
TIMEOUT = 20

# 국민연금 보험료율. 근로자와 사업주가 절반씩 부담한다.
PENSION_RATE = 0.09

JNNG_STATUS = {"1": "등록", "2": "탈퇴"}
STYLE_DIV = {"1": "법인", "2": "개인"}

SIDO = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주",
    "30": "대전", "31": "울산", "36": "세종", "41": "경기", "42": "강원",
    "43": "충북", "44": "충남", "45": "전북", "46": "전남", "47": "경북",
    "48": "경남", "50": "제주", "51": "강원", "52": "전북",
}


def service_key():
    key = os.environ.get("ODCLOUD_SERVICE_KEY")
    if not key:
        print(
            "ODCLOUD_SERVICE_KEY 환경변수가 없습니다.\n"
            "data.go.kr 에서 '국민연금공단_국민연금 가입 사업장 내역' 활용신청 후\n"
            "일반 인증키(Decoding) 를 등록하세요.\n\n"
            "  export ODCLOUD_SERVICE_KEY=\"발급받은키\"\n\n"
            "키가 없어도 실사는 진행됩니다. 이 검증 단계만 건너뜁니다.",
            file=sys.stderr,
        )
        sys.exit(2)
    return key


def call(operation, params):
    params = {k: v for k, v in params.items() if v is not None}
    params.update({"serviceKey": service_key(), "dataType": "json"})
    url = f"{BASE}/{operation}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        print(f"API 호출 실패 (HTTP {exc.code}): {body}", file=sys.stderr)
        if exc.code in (401, 403):
            print("인증키가 잘못되었거나 활용신청 승인 전일 수 있습니다.", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"네트워크 오류: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 인증 실패 등은 XML 에러 문서로 돌아온다
        print("응답을 JSON으로 해석하지 못했습니다. 원본 일부:", file=sys.stderr)
        print(raw[:500], file=sys.stderr)
        sys.exit(1)

    body = data.get("response", {}).get("body", {})
    header = data.get("response", {}).get("header", {})
    if header.get("resultCode") not in ("00", None):
        print(f"API 오류: {header.get('resultMsg')}", file=sys.stderr)
        sys.exit(1)
    return body


def items_of(body):
    """items 가 dict 하나일 수도 리스트일 수도 있어서 정규화한다."""
    container = body.get("items")
    if not container:
        return []
    raw = container.get("item") if isinstance(container, dict) else container
    if raw is None:
        return []
    return raw if isinstance(raw, list) else [raw]


def region(item):
    code = str(item.get("ldongAddrMgplDgCd") or "")
    return SIDO.get(code[:2], "")


def cmd_search(name, rows):
    body = call("getBassInfoSearchV2", {"wkpl_nm": name, "numOfRows": rows, "pageNo": 1})
    items = items_of(body)
    total = body.get("totalCount", len(items))

    if not items:
        print(
            f"'{name}' 으로 등록된 국민연금 사업장을 찾지 못했습니다.\n\n"
            "가능한 이유:\n"
            "  - 법인 3인 미만이거나 개인사업장 10인 미만이라 수록 대상이 아님\n"
            "  - 등록된 법인명이 검색어와 다름 (브랜드명과 법인명이 다른 경우가 흔함)\n"
            "  - 사업장이 탈퇴 처리됨\n\n"
            "회사 홈페이지 푸터나 이용약관에서 정식 법인명을 확인해 다시 검색하세요."
        )
        return

    print(f"'{name}' 검색 결과 {len(items)}건 (전체 {total}건)\n")
    for it in items:
        status = JNNG_STATUS.get(str(it.get("wkplJnngStcd")), "?")
        style = STYLE_DIV.get(str(it.get("wkplStylDvcd")), "?")
        mark = "  [탈퇴]" if status == "탈퇴" else ""
        print(f"  seq {it.get('seq')}  {it.get('wkplNm')}{mark}")
        print(f"      {region(it)} {it.get('wkplRoadNmDtlAddr') or '주소 미상'}")
        print(f"      {style} / 상태 {status} / 사업자번호 앞 6자리 {it.get('bzowrRgstNo') or '-'}")
        print()

    if len(items) > 1:
        print("동명 사업장이 여러 개입니다. 주소와 규모로 대상을 확정하세요.")
        seqs = " / ".join(str(i.get("seq")) for i in items[:5])
        print(f"각 후보의 직원 수를 보려면 --detail 에 seq 번호를 넣으세요: {seqs}")
    else:
        print(f"상세 정보를 보려면: --detail {items[0].get('seq')}")

    if any(JNNG_STATUS.get(str(i.get("wkplJnngStcd"))) == "탈퇴" for i in items):
        print("\n주의: 탈퇴 처리된 사업장이 포함되어 있습니다.")
        print("사업장 탈퇴는 폐업이나 휴업의 강한 신호입니다. 국세청 사업자상태 조회로 교차확인하세요.")


def cmd_detail(seq):
    body = call("getDetailInfoSearchV2", {"seq": seq})
    items = items_of(body)
    if not items:
        print(f"seq {seq} 에 해당하는 사업장 상세 정보가 없습니다.")
        return
    it = items[0]

    count = it.get("jnngpCnt")
    notice = it.get("crrmmNtcAmt")
    status = JNNG_STATUS.get(str(it.get("wkplJnngStcd")), "?")

    print(f"사업장명: {it.get('wkplNm')}")
    print(f"업종: {it.get('vldtVlKrnNm') or '미상'}")
    print(f"주소: {it.get('wkplRoadNmDtlAddr') or '미상'}")
    print(f"형태: {STYLE_DIV.get(str(it.get('wkplStylDvcd')), '?')} / 상태: {status}")
    print(f"사업장 등록일: {it.get('adptDt') or '-'}")
    if it.get("scsnDt"):
        print(f"사업장 탈퇴일: {it.get('scsnDt')}")
    print(f"국민연금 가입자 수: {count if count is not None else '미상'}")

    flags = []
    if status == "탈퇴":
        flags.append("사업장이 탈퇴 처리됨. 폐업 또는 휴업 가능성이 높음 (차단 신호 후보)")

    try:
        count_i = int(count)
        notice_i = int(str(notice).replace(",", ""))
        if count_i > 0 and notice_i > 0:
            avg = notice_i / count_i / PENSION_RATE
            print(f"\n1인당 월 고지금액: {notice_i // count_i:,}원")
            print(f"추정 평균 기준소득월액: 약 {int(avg):,}원")
            print("  주의: 기준소득월액에는 상한과 하한이 있어 고소득 사업장은 과소추정됩니다.")
            print("  연봉 추정이 아니라 '이 회사 급여 수준이 대략 어느 구간인가' 정도로만 쓰세요.")
    except (TypeError, ValueError):
        pass

    if flags:
        print("\n점등된 신호:")
        for f in flags:
            print(f"  - {f}")

    print(f"\n인원 증감 추이를 보려면: --trend {seq}")


def cmd_trend(seq, rows):
    body = call("getPdAcctoSttusInfoSearchV2", {"seq": seq, "numOfRows": rows})
    items = items_of(body)
    if not items:
        print(f"seq {seq} 의 기간별 현황 정보가 없습니다.")
        return

    print(f"seq {seq} 월별 입퇴사 추이 (취득 = 입사, 상실 = 퇴사)\n")
    print(f"  {'자료년월':<10} {'취득':>6} {'상실':>6} {'순증감':>8}")
    print(f"  {'-' * 34}")

    net_total = 0
    negatives = 0
    for it in items:
        ym = str(it.get("dataCrtYm") or "-")
        gain = int(it.get("nwAcqzrCnt") or 0)
        loss = int(it.get("lssJnngpCnt") or 0)
        net = gain - loss
        net_total += net
        if net < 0:
            negatives += 1
        sign = f"+{net}" if net > 0 else str(net)
        print(f"  {ym:<10} {gain:>6} {loss:>6} {sign:>8}")

    print(f"\n  합계 순증감: {net_total:+d} ({len(items)}개월)")

    if net_total < 0:
        print("\n  신호: 조회 구간에서 인원이 순감소했습니다.")
        print("  축소 국면일 수 있습니다. 다른 신호와 함께 판단하세요 (references/risk-signals.md)")
    if negatives >= 3:
        print(f"\n  신호: {negatives}개월이 순감소입니다. 지속적 이탈 가능성을 확인하세요.")
    if net_total > 0 and negatives == 0:
        print("\n  조회 구간에서 인원 감소 신호는 없습니다.")


def main():
    parser = argparse.ArgumentParser(
        description="국민연금 가입 사업장 조회 (회사명으로 실제 직원 수와 인원 추이 확인)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--search", metavar="회사명", help="사업장명으로 검색")
    group.add_argument("--detail", metavar="SEQ", type=int, help="사업장 상세 정보")
    group.add_argument("--trend", metavar="SEQ", type=int, help="월별 인원 증감 추이")
    parser.add_argument("--rows", type=int, default=20, help="가져올 결과 수 (기본 20, 최대 100)")
    parser.add_argument("--json", action="store_true", help="원본 JSON 출력")
    args = parser.parse_args()

    if args.json:
        if args.search:
            body = call("getBassInfoSearchV2", {"wkpl_nm": args.search, "numOfRows": args.rows})
        elif args.detail:
            body = call("getDetailInfoSearchV2", {"seq": args.detail})
        else:
            body = call("getPdAcctoSttusInfoSearchV2", {"seq": args.trend, "numOfRows": args.rows})
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0

    if args.search:
        cmd_search(args.search, min(args.rows, 100))
    elif args.detail:
        cmd_detail(args.detail)
    else:
        cmd_trend(args.trend, min(args.rows, 100))
    return 0


if __name__ == "__main__":
    sys.exit(main())
