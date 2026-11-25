# zer0ken/my-skills

Personal agent skills, one source copy per skill under [skills/](skills/). Each skill describes a methodology; each agent runtime decides which of its native features carries it out, so there are no per-agent copies.

## Skills

- [problem-modeling](skills/problem-modeling/SKILL.md) · 문제의 입력·출력·제약과 평가 기준을 정의한다.
- [prior-research](skills/prior-research/SKILL.md) · 논문·표준 구현·저장소 기록에서 선행 해법을 찾고 근거를 대조한다.
- [ds](skills/ds/SKILL.md) · 저장소의 아키텍처를 확인하고 변경할 책임과 통합 지점을 설계한다.
- [pov](skills/pov/SKILL.md) · 제품과 관련 기술을 일곱 전문 분야의 관점에서 조사한다.
- [my-code-plan](skills/my-code-plan/SKILL.md) · 요구사항에서 파일별 변경까지 계획을 트리로 만들고 검사한다.
- [expert-skill](skills/expert-skill/SKILL.md) · 분야별 일차 자료에서 검토 방법을 추출해 전문 스킬을 설계한다.
- [python-expert](skills/python-expert/SKILL.md) · Python의 타입·모듈 경계·예외·자원 수명을 검토한다.
- [sql-expert](skills/sql-expert/SKILL.md) · 데이터 모델·질의·인덱스·실행 계획·트랜잭션을 검토한다.
- [llm-expert](skills/llm-expert/SKILL.md) · LLM 파이프라인의 프롬프트·출력 계약·평가 데이터와 오류를 분석한다.
- [parallel-expert](skills/parallel-expert/SKILL.md) · 병렬 작업의 의존성·동시성·취소·재시도·복구를 검토한다.
- [claude-cookbook](skills/claude-cookbook/SKILL.md) · 주제에 맞는 Anthropic Cookbook 예제와 노트북을 찾는다.
- [openai-cookbook](skills/openai-cookbook/SKILL.md) · 주제에 맞는 OpenAI Cookbook 예제와 노트북을 찾는다.
- [tdd-is-dead](skills/tdd-is-dead/SKILL.md) · 의도와 호출 범위를 확인하고 동작을 검증할 테스트·구현 순서를 정한다.
- [refactor](skills/refactor/SKILL.md) · 기능과 성능을 유지하면서 코드 구조를 단순화한다.
- [issue](skills/issue/SKILL.md) · 문제와 완료 조건을 정리하고 GitHub 이슈를 작성한다.
- [pr](skills/pr/SKILL.md) · PR 작성부터 CI·리뷰·병합까지 진행한다.
- [pr-visual](skills/pr-visual/SKILL.md) · 같은 입력에서 변경 전후 동작을 비교하는 PR 그림을 만든다.
- [prv](skills/prv/SKILL.md) · 구현 전에 계획과 설계를 관점별로 독립 검토한다.
- [rv](skills/rv/SKILL.md) · 코드·설계·PR을 검토하고 근거와 영향 범위를 확인한다.
- [swarm-review](skills/srv/SKILL.md) · 여러 리뷰어가 관점별로 독립 검토한 뒤 결과를 합친다.
- [review-technique](skills/review-technique/SKILL.md) · 리뷰 관점과 각 관점의 검사 절차를 정의한다.
- [response-rv](skills/response-rv/SKILL.md) · 리뷰 지적의 원인을 확인하고 수용 여부·수정·답변을 기록한다.
- [osiri](skills/osiri/SKILL.md) · 명시적으로 호출하면 코드·설계·보고서의 기술적 주장과 증거를 감사한다.
- [report](skills/report/SKILL.md) · 보고 요청에 작업 목적·결정·검증 결과·남은 일을 정리한다.
- [teqr](skills/teqr/SKILL.md) · 명시적으로 호출하면 기술 보고서·런북·실험 기록·검증 계획을 작성한다.
- [jhchoi-style](skills/jhchoi-style/SKILL.md) · 한국어 기술 문서를 논문 형식의 PDF로 작성한다.
- [한국어 기술 문체](skills/sucks/SKILL.md) · 한국어 기술 문장을 중립적인 문어체로 다듬는다.
- [visuals](skills/visuals/SKILL.md) · 차트·도식·UI·슬라이드에 사용자 시각화 규칙을 적용한다.
- [eli5](skills/eli5/SKILL.md) · 주제를 쉬운 말과 그림으로 설명한다.
- [handoff](skills/handoff/SKILL.md) · 다음 세션이 이어갈 수 있도록 목표·결정·현재 상태를 인계 문서에 정리한다.
- [cleanup](skills/cleanup/SKILL.md) · 세션이 만든 자원을 정리하고 재사용할 데이터는 보존한다.

## Install / Update

Clone the repository once and link the skills each agent should load. A link enables a skill for that agent and removing the link disables it.

```bash
git clone https://github.com/zer0ken/my-skills.git ~/.agents/my-skills
ln -s ~/.agents/my-skills/skills/<skill> ~/.agents/skills/<skill>
```

Agents that read `~/.agents/skills` directly (Codex, pi, Hermes) see every linked skill there and use their own per-skill switches to turn one off. Claude Code reads `~/.claude/skills`, so link `~/.claude/skills/<skill>` to the same source to enable it there. Update with `git -C ~/.agents/my-skills pull`.
