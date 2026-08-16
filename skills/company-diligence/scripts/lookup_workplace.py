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
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "http://apis.data.go.kr/B552015/NpsBplcInfoInqireServiceV2"
TIMEOUT = 20

# 인증키 없이 쓰는 경로.
# 공공데이터포털은 같은 데이터를 파일(CSV)로도 공개하며, 파일 다운로드에는 키가 필요 없다.
# 대신 월 1회 갱신되는 한 달치 스냅샷이라 API보다 할 수 있는 일이 적다 (아래 주의 참조).
NPS_FILE_PAGE = "https://www.data.go.kr/data/15083277/fileData.do"
NPS_FILE_DOWNLOAD = "https://www.data.go.kr/cmm/cmm/fileDownload.do"
NPS_CACHE = Path.home() / ".cache" / "job-application-skills" / "nps-workplaces.csv"
NPS_ENCODING = "cp949"
UA = "Mozilla/5.0 (job-application-skills)"

# 국민연금 보험료율. 근로자와 사업주가 절반씩 부담한다.
PENSION_RATE = 0.09

# 이직률을 %로 낼 수 있는 최소 인원.
# 5명 중 2명이 나가면 40%지만 이건 통계가 아니라 개인사다.
# 이 미만이면 비율 대신 실수(實數)만 낸다.
MIN_HEADCOUNT_FOR_RATE = 10

# 국민연금 기준소득월액에는 상한이 있어서, 급여가 아무리 높아도 보험료가 더 오르지 않는다.
# 역산값이 이 선에 가까우면 상한에 걸린 것이므로 실제 급여는 훨씬 높을 수 있다.
# 카카오뱅크로 실측했을 때 역산 약 627만원 대 공개 평균연봉 약 1억(월 850만원 상당)으로
# 큰 차이가 났다. 정확한 상한은 해마다 고시되므로 경고용 근사값만 둔다.
CEILING_WARN = 6_000_000

# 기간별 조회에서 현재 우리가 해석할 줄 아는 필드.
# 이 외의 필드가 응답에 있으면 알려준다 (고지금액 시계열 존재 여부 확인용).
KNOWN_PERIOD_FIELDS = {"dataCrtYm", "nwAcqzrCnt", "lssJnngpCnt"}

JNNG_STATUS = {"1": "등록", "2": "탈퇴"}
STYLE_DIV = {"1": "법인", "2": "개인"}

SIDO = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주",
    "30": "대전", "31": "울산", "36": "세종", "41": "경기", "42": "강원",
    "43": "충북", "44": "충남", "45": "전북", "46": "전남", "47": "경북",
    "48": "경남", "50": "제주", "51": "강원", "52": "전북",
}


def have_key():
    return bool(os.environ.get("ODCLOUD_SERVICE_KEY"))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def nps_download():
    """공공데이터포털에서 국민연금 사업장 CSV를 받는다. 인증키가 필요 없다.

    파일 ID는 갱신될 때마다 바뀌므로 상세 페이지에서 현재 ID를 찾아낸다.
    """
    print("국민연금 사업장 파일을 내려받습니다 (약 110MB, 인증키 불필요)...", file=sys.stderr)
    try:
        page = fetch(NPS_FILE_PAGE).decode("utf-8", errors="replace")
    except Exception as exc:
        print(f"상세 페이지를 열지 못했습니다: {exc}", file=sys.stderr)
        return False

    m = re.search(r"atchFileId=(FILE_[0-9A-Z]+)", page)
    if not m:
        print(
            "다운로드 링크를 찾지 못했습니다. 포털 페이지 구조가 바뀐 것 같습니다.\n"
            f"직접 받으려면: {NPS_FILE_PAGE}",
            file=sys.stderr,
        )
        return False

    url = f"{NPS_FILE_DOWNLOAD}?atchFileId={m.group(1)}&fileDetailSn=1"
    try:
        blob = fetch(url)
    except Exception as exc:
        print(f"내려받기 실패: {exc}", file=sys.stderr)
        return False

    if len(blob) < 1_000_000:
        print("받은 파일이 너무 작습니다. 포털 응답이 예상과 다릅니다.", file=sys.stderr)
        return False

    NPS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    NPS_CACHE.write_bytes(blob)
    print(f"저장 완료: {NPS_CACHE} ({len(blob) // 1024 // 1024}MB)", file=sys.stderr)
    return True


def nps_rows():
    """캐시된 CSV를 한 줄씩 흘려보낸다. 112MB를 통째로 메모리에 올리지 않는다."""
    if not NPS_CACHE.exists() and not nps_download():
        sys.exit(1)
    with open(NPS_CACHE, encoding=NPS_ENCODING, errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def col(row, want):
    """컬럼명에 설명이 붙어 있어서(예: '사업장가입상태코드 1 등록 2 탈퇴') 앞부분으로 찾는다."""
    for k in row:
        if k and k.startswith(want):
            return (row[k] or "").strip()
    return ""


def cmd_file_search(name, rows_limit):
    """파일 모드 검색. 검색과 상세가 한 번에 나온다 (행 하나에 모든 값이 있다)."""
    hits = []
    asof = ""
    for row in nps_rows():
        if name in col(row, "사업장명"):
            hits.append(row)
            asof = asof or col(row, "자료생성년월")
            if len(hits) >= rows_limit:
                break

    if not hits:
        print(f"'{name}' 으로 등록된 사업장을 찾지 못했습니다.")
        print("가입자 3인 미만 법인은 아예 수록되지 않습니다. 규모가 매우 작다는 정보 자체가 신호입니다.")
        return

    print(f"'{name}' 검색 결과 {len(hits)}건 (자료 기준: {asof}, 파일 모드)\n")
    for row in hits:
        status = "탈퇴" if col(row, "사업장가입상태코드") == "2" else "등록"
        cnt = col(row, "가입자수")
        notice = col(row, "당월고지금액")
        print(f"  사업장명: {col(row, '사업장명')}")
        print(f"  상태: {status} / 형태: {'법인' if col(row, '사업장형태구분코드') == '1' else '개인'}")
        print(f"  업종: {col(row, '사업장업종코드명') or '미상'}")
        print(f"  주소: {col(row, '사업장도로명상세주소') or col(row, '사업장지번상세주소') or '미상'}")
        print(f"  사업자등록번호: {col(row, '사업자등록번호')} (앞 6자리만 공개)")
        print(f"  적용일자: {col(row, '적용일자') or '-'}", end="")
        print(f" / 탈퇴일자: {col(row, '탈퇴일자')}" if col(row, "탈퇴일자") else "")
        print(f"  국민연금 가입자 수: {cnt or '미상'}")
        print(f"  이번 달 입사: {col(row, '신규취득자수') or 0}명 / 퇴사: {col(row, '상실가입자수') or 0}명")

        try:
            c, n = int(cnt), int(notice)
            if c > 0 and n > 0:
                est = int(n / c / PENSION_RATE)
                print(f"  1인당 월 고지금액: {n // c:,}원")
                print(f"  추정 평균 기준소득월액: 약 {est:,}원")
                if est >= CEILING_WARN:
                    # 기준소득월액 상한에 걸리면 실제 급여가 아무리 높아도 이 값이 안 올라간다.
                    # 고연봉 회사일수록 오차가 커지므로 숫자를 단독으로 쓰면 안 된다.
                    print("    주의: 이 값은 상한에 가까워 실제 급여보다 크게 낮을 수 있습니다.")
                    print("    고연봉 회사일수록 오차가 커집니다. 하한선으로만 보고,")
                    print("    실제 수준은 채용사이트 연봉 정보로 교차확인하세요.")
                else:
                    print("    주의: 상한과 하한이 있어 고소득 사업장은 과소추정됩니다.")
        except (TypeError, ValueError):
            pass

        if status == "탈퇴":
            print("\n  신호: 사업장이 탈퇴 처리됐습니다. 폐업 또는 휴업 가능성이 높습니다.")
        print()

    print("파일 모드의 한계:")
    print("  이 파일은 한 달치 스냅샷이라 연환산 이직률을 계산할 수 없습니다.")
    print("  위 입퇴사 숫자는 12개월이 아니라 해당 월 1개월분입니다.")
    print("  이직률이 필요하면 ODCLOUD_SERVICE_KEY 를 발급받아 --trend 를 쓰세요.")


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


def current_headcount(seq):
    """이직률 분모로 쓸 현재 가입자 수. 실패하면 None."""
    try:
        items = items_of(call("getDetailInfoSearchV2", {"seq": seq}))
        return int(items[0].get("jnngpCnt")) if items else None
    except (TypeError, ValueError, IndexError):
        return None


def report_metrics(months, headcount):
    """지원자 지표를 계산해 출력한다.

    계산은 여기서만 한다. 리포트 문서는 이 출력을 인용할 뿐 다시 계산하지 않는다
    (references/evidence-grades.md 의 [계산] 등급 규칙).
    분자와 분모를 항상 함께 출력해서 사용자가 직접 검증할 수 있게 한다.
    """
    print("\n지원자 지표")
    print(f"  {'-' * 46}")

    recent12 = months[:12]
    losses = sum(m["loss"] for m in recent12)
    span = len(recent12)

    # 채용 활발도: 최근 6개월 입사자
    recent6 = months[:6]
    gains6 = sum(m["gain"] for m in recent6)
    print(f"  채용 활발도: 최근 {len(recent6)}개월 신규 입사 {gains6}명")
    print(f"    = {' + '.join(str(m['gain']) for m in recent6) or '0'}")

    # 이직률
    if headcount is None:
        print("\n  연환산 이직률: 산출 불가 (현재 가입자 수를 확인하지 못했습니다)")
        return
    if headcount < MIN_HEADCOUNT_FOR_RATE:
        print(f"\n  연환산 이직률: 비율 산출 안 함 (가입자 {headcount}명, "
              f"{MIN_HEADCOUNT_FOR_RATE}명 미만)")
        print(f"    최근 {span}개월 퇴사 {losses}명 / 현재 가입자 {headcount}명 (실수만 표기)")
        print("    소규모 사업장은 1~2명 이동으로 비율이 크게 흔들려 오해를 부릅니다.")
        return

    annualized = losses * (12 / span) if span else 0
    rate = annualized / headcount * 100
    print(f"\n  연환산 이직률: {rate:.0f}%")
    if span == 12:
        print(f"    = 12개월 퇴사 {losses}명 / 현재 가입자 {headcount}명")
    else:
        print(f"    = {span}개월 퇴사 {losses}명 x (12/{span}) / 현재 가입자 {headcount}명")
        print(f"      ({span}개월치만 있어 연환산했습니다)")
    print("    주의: 분모는 기간 평균이 아니라 '현재' 가입자 수입니다.")
    print("    기간 중 인원이 크게 변한 사업장은 이 값이 왜곡됩니다.")


def cmd_trend(seq, rows):
    body = call("getPdAcctoSttusInfoSearchV2", {"seq": seq, "numOfRows": rows})
    items = items_of(body)
    if not items:
        print(f"seq {seq} 의 기간별 현황 정보가 없습니다.")
        return

    # 응답 순서를 신뢰하지 않는다. 최신 월이 앞에 오도록 직접 정렬한다.
    months = sorted(
        (
            {
                "ym": str(it.get("dataCrtYm") or ""),
                "gain": int(it.get("nwAcqzrCnt") or 0),
                "loss": int(it.get("lssJnngpCnt") or 0),
            }
            for it in items
        ),
        key=lambda m: m["ym"],
        reverse=True,
    )

    print(f"seq {seq} 월별 입퇴사 추이 (취득 = 입사, 상실 = 퇴사)\n")
    print(f"  {'자료년월':<10} {'취득':>6} {'상실':>6} {'순증감':>8}")
    print(f"  {'-' * 34}")

    net_total = 0
    negatives = 0
    for m in months:
        net = m["gain"] - m["loss"]
        net_total += net
        if net < 0:
            negatives += 1
        sign = f"+{net}" if net > 0 else str(net)
        print(f"  {m['ym'] or '-':<10} {m['gain']:>6} {m['loss']:>6} {sign:>8}")

    print(f"\n  합계 순증감: {net_total:+d} ({len(months)}개월)")

    report_metrics(months, current_headcount(seq))

    if net_total < 0:
        print("\n  신호: 조회 구간에서 인원이 순감소했습니다.")
        print("  축소 국면일 수 있습니다. 다른 신호와 함께 판단하세요 (references/risk-signals.md)")
    if negatives >= 3:
        print(f"\n  신호: {negatives}개월이 순감소입니다. 지속적 이탈 가능성을 확인하세요.")
    if net_total > 0 and negatives == 0:
        print("\n  조회 구간에서 인원 감소 신호는 없습니다.")

    # 고지금액 시계열이 실제로 오는지 여기서 드러난다.
    # 온다면 '월급 안 밀리나' 조기 경고를 실제로 만들 수 있다 (지금은 불가).
    extra = {k for it in items for k in it} - KNOWN_PERIOD_FIELDS
    if extra:
        print(f"\n  참고: 해석하지 않은 응답 필드가 있습니다: {', '.join(sorted(extra))}")
        print("  고지금액 관련 필드가 보이면 references/public-data-sources.md 를 갱신하세요.")


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
    parser.add_argument(
        "--file",
        action="store_true",
        help="인증키 대신 공공데이터포털 CSV 파일로 조회 (키 없으면 자동 선택)",
    )
    args = parser.parse_args()

    # 키가 없으면 파일 모드로 자동 전환한다. 키 발급은 회원가입과 승인이 필요해서
    # 그 자리에서 끝나지 않지만, 파일은 바로 받을 수 있다.
    use_file = args.file or not have_key()

    if use_file:
        if args.search:
            if not args.file:
                print("ODCLOUD_SERVICE_KEY 가 없어 파일 모드로 조회합니다.\n", file=sys.stderr)
            cmd_file_search(args.search, min(args.rows, 100))
            return 0
        print(
            "--detail 과 --trend 는 인증키가 있어야 합니다.\n"
            "파일 모드에서는 --search 로 회사명을 넣으면 직원 수, 업종, 탈퇴 여부,\n"
            "해당 월 입퇴사까지 한 번에 나옵니다. 월별 추이만 인증키가 필요합니다.",
            file=sys.stderr,
        )
        return 2

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
