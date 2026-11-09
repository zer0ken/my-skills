---
name: issue
description: "이슈를 올린다. 본문은 `- **문제:**` 처럼 항목 이름을 붙인 불릿 한 줄씩으로 문제와 원인 또는 추정과 목표와 계획 중 필요한 것만 담고, 상세 설명은 본문 하단에 배치한다. 한국어 산문에는 sucks 스킬을 반드시 적용한다. 사용자가 /issue 를 호출하거나 이슈를 올리라고 지시할 때 사용한다."
metadata:
  author: hrlee
  version: "1.6.0"
  domain: workflow
  triggers: 이슈, issue, 이슈 올려, 이슈 생성, gh issue create
  role: guardian
  scope: output
  output-format: action
---

# Issue

전역 규칙, 프로젝트 규칙 중 관련된 것을 다시 명시적으로 읽고 작업할 것.

## 선행 조건

Skill 도구로 `sucks` 를 먼저 호출한다. 본문의 한국어 산문 전체에 그 규칙을 적용한다.

## 메타데이터

생성 전에 저장소 규칙과 GitHub의 실제 선택지를 조회한다. `.github/ISSUE_TEMPLATE/`, `CONTRIBUTING`, 저장소별 `AGENTS.md`, 같은 종류의 최근 이슈를 확인하고 `gh label list`, `gh api`, `gh project list`, `gh project field-list` 등으로 유효한 값을 확인한다.

아래 항목을 모두 내부 체크리스트로 만들고 각각을 `값`, `해당 없음`, `사용자 확인 필요`로 판정한다.

- 라벨
- Issue type
- Assignee
- Milestone
- Project 포함 여부
- Project의 편집 가능한 필드

명시적인 요청, 이슈 폼의 기본값, 저장소 규칙, 같은 종류의 최근 이슈 순으로 근거를 사용한다. 적용할 값이 유일하게 정해지지 않으면 생성하기 전에 사용자에게 묻는다. 사용자나 팀의 소유권, 릴리스 일정, 우선순위를 증거 없이 지어내지 않는다. 계산 필드와 읽기 전용 필드는 편집 대상에서 뺀다. 작업 중인 이슈는 작업을 시작하는 즉시 assignee를 확인하고, 기존 assignee를 지우지 않고 사용자 계정을 추가한다.

`gh issue create`가 지원하는 값은 `--label`, `--assignee`, `--milestone`, `--project`로 생성할 때 같이 넘긴다. Issue type은 조직 저장소에서 사용 가능한 type ID를 조회한 뒤 GraphQL `updateIssueIssueType`으로 설정한다. Project 필드는 이슈를 Project에 추가한 뒤 `gh project item-list` 결과의 item ID와 `gh project field-list` 결과의 field ID를 사용해 `gh project item-edit`로 설정한다. 설치된 `gh` 버전의 `--help`를 기준으로 실제 인자를 선택한다.

생성 직후 `gh issue view --json id,url,labels,assignees,milestone,projectItems`로 일반 메타데이터를 다시 읽고, GraphQL로 Issue type을, `gh project item-list`로 Project 필드를 다시 읽는다. 생성 전 체크리스트와 실제 값을 대조하고 누락이 있으면 즉시 보정한 뒤 다시 조회한다. 권한이나 `project` scope 부족으로 설정하지 못한 값은 조용히 빼지 말고 어느 항목이 남았는지 보고한다.

## 독자

독자는 이 저장소에서 함께 일하는 개발자다. 그들이 아는 어휘로 쓰고, 이해하는 데 필요한 최소한의 맥락만 담는다. 이 저장소에 이미 있는 도메인 지식이나 전문 용어는 풀어 쓰지 않고 그대로 쓴다. 프로젝트의 자체 규칙(CONTRIBUTING, README, 저장소별 AGENTS.md, 기존 이슈·PR 형식)을 최우선으로 존중한다. 프로젝트 규칙과 이 스킬의 지침이 어긋나면 프로젝트 규칙을 따른다.

## 본문

아래 템플릿을 채운다. 항목 하나가 불릿 한 줄이고, 그 줄은 한 문장으로 끝낸다. 항목 이름을 `**문제:**` 처럼 굵게 적어 어느 항목인지 드러낸다. 제목을 넣지 않는다.

```
- **문제:** 
- **원인:** 
- **목표:** 
- **계획:** 
```

필요한 항목만 이 순서로 남기고 나머지 줄은 지운다. 한 내용을 두 항목에 나누어 적지 않는다. 한 항목을 두 줄로 늘리지 않는다.

다른 이슈나 PR 을 참조하면(`Refs #12`, 상위 이슈, 관련 PR 등) 그 참조 줄을 본문 맨 위에 두고, 빈 줄을 둔 뒤 항목을 쓴다.

| 항목 | 적는 것 | 쓰는 경우 |
| --- | --- | --- |
| 문제 | 관측된 현상 | 항상 |
| 원인 | 확인한 원인 | 원인을 확인했을 때 |
| 추정 | 원인의 후보 | 원인을 확인하지 못했을 때. 원인을 쓴 경우에는 쓰지 않는다 |
| 목표 | 이슈를 해결해 달성하려는 상태 | 문제 문장에서 자명하지 않을 때 |
| 계획 | 바로 착수할 수 있는 작업 방향 | 원인을 확인했을 때 |

체크박스(`- [ ]`)를 쓰지 않는다. 본문은 이슈를 설명하는 자리이지 진행 상태를 추적하는 자리가 아니다. 하위 작업으로 쪼개야 하면 본문 하단에 쓴다.

원인을 확인하지 못한 경우:

```
- **문제:** 20000건을 동시에 insert 하면 벡터 인덱스 서버가 종료 코드 없이 죽는다
- **추정:** 세그먼트 병합 경로에서 인덱스 락을 잡지 않는 것으로 추정한다
- **목표:** 동시 insert 부하에서 인덱스 서버가 살아남는 것을 목표로 한다
```

원인을 확인한 경우:

```
- **문제:** 20000건을 동시에 insert 하면 벡터 인덱스 서버가 종료 코드 없이 죽는다
- **원인:** 세그먼트 병합 경로가 인덱스 락을 잡지 않아 병합 중인 세그먼트를 다른 스레드가 해제한다
- **계획:** 병합 진입부에서 인덱스 락을 잡고 동시 insert 재현 테스트를 회귀 테스트로 추가한다
```

## 상세

본문의 각 항목은 한 줄로 끝낸다. 재현 절차, 로그, 조사 경과, 추정의 근거, 검토하고 배제한 원인, 계획의 세부 절차처럼 한 줄에 담기지 않는 내용은 전부 본문 하단에 배치한다. 불릿 요약과 구분되도록 빈 줄을 두고 이어 쓴다. 상세를 코멘트로 나누지 않고 본문 하나에 모두 둔다.

## 사용자 대신 쓰는 이슈

사용자가 이슈 작성을 맡기면 본문에는 사용자가 말했거나 정한 요구(문제, 목표, 범위, 조건)만 적는다. 도구 선택, 구현 위치, 시험 종류, 점수 지표, 실행 절차 같은 설계는 담당자의 몫이므로 적지 않고, `계획` 항목은 사용자가 방법을 정했을 때만 쓴다. 사용자가 일반 원칙을 말했으면 알고 있는 구체 사례로 좁히지 않는다. 이슈에 이르기까지 조사한 내용(도구, 근거, 현재 코드의 관련 지점)은 지우지 않고 본문 하단의 `참고` 절에 담아 담당자가 고르게 한다.

## anti-slop 오동작 이슈

anti-slop이 정상 용례를 검출하거나 대체안이 비문이면 문구만 바꿔 통과시키지 않고 `graphai-repository/anti-slop` 저장소에 이슈로 남긴다. 이 이슈 작성은 사용자의 상시 지시이므로, 이슈는 사용자가 말할 때만 만든다는 전역 지침의 예외다. 최소 입력으로 재현하고 의도된 규칙과 오동작을 구분해 적는다. 라벨 `bug`와 Issue type `Bug`를 쓰고, 기존에 닫힌 이슈와 같은 부류면 `Refs #번호`로 잇는다.

## 결정 기록

사용자가 설계나 범위를 결정하면 그 결정을 대화에만 두지 않고 연결된 이슈에 코멘트로도 남긴다. 결정이 본문의 설계나 완료 조건을 바꾸면 본문도 함께 고친다.

```bash
gh issue create --title "<제목>" --body-file body.md
```

본문은 파일로 넘긴다. 인라인 문자열은 여러 줄에서 깨진다.

## 제목

명사구로 쓰고, 같은 저장소의 다른 이슈와 구별되는 식별자를 남긴다. 종결어미와 문장부호를 넣지 않는다.

- 나쁜 예: `20000건 동시 insert 시 벡터 인덱스 서버가 죽는다`
- 좋은 예: `동시 Insert 시 Segfault (Crash 30) 발생`
## Install and Update

PowerShell (Windows):

```powershell
irm https://raw.githubusercontent.com/zer0ken/skills/main/codex/issue/install.ps1 | iex
```

Bash (macOS / Linux / WSL):

```bash
curl -fsSL https://raw.githubusercontent.com/zer0ken/skills/main/codex/issue/install.sh | bash
```

Re-running the command fetches the latest version; install and update are the same command.
