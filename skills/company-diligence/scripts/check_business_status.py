#!/usr/bin/env python3
"""국세청 사업자등록상태 조회.

사업자등록번호로 계속사업 / 휴업 / 폐업 여부를 확인한다.
커버리지가 사실상 전 사업자라서, DART에 없는 소규모 스타트업에도 그대로 적용된다.

사전 준비:
    1. data.go.kr 회원가입
    2. "국세청_사업자등록정보 진위확인 및 상태조회" 활용신청
    3. 발급받은 일반 인증키(Decoding) 를 환경변수로 등록

        export ODCLOUD_SERVICE_KEY="발급받은키"

사용법:
    python3 check_business_status.py 1234567890
    python3 check_business_status.py 1234567890 2345678901
    python3 check_business_status.py --json 1234567890
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

API_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"
TIMEOUT = 15

# b_stt_cd 기준 판정. SKILL.md 의 Tier 1 차단 신호와 연결된다.
VERDICT = {
    "01": ("계속사업자", "PASS", "영업 중. 단 이것은 최소 요건일 뿐 재무 건전성 증명이 아님"),
    "02": ("휴업자", "RED", "영업 중단 상태. 급여 지급 주체가 멈춰 있음"),
    "03": ("폐업자", "RED", "법인이 사업을 종료함. 지원 대상이 될 수 없음"),
}


def normalize(b_no: str) -> str:
    """하이픈, 공백 등을 제거해 숫자 10자리로 만든다."""
    digits = re.sub(r"\D", "", b_no)
    if len(digits) != 10:
        raise ValueError(f"사업자등록번호는 숫자 10자리여야 합니다: {b_no!r} -> {digits!r}")
    return digits


def query(b_numbers, service_key):
    payload = json.dumps({"b_no": b_numbers}).encode("utf-8")
    url = f"{API_URL}?serviceKey={urllib.parse.quote(service_key, safe='')}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def render(item):
    b_no = item.get("b_no", "?")
    code = item.get("b_stt_cd", "")
    status = item.get("b_stt") or "조회 결과 없음"
    tax_type = item.get("tax_type", "")
    end_dt = item.get("end_dt", "")

    label, verdict, note = VERDICT.get(
        code,
        (status, "UNKNOWN", "등록되지 않은 번호이거나 조회에 실패했습니다. 번호를 다시 확인하세요"),
    )

    lines = [
        f"사업자등록번호: {b_no}",
        f"상태: {label}",
        f"판정: {verdict}",
    ]
    if tax_type:
        lines.append(f"과세유형: {tax_type}")
    if end_dt:
        lines.append(f"폐업일: {end_dt}")
    lines.append(f"해석: {note}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="국세청 사업자등록상태 조회")
    parser.add_argument("b_no", nargs="+", help="사업자등록번호 (하이픈 포함 가능)")
    parser.add_argument("--json", action="store_true", help="원본 JSON 응답 출력")
    args = parser.parse_args()

    service_key = os.environ.get("ODCLOUD_SERVICE_KEY")
    if not service_key:
        print(
            "ODCLOUD_SERVICE_KEY 환경변수가 없습니다.\n"
            "data.go.kr 에서 '국세청_사업자등록정보 진위확인 및 상태조회' 활용신청 후\n"
            "일반 인증키(Decoding) 를 등록하세요.\n\n"
            "  export ODCLOUD_SERVICE_KEY=\"발급받은키\"\n\n"
            "키 없이도 실사는 진행 가능합니다. 리포트에 '공공데이터 미검증'으로 표기하세요.",
            file=sys.stderr,
        )
        return 2

    try:
        numbers = [normalize(n) for n in args.b_no]
    except ValueError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return 1

    try:
        result = query(numbers, service_key)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"API 호출 실패 (HTTP {exc.code}): {body}", file=sys.stderr)
        if exc.code in (401, 403):
            print("인증키가 잘못되었거나 활용신청 승인이 안 된 상태일 수 있습니다.", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"네트워크 오류: {exc.reason}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    items = result.get("data") or []
    if not items:
        print("조회 결과가 비어 있습니다. 응답 원본:", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print("\n\n".join(render(item) for item in items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
