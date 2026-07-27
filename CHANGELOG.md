# 변경 이력

이 저장소는 스킬 4개를 하나의 파이프라인으로 묶어 배포하므로 **저장소 단위로 버전을 매깁니다.**
스킬별로 버전이 갈리지 않습니다. 자세한 규칙은 [VERSIONING.md](VERSIONING.md)를 보세요.

형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고,
버전은 [유의적 버전](https://semver.org/lang/ko/)을 따릅니다.

각 항목은 "무엇을 고쳤나"가 아니라 **"내 결과물이 어떻게 달라지나"** 기준으로 적습니다.

## [0.2.0](https://github.com/useful-skills/job-application-skills/compare/v0.1.0...v0.2.0) (2026-07-27)


### Features

* release-please 기반 CHANGELOG/버전 자동화 CI 도입 ([d28992a](https://github.com/useful-skills/job-application-skills/commit/d28992a6ecdf346c08e937936ae6a727d2a27c17))
* 채용 지원 4단계 Agent Skills 파이프라인 초기 구성 ([40eb715](https://github.com/useful-skills/job-application-skills/commit/40eb715fdb33e9720267b8f70419ebdc4bd3d146))


### Bug Fixes

* release-please 첫 릴리스가 1.0.0으로 튀는 문제 수정 ([5c83956](https://github.com/useful-skills/job-application-skills/commit/5c83956299f58c12f8345e4860b2755d04c7d09a))
* release-please가 config 파일을 완전히 무시하던 근본 원인 수정 ([bc8734d](https://github.com/useful-skills/job-application-skills/commit/bc8734d585f6f2ea0e090a9308653ed93b886e80))

## [Unreleased]

### 문서
- 공공 API 키를 "선택"이 아니라 사실상 필수로 명시했습니다.
  키가 없으면 폐업 여부, 실제 직원 수, 재무 상태 확인이 모두 빠져
  판정 근거가 크게 약해진다는 점을 앞부분에서 밝힙니다
- 환경변수와 발급처, 사용 스크립트를 대조한 표를 추가했습니다
  (`ODCLOUD_SERVICE_KEY` 하나가 국세청과 국민연금 두 서비스를 커버한다는 점 포함)
- 셸 설정 파일에 키를 영구 등록하는 방법과, 등록 후 에이전트 재시작이 필요하다는 안내를 추가했습니다

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
