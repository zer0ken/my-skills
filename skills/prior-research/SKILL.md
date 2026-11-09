---
name: prior-research
description: "Investigate prior work on a topic or the problem at hand (papers, standard implementations, the repository's design and decision records) with iterative search, and leave a search log and an evidence table. Use when the user calls /prior-research, asks for prior work, related papers, or existing solutions, or when known solutions must be found before problem definition or design."
metadata:
  author: hrlee
  version: "1.1.0"
  domain: research
  triggers: 선행 연구, 관련 연구, 논문 조사, 기존 해법 조사, prior work, related work, literature
---

# Prior Research

Find research and records that already dealt with the problem being solved. Do not stop at one or two keyword searches; widen to neighboring fields and better solutions by repeating the search with the academic names obtained from matching literature. The outputs are two: a search log and an evidence table.

## Preconditions

1. Write the problem to investigate in one paragraph as input, output, and constraints. If there is no definition, define it first with the `problem-modeling` skill.
2. Read the project rules and the criteria the user set. Apply the `sucks` skill to Korean prose.

## Source of candidates

Candidates come only from search results. A language model only generates text probabilistically and is not a store that remembers literature, so titles, authors, arXiv numbers, and URLs the model came up with may not exist.

1. Do not start a candidate from a generated title, number, or URL, and do not put them in queries either.
2. Keep a candidate that already started that way only when it was found again by a query that does not contain that name, and cite the search log row that found it again.
3. In reports, do not make the model the subject of memory, as in "a paper I remember" or "research I know". State sources by search log id and URL.

## Iterative search

Write one row to the search log for every search.

1. Search for papers with plausible keywords that express the input, output, and constraints of the problem definition.
2. Find at least one paper in the results that matches the problem being solved. Judge the match by the problem setting in the body (input, output, assumptions), not the abstract.
3. From the matching paper, find and record the academic name of this problem and the names neighboring fields use for the same problem.
4. Search again with those names to find more recent papers, better solutions, surveys, and benchmarks that solved the same problem. If a new name appears, go back to 3.
5. Stop when no new names appear and the same candidates repeat. Write the reason for stopping and the directions not checked in the last row.

Besides papers, also investigate the following as prior work.

1. The repository's design and decision records: related issues, PRs, commits, CHANGELOG, design documents, and the original records of existing measurements. Anchor them to the code first: `git blame -L <start>,<end> <file>` for the last commits that touched the target lines, `git log --follow -p -- <file>` for the full history, PR numbers in merge commit subjects (`(#1234)`), and ticket ids linked from those PRs. Then read the linked issue bodies and review threads, not only the commit messages.
2. Team discussion records the user can reach, such as chat channels and long-form documents, when a decision was made there. Treat them like any other source: quote only text you fetched.
3. Widely used implementations and their documentation.

Record a search that found nothing as its own row with an empty `found`. A documented null result tells the reader that direction was checked; a missing row does not.

## Access and citation

1. For each candidate, fetch the primary source directly (paper text, official repository, standards document). Summary sites, other agents' summaries, and search-result snippets are not primary sources.
2. Record access with the HTTP status, the time fetched, and the sha256 of the response body.
3. Use only quotes that exist, matched as strings against the fetched body. Do not use quotes that could not be matched.
4. Write together the conditions under which the candidate does not hold (`limits`) and what was not confirmed (`unresearched`). Leave neither empty.

## Outputs

The search log is a JSON array, and each element has the following fields.

| Field | Content |
| --- | --- |
| `id` | Search log id (`S01` etc.) |
| `query` | The exact query entered |
| `tool` | Search tool or service |
| `generated` | `true` if the query contains a model-generated name |
| `found` | Array of titles and URLs of literature found |
| `names` | Array of academic names and neighboring-field names obtained from this search |
| `next` | The next query and its reason; in the last row, the reason for stopping |

The evidence table is a JSON array, and each element has `candidate`, `search_id` (the search log id that produced the candidate; it must not be a row whose `generated` is `true`), `url` (primary source), `quote` (a quote of 20 or more characters that exists in the body), `limits`, `unresearched`, `accessed_at`, `http_status`, and `body_sha256`.

In the research narrative, write the path of the iterative search (the first keywords, the names found, the fields widened with those names), the reason for stopping, and the unresearched scope, citing evidence table rows. If another procedure (such as R2 of my-workflow) fixes file names and fields, follow that procedure.
