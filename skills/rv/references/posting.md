# rv posting rules

Read this file when approval_scope allows posting a review as a PR review or comment.

The procedure for posting as a PR review or comment is as follows. Post and edit only within the scope allowed by approval_scope.

1. Mention the PR author (the login from `gh pr view --json author`) as `@login` in the first sentence of the result document. The same for follow-up reviews.

2. Before posting, recheck the latest head and PR state, the applicable target conditions, CI and conflict conditions, and new reviews and comments. If the head changed, do not post stale results. If there is a review with a different verdict on the same head, do not post; report the conflicting evidence.

3. Outside code spans, `~` becomes strikethrough on GitHub, so write ranges with a hyphen, as in `R-001-R-006`.

4. If the repository has an anti-slop check, read the latest rules and vocabulary through the connected repository tools and compare the draft. Clean up vocabulary and unnecessary phrases without changing technical meaning, severity, evidence, or verification limits. Do not download or run executables.

5. After posting or editing, wait until all anti-slop runs finish, and check the section for your own comment id in the bot thread comment. If there is no section, there are 0 detections. If there are detections, edit the same comment and check again.

6. Do not fix detections from other authors' comments and changed files; report them.

7. Distinguish GitHub Conversation comments from formal PR Review COMMENT, REQUEST_CHANGES, and APPROVE. Choose the action that fits the allowed posting scope and the repository's verdict criteria, and distinguish confirmed findings that need fixes from non-blocking explanations and questions. Do not submit REQUEST_CHANGES on taste or on presumptions without sufficient grounds. Submit APPROVE only when the approval authority and the needed user confirmation are met. After submitting, re-query the actual review state and commit, and report self-PR review limits and remaining verification conditions as they are. Do not report a general comment as a formal review or completed approval.

8. Match the form of a reply to what it answers and where it sits. A follow-up on a formal review keeps the review document format (`R-001-C`, statuses). A reply to people's prose opinions, questions, or discussion in a conversation is prose, written as one engineer to the others: one paragraph per point saying what changed or why it stands, points named by their topic rather than by IDs, with commits and documents linked inside the sentences and no ID, status, evidence-class, or `file:line` lists. This follows the split in osiri `TECHNICAL_REVIEW_GUIDE.md` between a formal finding review and a GitHub discussion draft; the user's words (2026-11-12): "지금 사람들이 논의하는 자리니까 방금처럼 코드 리뷰에 대한 응답 포멧을 사용하면 안되는 상황이었다."
