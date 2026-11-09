---
name: sucks
description: "Style rules for Korean technical documents. Use when writing or editing Korean prose such as READMEs, design documents, issues, PR bodies, slides, and comments. Excludes both translated-English AI document style and choppy blog style, and writes in a neutral technical written style."
metadata:
  author: hrlee
  version: "2.6.0"
  domain: writing
  triggers: 한국어 문서, README, 문체, 말투, 번역투, 산문, 기술 문서, korean prose, doc tone
  role: guardian
  scope: output
  output-format: guidance
---

# sucks - 한국어 기술 문서 문체

The rules below govern Korean prose. Every example is Korean and is kept verbatim, because the rules are about Korean grammar and vocabulary.

## Purpose

Check the style of Korean prose by rules instead of judging it by feel.

A text contains only the minimum content needed to achieve its purpose.

## Scope

Apply to all prose written in Korean.

- READMEs, design documents, specs
- Issues, PR bodies, commit message bodies
- Slide bodies
- Code comments and docstrings

Do not apply to conversational replies sent to the user. Replies follow the plain-style rules of the global CLAUDE.md.

## Two failure modes

The rules below prevent two things. Moving to the opposite extreme after being corrected is a common failure.

| Failure | Symptoms |
| --- | --- |
| 번역투 AI 문서체 (translated-English AI document style) | Inanimate subjects, excessive passives, stacked nouns, emphasis constructions in English word order |
| 블로그체 (blog style) | Choppy short sentences, colloquial verbs, second-person commands, rhetorical openings |

The goal is not something between the two but neither: a neutral technical written style (중립 기술 문어체). It calls the actor by name, describes actions with technical predicates, and keeps the writer's voice out of the sentences.

## Titles

**A title is a name, not a sentence.** A title is a noun phrase that points to what the section covers. Putting a claim or explanation in the title inverts the relationship in which the section explains the title, so the title summarizes the section. A reader who read the summary loses the reason to read the section.

Do not use sentence endings (`~다`, `~요`, `~습니다`) or predicates, and do not add punctuation (`.`, `!`, `?`).

- 나쁜 예: `캐시를 도입해 응답 속도를 개선했다`, `왜 인덱스가 필요한가?`
- 좋은 예: `캐시 도입과 응답 속도`, `인덱스 필요성`

Apply to document titles, section titles, table of contents entries, and slide titles.

## Sections

Sections also have cohesion and coupling. Cohesion is how completely one section contains one topic, and coupling is how much a section depends on other sections. As in code, raise cohesion and lower coupling.

**One section covers one topic to the end.** If one section contains several topics, the reader must decide for every sentence which topic it belongs to. If one topic is spread over several sections, the reader cannot understand the topic until reading all of them.

- 나쁜 예: 설치 절이 설정 파일 형식을 일부 설명하고, 뒤의 설정 절이 나머지를 설명한다
- 좋은 예: 설치 절은 설치만 다루고, 설정 파일 형식은 설정 절이 전부 다룬다

**A section is understood without reading other sections.** A reader who finished a section must be able to mark the topic as understood and move to the next section. Cross-references take the reader out of the section being read, so minimize them.

**The order of sections is the order in which the reader understands.** Arrange them so each is understood from only what earlier sections established and what the reader knew from the start. Do not order them by the order the writer researched or by the system's internal structure. A section that needs a later section read first is misplaced, so do not patch it with a reference; reorder it or merge the two sections.

## Level of description

The level of description is how closely a text describes its subject. Describing what a technology does and describing which function implements it how are different levels.

**One text keeps one level of description.** The title and first paragraph set the level. If the text drops to a lower level midway, the reader loses the point to connect to the understanding built earlier. A function name or code appearing in a paragraph that introduces a technology means the level dropped.

- 나쁜 예: `git-pptx는 변경된 슬라이드만 diff로 보여줍니다. XML은 태그마다 줄을 나눠 textconv로 넘깁니다`
- 좋은 예: `git-pptx는 변경된 슬라이드만 diff로 보여줍니다. 어떤 슬라이드가 바뀌었는지는 함께 저장한 미리보기 이미지로 확인합니다`

If the level must drop, split the section, and its title announces the new level. Do not drop within one paragraph.

**Do not enumerate cases.** Once a property of a feature is described, the reader supplies the cases that satisfy it. Enumerating cases is one way of dropping the level, and a listed set reads as a specification, so a missing item means it is not supported. Enumerate only when the list really is complete.

- 나쁜 예: `Chrome, Firefox, Safari, Edge에서 접근할 수 있습니다`
- 좋은 예: `브라우저에서 접근할 수 있습니다`

## Lists

**Do not chain items by repeating `와` and `과`.** Attaching a conjunctive particle to every item copies English `and` as is. A Korean enumeration is joined with commas, with `와` or `과` only on the last one. Repeating `이며`, `및`, or `그리고` is the same.

- 나쁜 예: `주어와 목적어와 서술어 차례`
- 좋은 예: `주어, 목적어, 서술어 차례`

**Write enumerations as lists.** Even when enumerating because the list really is complete, do not list items with commas inside a sentence. A list inside a sentence must be reread to count its items, and has no room for the explanation attached to each item.

- 나쁜 예: `설정은 홈 디렉터리, 프로젝트 루트, 실행 인자 순으로 읽습니다`
- 좋은 예: 세 항목을 각각 한 줄로 적고, 읽는 순서는 목록 앞 문장이 밝힌다

**If each item has several attributes, write a table.** If one list line contains several attributes, the reader must find the position of the same attribute in the line again every time items are compared. A table has a fixed column per attribute, so reading down a column completes the comparison.

- 나쁜 예: `- retries: 기본값은 3, 실패한 요청을 다시 보내는 횟수`가 이어지는 목록
- 좋은 예: 설정 이름, 기본값, 설명을 각각 열로 둔 표

If there is only one attribute, use a list. Use a table only when there are two or more columns.

## Sentences

**Do not omit the subject.** The actor of an action is a program and is called by name. A subjectless sentence reads as if the writer performs it directly.

- 나쁜 예: `디렉터리에는 그대로 씁니다`
- 좋은 예: `decomp는 git-pptx 디렉터리에 그대로 저장합니다`

Docstrings are an exception. The subject is fixed as the module, class, or function the docstring is attached to, so it is not written again. However, put a name in a sentence whose actor is not that target. Writing work the target does not perform without a subject reads as work the target performs.

- 나쁜 예: 모듈 docstring에 `분류 결과로 재시도 여부를 정한다` (정하는 것은 호출자다)
- 좋은 예: `재시도 여부는 분류 결과를 받은 쪽이 정한다`

**Keep subject, object, predicate order.** This is the basic order of a Korean declarative sentence. Moving the object forward for emphasis or nesting long adnominal clauses before the subject makes the reader find the subject only at the end of the sentence.

- 나쁜 예: `구조화 출력 API를 지원하지 않는 모델에서 스키마를 YAML로 받으려고 프롬프트에 넣을 템플릿을 렌더하는 함수가 이 모듈에 있다`
- 좋은 예: `이 모듈은 프롬프트에 넣을 YAML 템플릿을 렌더한다. 구조화 출력 API를 지원하지 않는 모델에 쓴다`

When an adnominal clause grows long, split the sentence. Do not nest it before the subject.

**Write declarative sentences that describe one thing.** Do not use permission expressions or second-person commands directed at the reader.

- 나쁜 예: `열어둔 채로 돌려도 됩니다`
- 좋은 예: `편집 중인 상태에서 실행해도 안전합니다`

**Do not use exclamation marks or question marks.** This applies to the body as well as titles. An exclamation mark emphasizes with the writer's voice instead of the sentence's content, and a question mark postpones the answer to the next sentence. If something needs emphasis, state the fact; if there is something to ask, write the answer.

- 나쁜 예: `개선이 아닌 회귀이다!`, `왜 이 값이 필요한가?`
- 좋은 예: `개선이 아니라 회귀다`, `이 값은 재시도 간격을 정한다`

**Do not split one fact into two sentences.** If the next sentence restates what follows from the previous one, the reader reads it expecting new information and finds none. If two sentences point to the same fact, merge them.

- 나쁜 예: `실험을 완료했다. 결과는 기존 주장과 반대다. 개선이 아니라 회귀다`
- 좋은 예: `두 arm을 실행한 결과, 성능은 기존보다 회귀했다`

**Do not write around the point.** Do not build a structure that lays an introduction and answers in the next sentence.

- 나쁜 예: `파트 이름을 정규화하는 이유가 있습니다. 스크립트가 생성한 덱은...`
- 좋은 예: `decomp는 기본적으로 파트 이름을 정규화합니다. 스크립트가 생성한 덱은...`

## Verbs

**Do not use colloquial verbs.** Verbs are the part of speech that slides into blog style while avoiding translated-English style.

The judgment is not a list lookup. For each verb used, check whether a corresponding technical predicate exists, and if it does, replace it. The table below collects frequent ones and is not the whole set to check. Replace verbs not in the table too if a corresponding word exists.

| 구어 | 기술 서술어 |
| --- | --- |
| 난다, 생긴다 | 발생한다 |
| 뗀다 | 제거한다 |
| 부른다 | 호출한다 |
| 쪼갠다 | 분할한다 |
| 담는다 | 포함한다, 정의한다, 저장한다 |
| 준다 | 전달한다, 반환한다 |
| 낸다, 돌려준다 | 반환한다, 출력한다 |
| 본다 | 참조한다, 검사한다 |
| 넣는다 | 삽입한다, 주입한다 |
| 뺀다 | 제외한다, 제거한다, 분리한다 |
| 잡는다 | 검출한다, 포착한다 |
| 돈다 | 실행된다, 순회한다 |
| 띄운다 | 기동한다 |
| 막는다 | 차단한다 |

**The corresponding word differs by meaning.** If one technical predicate is fixed to one colloquial verb, it gets applied to sentences with a different meaning. Check what the sentence actually performs and choose. `가르다` is an example.

| 그 문장에서의 뜻 | 대응어 |
| --- | --- |
| 여럿을 종류별로 나눈다 | 분류한다 |
| 하나를 여러 조각으로 나눈다 | 분할한다 |
| 둘 중 어느 쪽인지 정한다 | 판정한다 |

**If there is no corresponding word, leave it.** Coining a Sino-Korean word by force violates the ban on coinages in the `Words` section below. Replace only verbs for which an established technical predicate exists.

## Words

**Use the domain's terms as they are.** Replacing them is not replacing with easy words but with wrong words.

- 나쁜 예: `미리보기를 그립니다`, `쓰는 법`
- 좋은 예: `미리보기를 렌더합니다`, `사용법`

**Write technical terms in English.** Using English technical terms as is between Korean sentences is allowed. Do not replace English terms with native Korean words. Replacing them turns words the reader knows into words the reader does not know, so it does not get easier. A word translated literally has the same form as an everyday word, so the reader reads it as an everyday word.

- 나쁜 예: `빈 칸짜리 YAML`, `본보기`, `두 팔`(arm), `뜨거운 경로`(hot path), `손 흔들기`(handshake), `함수 몸통`(function body)
- 좋은 예: `placeholder가 든 YAML`, `템플릿`, `두 arm` 또는 `두 조건`, `hot path`, `handshake`, `함수 body` 또는 `함수 바디`

**Do not add Korean names.** Use only the English technical term. Do not write a Korean name together in parentheses. A reader who does not know the term looks it up by that English term. Parenthesized pairs lengthen the sentence and put the burden of judging whether the translation is accurate on the writer.

- 나쁜 예: `deadlock(교착 상태)이 생긴다`, `tombstone(지움 표시)`, `hot path(뜨거운 경로)`
- 좋은 예: `deadlock이 생긴다`, `tombstone`, `hot path`

**Do not make up translations that do not exist.** Do not coin new Korean expressions to use in place of technical terms. A forced translation cannot be searched, and the reader must trace back the original term.

**Avoid transliterations only when a commonly used Korean name exists.** If a word that writes English sounds in Hangul has a widely used Korean name, use that name. If there is no commonly used name, use the English or the transliteration as is.

- 나쁜 예: `불릿으로 분리한다`, `레벨이 내려간다`
- 좋은 예: `목록으로 분리한다`, `서술 수준이 내려간다`

The rules above have one criterion: use the vocabulary developers actually use. That a native Korean word exists in the dictionary is not grounds by itself. `함수 몸통` is in the dictionary but developers do not use it, so write `함수 body` or `함수 바디`.

**Fix wrong words even when the meaning is ambiguous.** Being unable to judge what a word translates and the word currently written being wrong are different problems. Ambiguity is no reason to leave a wrong word. If you cannot judge the original term, quote the phrase, but do not leave the wrong word; propose a word to use instead.

**Do not invent words that are not in the system.** The names for the subject already exist in code and settings. If a noun used is in no identifier, setting value, or type name, the writer made it up. The reader cannot search by that word or confirm in code what it points to.

- 나쁜 예: `구조화 출력을 받아내는 경로`
- 좋은 예: `structured_output_mode가 "yaml"일 때 쓰는 것`

Lumping things under an abstract noun is the same. If what a function returns is one of four strings, it is not a strategy.

- 나쁜 예: `예외를 재시도 전략으로 분류한다`
- 좋은 예: `예외를 분류한다`

**Do not use catch-all nouns.** A noun that can point to anything makes the reader judge again what it is on every reading. If the same word points to a different thing in every sentence, it points to nothing. Use the name of what it points to.

`자리` is the typical one. In one document this word pointed to placement, point, paragraph, item, position, part of speech, and phrase.

| 뭉뚱그린 말 | 가리키는 것의 이름 |
| --- | --- |
| 자리 | 배치, 지점, 문단, 항목, 위치, 구절, 꼴 |
| 부분 | 절, 문단, 항목, 필드 |
| 것 | 값, 파일, 함수, 조건 |
| 내용 | 본문, 값, 설명, 근거 |
| 방식 | 절차, 알고리즘, 형식, 규약 |

This table is not complete either. If a noun used points to different things two or more times in the document, it is a catch-all.

**Use a term after introducing it.** Introduce it at its first appearance and call it by one name from then on. Saying only `디렉터리` does not tell which directory.

**Introduce terms within context.** Do not present the definition first. First show a concrete situation the reader can understand, and name the subject in the sentence where it first appears in that flow. A reader who read the definition first must remember the name without knowing what it is used for. Write the naming sentence in the form `…를 X라고 한다`, with the sentence ending following the style of the whole document. Do not use `부르다`, because the anti-slop check rejects it as a colloquial verb.

- 나쁜 예: `덧셈 연산자는 두 피연산자의 합을 반환하는 이항 연산자다. 예를 들어 1 + 2 는 3 이다`
- 좋은 예: `두 수를 더한다고 가정한다. 이 계산은 1 + 2 로 적고, 가운데의 + 기호를 덧셈 연산자라고 한다`
- 나쁜 예: `Job은 요청 하나의 실행 단위다. Task는 Job 안의 DAG 노드다`
- 좋은 예: `사용자가 문서 8개를 한 번의 요청으로 보낸다고 가정한다. 이 요청 하나를 처리하려고 시스템이 만드는 실행 단위를 Job이라고 한다. Job은 문서마다, chunk마다 따로 실행되는 처리로 나뉘고, 그 처리 하나를 Task라고 한다`

Introduction comes with three conditions.

- One section carries one example situation to the end. If a different example is pulled out for each term, the reader loses the relationships between the terms.
- If the document is split into levels of description such as concept, implementation, and theory, introduce terms in the highest-level section, and lower-level sections only state which identifier the term corresponds to. Do not include code names in the introducing sentence.
- Do not let one everyday word point to different concepts together. If `작업` points to both Job and Task, the reader must judge which one in every sentence. Introduce a concept that exists in code by its code name. If the document newly defines a concept not in code, state when introducing it which code concepts it is the parent of.

**Do not use redundant words.** If words with overlapping meanings are joined, one of the two can be deleted. A template already is a skeleton.

- 나쁜 예: `YAML 골격 템플릿`
- 좋은 예: `YAML 템플릿`

**Do not coin Sino-Korean words.** `재-` attaches only to action nouns that take `-하다`. Since `생성하다` exists, `재생성` is fine; since `번호하다` does not, `재번호` is not.

- 나쁜 예: `관계 ID 재번호는 걸러내지 못합니다`
- 좋은 예: `관계 ID의 번호를 다시 매기는 것은 걸러내지 못합니다`

**Escape `~` in Markdown.** Writing ranges with `~` is fine. GitHub Markdown renders text between two tildes as strikethrough, so outside code spans and code blocks write `~` as `\~`.

- 나쁜 예: `R-001~R-006, 3~5개` (두 `~` 사이가 취소선이 된다)
- 좋은 예: `R-001\~R-006, 3\~5개`

**Do not use metaphors for technical subjects.**

- 나쁜 예: `pptx는 속이 zip입니다`
- 좋은 예: `pptx는 슬라이드마다 XML 파일이 들어 있는 zip입니다`

## Information

**A stated fact must connect to the claim by causality.** Even a true fact, placed in a paragraph where it explains nothing, keeps the reader from moving on. That a file is a zip is not why version control is hard; it is why it can be unzipped.

**Do not use intensifying adverbs.** Words like `완전히`, `전혀`, `매우`, `아주`, `훨씬`, `크게` claim a large degree without measuring it. If the degree matters, write the measurement; if not, delete the adverb. Deleting it does not change whether the sentence is true.

- 나쁜 예: `기존 주장을 완전히 뒤집었다`, `응답이 훨씬 빨라졌다`
- 좋은 예: `기존 주장과 반대다`, `응답 시간이 420ms에서 90ms로 줄었다`

**Do not drop qualifiers.** One qualifier changes whether a sentence is true.

- 나쁜 예: `슬라이드를 렌더한 이미지를 저장합니다` (매번 전체를 렌더한다는 뜻)
- 좋은 예: `변경된 슬라이드를 렌더한 이미지를 저장합니다`

**A limitation item states all four things.** Stating only the symptom leaves the reader unable to judge.

- What it is
- When it occurs
- How it appears
- Whether it can be prevented

- 나쁜 예: `관계 ID 재번호는 걸러내지 못합니다`
- 좋은 예: `관계 ID는 PowerPoint가 다른 도구로 만든 덱을 처음 저장할 때 자기 순서대로 다시 매기는 값입니다. 내용이 같은 슬라이드가 변경으로 검출되지만, 정규화가 여기까지 처리하지 못해 예방할 방법이 없습니다. 두 번째 저장부터는 나타나지 않습니다.`

## Head sentences

The first sentence of a file or module states what the file is, not what is contained in it.

**Do not string together a list of components.** Functions, classes, and constants alike. What is contained is checked in the file. An enumeration of actions joined by conjunctions is a table of contents, so it does not describe identity, and it soon becomes a wrong list as elements grow.

- 나쁜 예: `템플릿을 만들고, 코드 펜스를 제거하고, 실패 원인을 분류한다`
- 좋은 예: `structured_output_mode가 "yaml"일 때 쓰는 스키마 렌더와 응답 파싱`

**Do not write callers.** Callers are confirmed by search, and a hand-written list becomes false when callers change.

- 나쁜 예: `구조화 출력을 쓰는 클라이언트 구현이 이 모듈을 호출한다`

**Write what is not in the code.** A head sentence exists to state what reading the code does not reveal: why this file exists, what it assumes, and what it does not do. A sentence that restates the code loses nothing when deleted.

**Do not repeat what the docstrings of the functions below already state.** The kinds of return values and the parameters are defined by that function's docstring. Moving them to the module head sentence drops the level of description and makes the two places diverge.

**Two or more sentences of the same form with only the noun replaced are wrong.** Such sentences do not describe how each file differs from the others.

- 나쁜 예: 네 파일이 모두 `...endpoint의 요청과 응답 모델을 정의한다`로 끝난다
- 좋은 예: 파일마다 어느 기능의 무엇을 포함하는지가 다르게 적힌다

## Revising

**Revising is not replacing words.** If only words are replaced while the original sentence boundaries stay, overlapping sentences and wrong sentence splits remain. A text whose wrong words were fixed has right words and the original's organization.

When revising, check three things along with the words.

- If two sentences point to the same fact, merge them.
- If one sentence contains several facts, split it.
- If the order of sections differs from the reader's order of understanding, move them.

If the revised text has the same number of sentences as the original, it is likely the organization was not checked. Check whether there is a reason they should be the same.

**Even a text that keeps every rule still has something to delete.** Find and delete sentences whose deletion leaves the purpose intact. Judge whether the purpose stays intact by whether the content of the deleted sentence can be obtained elsewhere. Keep a sentence, even a long one, if it contains something obtainable neither from code nor from other documents. Deleting because it is hard to write properly is not condensing.

## Self-check

After writing prose, check each section and paragraph.

### Organization

1. Is a title a sentence? Replace it with a noun phrase without sentence endings or predicates.
2. Does one section cover only one topic? Gather a scattered topic into one section.
3. Is there a section that needs another section to be understood? Do not add references; reorder or merge.
4. Is the level of description the same in every paragraph? Check whether function names or code are mixed into an introductory paragraph.
5. Does the revised text have the same number of sentences as the original? Check that only words were not replaced.

### Lists

6. Is there a place that enumerates cases? Check whether it can be reduced to one property.
7. Is a remaining enumeration inside a sentence with commas? Split it into a list.
8. Is there an enumeration that repeats `와` or `과`? Join with commas or split into a list.
9. Does one list line contain several attributes? Replace it with a table.

### Sentences

10. Is there a subject? If not, put in the name of who performs the action.
11. Is subject, object, predicate order kept? Are adnominal clauses nested before the subject?
12. Is there an exclamation mark or question mark in the body?
13. Do two sentences point to the same fact? Merge them.

### Verbs

14. Did you check for each verb whether a corresponding technical predicate exists?
15. Does the chosen word fit the meaning in that sentence?

### Words

16. Is there a place where a domain term was replaced with another word?
17. Is there an English technical term replaced with Korean or translated literally? Did you add a Korean name in parentheses after an English term?
18. Is each noun used a word that exists in code or settings? If not, it is made up.
19. Is there a noun used without introduction? Does the introducing sentence come before the context? Does one everyday word point to different concepts in the code together?
20. Does one noun point to different things two or more times in the document? `자리`, `부분`, `것`, `내용`, `방식` especially.
21. Did you join words with overlapping meanings?
22. Is there a coinage made with `재-`, `-화`, or `-성`? Check that it is an existing word.
23. Is there a place that uses `~` in a numeric range?

### Information

24. Does each stated fact connect by causality to the claims right before and after it?
25. Is there an intensifying adverb? Replace it with a measurement or delete it.
26. Is there a sentence that became a broader claim because a qualifier was dropped?
27. If a limitation was written, does it answer all four questions?
28. Can the content of a deleted sentence be obtained from code or other documents?

### Head sentences

29. Is the head sentence a list of components or a list of callers?
