# 변경 이력

이 저장소는 스킬 4개를 하나의 파이프라인으로 묶어 배포하므로 **저장소 단위로 버전을 매깁니다.**
스킬별로 버전이 갈리지 않습니다. 자세한 규칙은 [VERSIONING.md](VERSIONING.md)를 보세요.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고,
버전은 [유의적 버전](https://semver.org/lang/ko/)을 따릅니다.

각 항목은 "무엇을 고쳤나"가 아니라 **"내 결과물이 어떻게 달라지나"** 기준으로 적습니다.

## [0.3.0](https://github.com/useful-skills/job-application-skills/compare/v0.2.0...v0.3.0) (2026-08-16)


### Features

* company-diligence 리포트를 지원자 질문 순서로 재설계 ([#5](https://github.com/useful-skills/job-application-skills/issues/5)) ([edd109a](https://github.com/useful-skills/job-application-skills/commit/edd109aefb9c5b483b2cfb32c8d7f7f75685db4a))
* 인증키 없이도 조회되도록 파일 모드와 dartlab 경로 추가 ([#7](https://github.com/useful-skills/job-application-skills/issues/7)) ([5cb3607](https://github.com/useful-skills/job-application-skills/commit/5cb360739efbf5f76f4ec3141e8aa9c7242d0727))

## [0.2.0](https://github.com/useful-skills/job-application-skills/compare/v0.1.0...v0.2.0) (2026-07-27)


### Features

* release-please 기반 CHANGELOG/버전 자동화 CI 도입 ([d28992a](https://github.com/useful-skills/job-application-skills/commit/d28992a6ecdf346c08e937936ae6a727d2a27c17))
* 채용 지원 4단계 Agent Skills 파이프라인 초기 구성 ([40eb715](https://github.com/useful-skills/job-application-skills/commit/40eb715fdb33e9720267b8f70419ebdc4bd3d146))


### Bug Fixes

* release-please 첫 릴리스가 1.0.0으로 튀는 문제 수정 ([5c83956](https://github.com/useful-skills/job-application-skills/commit/5c83956299f58c12f8345e4860b2755d04c7d09a))
* release-please가 config 파일을 완전히 무시하던 근본 원인 수정 ([bc8734d](https://github.com/useful-skills/job-application-skills/commit/bc8734d585f6f2ea0e090a9308653ed93b886e80))

## [Unreleased]

### 변경 (리포트 내용이 달라집니다)
- **면접 질문에 의존하지 않습니다.** 실무진은 회사 재무를 모르고, 급여 지연 여부를 물어도
  솔직한 답이 나오지 않으며, 무엇보다 면접은 이미 지원한 뒤라 "지원해도 될까"를 판단하기엔
  늦습니다. 이제 **지원 전에 스스로 확인할 방법**을 먼저 알려줍니다
  (근로계약서 급여일 조항, 더브이씨 투자 이력, 최근 후기 등).
  면접 질문은 실무진이 답할 수 있는 팀·직무 단위 2개까지만 남고, 없으면 생략됩니다
- **연봉을 채용공고와 채용사이트 기준으로 말합니다.** 이전에는 국민연금 보험료 역산값을
  주로 썼는데, 상한 때문에 고연봉 회사에서 크게 낮게 나왔습니다(실측: 역산 월 627만원 대
  공개 평균연봉 1억 236만원). 역산값은 이제 "최소 이 정도" 하한선으로만 씁니다
- **안전한 회사와 다닐 만한 회사를 구분해 적습니다.** 재무가 멀쩡해도 후기 평판이 나쁘면
  두 가지를 따로 밝힙니다. 이전에는 "특별히 걱정할 신호 없음" 한 줄로 뭉뚱그려져
  좋은 회사라는 뜻으로 읽힐 수 있었습니다

### 수정 (잘못된 정보가 나가던 문제)
- **채용 공고가 있는데 "0건"으로 나오던 문제를 고쳤습니다.** 검색 결과 요약에 캐시된
  옛날 숫자를 그대로 인용해서, 실제로는 4건이 열려 있는데 "채용 0건"이라고 적고
  "공고가 방치된 건 아닌지 확인하라"는 없는 걱정까지 만들었습니다.
  이제 채용 페이지를 직접 열어 확인하고, 확인이 불완전하면 "확인 못 함"으로 남깁니다
- **검색 결과의 숫자를 그대로 믿지 않습니다.** 채용 건수, 리뷰 수, 평점 같은 수치는
  페이지를 열어 확인하고, 못 열면 아예 쓰지 않습니다
- **같은 이름의 다른 회사가 섞이던 문제를 줄였습니다.** 회사를 특정한 뒤에도 이름만으로
  검색해서 동명 회사 정보가 들어왔습니다. 이제 사업자번호, 소재지, 도메인으로 대조하고,
  후기처럼 대조할 수 없는 정보는 "동명 회사 내용이 섞였을 수 있다"고 밝힙니다
- **은행·보험·증권을 일반 기업 기준으로 판정하지 않습니다.** 예금이 부채로 잡혀
  부채비율이 수백 퍼센트인 것이 정상인데, 기존 기준을 적용하면 건전한 금융회사가
  전부 위험으로 판정됐습니다
- **분기 실적이 띄엄띄엄한 회사에서 추이를 오독하던 문제를 고쳤습니다.** 중간 분기가
  비어 있으면 연속된 분기처럼 보였습니다. 이제 끊긴 구간을 표시합니다

## [0.1.0] - 미공개

첫 공개 준비 버전입니다. 아직 실제 API 응답으로 검증된 사례가 없습니다.

### 추가
- `company-diligence`: 기업 실사 스킬. 공식정보와 비공식정보를 분리 수집하고
  RED / AMBER / GREEN / UNKNOWN 4단계로 판정합니다
- `jd-analyzer`: 채용공고의 추상적 문구를 실제 업무로 역추론합니다
- `application-strategy`: 비즈니스 모델의 병목을 가설로 세우고 지원자 경험과 매칭합니다
- `resume-customizer`: 경험 마스터 데이터에서 공고별로 이력서를 재조립합니다
- 공공데이터 조회 스크립트 3종
  - `check_business_status.py` 국세청 사업자상태 (폐업·휴업 확인)
  - `lookup_workplace.py` 국민연금 사업장 (회사명 검색, 실제 직원 수, 월별 입퇴사 추이)
  - `dart_lookup.py` DART 재무제표와 공시 이상 신호

### 알려진 제약
- 임금체불 명단은 API 자동 조회가 아니라 웹 조회입니다. 결과가 일정하지 않을 수 있습니다
- 국민연금 API는 사업자등록번호를 앞 6자리만 제공합니다. 국세청 조회에 필요한 10자리는 별도로 찾아야 합니다
- 국민연금 데이터는 법인 3인 미만 사업장을 수록하지 않습니다
- 스크립트 파싱 로직은 모의 응답으로 검증했습니다. 실 데이터 검증 사례가 아직 없습니다
