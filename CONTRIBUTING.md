# 기여 가이드

## PR 제목 규칙 (필수)

이 저장소는 [Conventional Commits](https://www.conventionalcommits.org/ko/v1.0.0/) 형식의
PR 제목을 요구합니다. CI가 PR 제목을 자동으로 검사하며, 형식이 맞지 않으면 병합할 수 없습니다.

```
<타입>: <설명>
```

예시:
```
feat: 잡플래닛 리뷰 요약 데이터소스 추가
fix: 부채비율 계산에서 자본총계가 0일 때 나누기 오류 수정
docs: company-diligence 판정 기준 설명 보강
```

브랜치 안의 개별 커밋 메시지는 자유롭게 써도 됩니다. 병합은 **squash merge**로 이루어지고,
그때 PR 제목이 최종 커밋 메시지가 되어 [CHANGELOG.md](CHANGELOG.md)에 그대로 반영되기 때문에
PR 제목만 정확하면 됩니다.

## 왜 이 형식을 강제하는가

PR이 병합되면 [release-please](https://github.com/googleapis/release-please)가
커밋 메시지를 읽어 자동으로 CHANGELOG를 쓰고 버전을 올립니다.
타입에 따라 버전이 이렇게 바뀝니다.

| 타입 | 버전 영향 | 예시 |
|---|---|---|
| `feat:` | MINOR | 새 데이터소스, 새 스크립트, 새 스킬 추가 |
| `fix:` | PATCH | 버그 수정, 판정 임계값 미세 조정 |
| `feat!:` 또는 본문에 `BREAKING CHANGE:` | MAJOR | 판정 등급 체계 변경, 리포트 섹션 구조 변경, 스킬 간 산출물 형식 변경 |
| `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `style:` | 버전 변화 없음 | 문서만 수정, 내부 정리 |

버전 정책의 전체 기준은 [VERSIONING.md](VERSIONING.md)를 참고하세요.

## 판정 기준을 바꾸는 PR이라면 (중요)

`skills/company-diligence/references/risk-signals.md`나 `SKILL.md`의 임계값(부채비율 %,
경고 신호 개수 등)을 바꾸는 PR은 타입상 `fix:`(PATCH)로 분류되더라도,
**같은 회사를 다시 조회했을 때 판정 등급이 달라질 수 있습니다.**

이런 변경은 커밋 본문(PR 설명)에 아래처럼 명시해 주세요. release-please가 본문을
CHANGELOG에 그대로 옮기므로, 이 문장이 있어야 사용자가 판정이 바뀔 수 있다는 걸 알 수 있습니다.

```
fix: 부채비율 경고 임계값을 200%에서 180%로 조정

이전에 GREEN이었던 일부 기업이 이 변경 후 AMBER로 판정될 수 있습니다.
```

이 문장을 빠뜨리는 것이 이 저장소에서 가장 조심해야 할 실수입니다.
판정 기준은 사용자의 의사결정에 직접 영향을 주기 때문에, 조용히 바뀌면 안 됩니다.

## 로컬 검증

PR을 올리기 전에 CI가 하는 검증을 미리 돌려볼 수 있습니다.

```bash
# SKILL.md frontmatter, 버전 일관성 검증은 .github/workflows/validate.yml 참고

# 스크립트 컴파일
python3 -m py_compile skills/company-diligence/scripts/*.py
```

이 프로젝트는 EM DASH(U+2014), EN DASH(U+2013) 문자를 쓰지 않습니다.
마침표나 하이픈(-)으로 대신해 주세요. `validate` 워크플로가 이 두 문자의 사용 여부를
자동으로 검사하며, 발견되면 병합이 막힙니다.

## 새 스킬을 추가하는 경우

기존 4개 스킬과 같은 구조를 따라 주세요.

```
skills/{skill-name}/
├── SKILL.md              name, description, metadata(version, repo) frontmatter 필수
├── references/           판단 기준, 상세 절차
└── scripts/               필요한 경우 (표준 라이브러리만 사용 권장)
```

`SKILL.md`의 `name` frontmatter 값은 반드시 폴더명과 같아야 합니다. `validate.yml`이 이걸 검사합니다.

## 리뷰와 병합

모든 PR은 코드 오너([CODEOWNERS](.github/CODEOWNERS))의 승인이 있어야 병합됩니다.
CI(`validate`, `lint-pr-title`)도 통과해야 합니다. 둘 다 자동으로 실행되니 별도 요청은 필요 없습니다.
