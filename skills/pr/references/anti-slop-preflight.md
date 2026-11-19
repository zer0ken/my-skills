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

# diff 의 추가된 줄만: 점 세 개는 분기점부터의 diff 로, GitHub 가 PR 에 보이는 범위다
cd <worktree>
git diff origin/main...HEAD -U0 | grep '^+' | grep -v '^+++' | sed 's/^+//' > /tmp/added.txt
"$SLOP" text --label diff < /tmp/added.txt

# 커밋 메시지 전부
for c in $(git rev-list origin/main..HEAD); do
  git log -1 --format=%B "$c" | "$SLOP" text --label "$(git log -1 --format=%h "$c")"
done
```

The checker exits 0 even when it reports findings, so a finding is its output being non-empty, not its exit code: run each check as its own step and read the output before posting or pushing, never chain the check to the post with `&&` (2026-11-18, enterprise-memory #1518: a flagged issue title was posted that way). The checker sometimes reports only the top 10 or so findings. If you do not get 0 in one run, fix and run again. From the replacement candidates in the output, choose the one that fits the meaning of that sentence, and if none of the candidates fits, change it to wording that describes the action that sentence actually performs.

## Commit message rewriting that preserves the PR diff

To fix only the commit messages already made, the history must be rewritten. Interactive rebase easily fails from editor interaction and conflicts, so read each commit's tree as it is and commit it again with a new message, on the same base commit the PR started from.

The base is the branch's fork point, `git merge-base HEAD origin/main`, saved as a SHA before anything else, never `origin/main` itself: a fetch, including one another session runs in the shared repository, moves `origin/main`, and a commit holding the old-base tree on top of the moved main reverts every change main gained since the fork. A tree hash cannot show this, because the tree stays the same while the parent changes; what the rewrite must keep is the PR diff, `git diff $base HEAD`, which `git diff origin/main...HEAD` shows ("git diff A...B is equivalent to git diff $(git merge-base A B) B", git-diff manual, git 2.43.0). The case (2026-11-20, enterprise-memory PR #1545): a squash made with `git reset --soft origin/main` after `origin/main` had moved from d35feca to bcf4023 passed the tree-hash check and turned a 5-file PR into 119 files that would have reverted #1533 and #1544; an independent review caught it. Moving the PR onto a newer main is a rebase, a separate act whose conflicts are resolved and whose tests are run again, not part of a rewrite.

```bash
wt=<worktree>
cd "$wt"
base=$(git merge-base HEAD origin/main)                # PR 의 분기점, 움직이지 않는 SHA
git diff "$base" HEAD | git patch-id --stable > /tmp/old_pr_diff.txt   # 재작성 전 PR diff
shas=$(git rev-list --reverse "$base"..HEAD)
git checkout -q --detach "$base"
for sha in $shas; do
  export GIT_AUTHOR_NAME="$(git log -1 --format=%an $sha)"
  export GIT_AUTHOR_EMAIL="$(git log -1 --format=%ae $sha)"
  export GIT_AUTHOR_DATE="$(git log -1 --format=%aI $sha)"
  git read-tree -u --reset $sha                        # 인덱스와 작업 트리를 그 커밋 트리로
  git commit -q -F /path/to/message-$sha.txt            # 새 메시지
done
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_AUTHOR_DATE
git branch -f <branch> HEAD && git checkout -q <branch>
test "$(git merge-base HEAD origin/main)" = "$base" &&
  git diff "$base" HEAD | git patch-id --stable | cmp - /tmp/old_pr_diff.txt &&
  git diff --stat origin/main...HEAD                   # 재작성 전과 같은 파일 목록이어야 한다
git push --force-with-lease origin <branch>
```

Squashing the PR's commits into one is the same rewrite with one commit: `git reset --soft "$base"` and `git commit`, with `base` saved and checked as above; `git reset --soft origin/main` is the defect of the case.

- After rewriting, check the commit messages and added lines again and confirm 0 findings.
- If the merge-base and the PR diff are the same, the code and test content the PR changes did not change. Report this fact to the user. All commit SHAs change, so also state that the history was rewritten.
- If the check fails, do not push: reset the branch to the old head (`git branch -f <branch> <old head>`) and redo the rewrite from the saved `base`.
- If, after `git read-tree`, `git commit` meets a pre-commit hook that requires review of the staged tree, perform the confirmation procedure the hook describes (get a token with `--review` and then `--confirm <token>`) once per tree. The token is bound to the staged tree, so get it again for every commit.

## Common failures

- Checking only the body and pushing, then failing again on the commit messages.
- Leaving comments and docstrings out of the check target. If an added line of the diff has a colloquial verb, it is caught as it is.
- Mistaking the 10 findings the checker printed for all of them and making a couple more round trips. Repeat until it reaches 0 locally.
- Trying to fix commit messages later and ending up rewriting the history. Check the message before committing.
- Rewriting or squashing onto `origin/main` instead of the saved merge-base, and taking the same tree hash as proof.
