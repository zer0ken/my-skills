# anti-slop preflight and commit message rewriting

If you first meet the Korean prose check (anti-slop) in CI, the round trips repeat. Know the check scope, bring it to 0 findings locally, and then push.

## Check target scope

On a PR event the checker checks all of the following. It does not check whether the title is a noun phrase, so check the PR title separately with the skill's pre-posting check.

- The PR title and body
- The **commit messages** included in the PR
- The **added lines** of the diff. This includes code comments and docstrings

So even if you fix only the body and push again, the next bundle is caught. Check the commit messages and comments together from the start.

## Repeat locally until 0 findings

The checker is an executable in the repository or in the action's distribution. This family of repositories checks stdin with the `text` subcommand.

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

The checker sometimes reports only the top 10 or so findings. If you do not get 0 in one run, fix and run again. From the replacement candidates in the output, choose the one that fits the meaning of that sentence, and if none of the candidates fits, change it to wording that describes the action that sentence actually performs.

## Commit message rewriting that preserves the tree

To fix only the commit messages already made, the history must be rewritten. Interactive rebase easily fails from editor interaction and conflicts, so read each commit's tree as it is and commit it again with a new message. The fact that the code content did not change can be proved with the tree hash.

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

- After rewriting, check the commit messages and added lines again and confirm 0 findings.
- If the tree hash is the same, the code and test content did not change. Report this fact to the user. All commit SHAs change, so also state that the history was rewritten.
- If, after `git read-tree`, `git commit` meets a pre-commit hook that requires review of the staged tree, perform the confirmation procedure the hook describes (get a token with `--review` and then `--confirm <token>`) once per tree. The token is bound to the staged tree, so get it again for every commit.

## Common failures

- Checking only the body and pushing, then failing again on the commit messages.
- Leaving comments and docstrings out of the check target. If an added line of the diff has a colloquial verb, it is caught as it is.
- Mistaking the 10 findings the checker printed for all of them and making a couple more round trips. Repeat until it reaches 0 locally.
- Trying to fix commit messages later and ending up rewriting the history. Check the message before committing.
