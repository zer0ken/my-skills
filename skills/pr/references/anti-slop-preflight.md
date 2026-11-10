# anti-slop 사전 검사와 커밋 메시지 재작성

한국어 산문 검사(anti-slop)를 CI 에서 처음 만나면 왕복이 반복된다. 검사 범위를 알고 로컬에서 0 건을 만든 뒤 push 한다.

## 검사 대상 범위

PR 이벤트에서 검사기는 다음을 모두 검사한다. 제목이 명사구인지는 검사하지 않으므로 PR 제목은 스킬의 게시 전 확인으로 따로 확인한다.

- PR 제목과 본문
- PR 에 포함된 **커밋 메시지**
- diff 의 **추가된 줄**. 코드 주석과 docstring 을 포함한다

따라서 본문만 고쳐 다시 push 해도 다음 묶음이 걸린다. 커밋 메시지와 주석을 처음부터 함께 검사한다.

## 로컬에서 0 건까지 반복

검사기는 저장소나 action 배포본에 실행 파일로 있다. 이 저장소 계열은 `text` 하위 명령으로 stdin 을 검사한다.

```bash
SLOP=<검사기 실행 파일 경로>

# PR 제목과 본문
"$SLOP" text --label "PR 제목" <<< "$TITLE"
"$SLOP" text --label "PR 본문" < body.md

# diff 의 추가된 줄만
cd <worktree>
git diff origin/main..HEAD -U0 | grep '^+' | grep -v '^+++' | sed 's/^+//' > /tmp/added.txt
"$SLOP" text --label diff < /tmp/added.txt

# 커밋 메시지 전부
for c in $(git rev-list origin/main..HEAD); do
  git log -1 --format=%B "$c" | "$SLOP" text --label "$(git log -1 --format=%h "$c")"
done
```

검사기가 상위 10 여 건만 보고하는 경우가 있다. 한 번에 0 건이 나오지 않으면 고치고 다시 돌린다. 출력의 대체어 후보 가운데 그 문장의 뜻에 맞는 것을 고르고, 후보에 없으면 그 문장이 실제로 수행하는 동작을 서술하는 말로 바꾼다.

## 트리를 보존하는 커밋 메시지 재작성

이미 만든 커밋 메시지만 고치려면 이력을 다시 써야 한다. interactive rebase 는 편집기 상호작용과 충돌로 실패하기 쉬우므로, 각 커밋의 트리를 그대로 읽어 새 메시지로 다시 커밋한다. 코드 내용이 바뀌지 않았다는 사실을 트리 hash 로 증명할 수 있다.

```bash
wt=<worktree>
base=origin/main
cd "$wt"
git rev-parse HEAD^{tree} > /tmp/old_tree.txt          # 재작성 전 최종 트리
shas=$(git rev-list --reverse $base..HEAD)
git checkout -q --detach $base
for sha in $shas; do
  export GIT_AUTHOR_NAME="$(git log -1 --format=%an $sha)"
  export GIT_AUTHOR_EMAIL="$(git log -1 --format=%ae $sha)"
  export GIT_AUTHOR_DATE="$(git log -1 --format=%aI $sha)"
  git read-tree -u --reset $sha                        # 인덱스와 작업 트리를 그 커밋 트리로
  git commit -q -F /path/to/message-$sha.txt            # 새 메시지
 done
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE
git branch -f <branch> HEAD && git checkout -q <branch>
git rev-parse HEAD^{tree}                             # /tmp/old_tree.txt 와 같아야 한다
git push --force-with-lease origin <branch>
```

- 재작성 뒤 커밋 메시지와 추가된 줄을 다시 검사해 0 건을 확인한다.
- 트리 hash 가 같으면 코드·시험 내용은 바뀌지 않았다. 이 사실을 사용자에게 보고한다. 커밋 SHA 가 모두 바뀌므로 이력 재작성 사실도 함께 밝힌다.
- `git read-tree` 뒤 `git commit` 이 스테이징 트리 검토를 요구하는 pre-commit 훅을 만나면, 훅이 안내하는 확인 절차(`--review` 로 토큰을 받고 `--confirm <토큰>`)를 트리마다 한 번 수행한다. 토큰은 스테이징 트리에 묶여 있으므로 커밋마다 다시 받아야 한다.

## 흔한 실패

- 본문만 검사하고 push 해서 커밋 메시지로 다시 실패한다.
- 주석과 docstring 을 검사 대상에서 빼먹는다. diff 의 추가 줄에 구어 동사가 있으면 그대로 걸린다.
- 검사기 출력 10 건을 전부로 착각하고 두어 번 더 왕복한다. 로컬에서 0 건이 될 때까지 반복한다.
- 커밋 메시지를 나중에 고치려다 이력을 다시 쓰게 된다. 커밋하기 전에 메시지를 검사한다.
