# Public repository content review — 12 November 2026

**Purpose:** make the public XGBA project README useful to readers while reducing
accidental disclosure of private conversations, personal information, and
unnecessary development-session detail.

## Reader-facing README

The root README now begins, in this order:

1. Plain-language project overview and how external storage differs from GBA RAM.
2. Goals: larger content libraries, eventual ROM patching and editor/emulator tooling.
3. Potential implications, clearly distinguished from completed features.
4. First-person disclosure: *I am developing XGBA with the help of AI for coding and logging purposes.*
5. Preserved R6–R27 verified engineering results, source links, historical context and limitations.

The earlier R24 header is labelled as a historical milestone, not the latest
milestone. The rest of the substantive technical material remains intact.

## Current tracked-tree review

- Enumerated the full current main-branch Git tree and searched the public
  code index for personal names, chat/session markers, prompt-like artifacts,
  common credential formats, plaintext personal contact information and
  other high-confidence leak indicators.
- Reviewed the older automation and operational runbooks. Removed unnecessary
  statements about individual decisions, account spending and conversations.
  Preserved their technical purpose and dated status.
- Reviewed the publicly accessible pull-request descriptions and issue
  descriptions/comments for the same classes of material, then corrected
  exposed historical narration where appropriate without changing CI evidence.
- Added `tools/repository_privacy_audit.py` and its unit tests. The new
  `xgba-public-privacy-audit.yml` workflow scans the entire Git-tracked
  checkout and fails without printing candidate secret values. It also protects
  README heading order and the required AI disclosure.

**Current finding:** no high-confidence chat transcripts, common live-looking
API tokens/private-key blocks, or private contact details were detected in the
scanned **current tracked worktree**. This is a bounded automated check,
**not a guarantee of zero private data in every possible format**.

**Legacy Copilot retirement:** the previously public R1–R6 agent queue,
single-task Porymap pilot, and manual Porymap prompt dispatcher are now removed
from the active source tree along with their task-specific tests and workflows.
The earlier task definitions were development automation instructions, not
personal ChatGPT transcripts. Their historical commits and execution artifacts
remain public until separately addressed.

The independent production game/emulator tests, historical signed evidence and
project AI disclosure have been preserved.

## Limitations: GitHub history is not the current checkout

Cleaning files on a new branch or in `main` does **not** erase them from
earlier public commits, PR versions, release attachments, cached web pages,
forks, external clones, workflow logs or artifacts.

Git commit author/committer metadata can contain email addresses irrespective
of file content. Existing non-no-reply author metadata must be assessed
separately and, if it is private, repaired through a carefully planned Git
history rewrite and GitHub coordination; no history rewrite was attempted.
Avoid placing private contact details into a public `.mailmap` or follow-up
audit report.

Potential credential exposure in history requires immediate credential
rotation independently of any attempted history cleanup. History rewriting
can disrupt commit hashes, open PRs, protected branches, old CI provenance,
existing clones and historical verification links. A routine content-review
PR is not a safe substitute for that operation.

For ongoing protection, prevent accidental credential/personal-data commits
at source and verify new public PR/issue descriptions. The automated workflow
does not currently inspect GitHub API issue/PR metadata or private branch
history; those are separate audit surfaces.

## Technical evidence preserved

Original native game/emulator artifacts, SHA-256 evidence manifests, pinned
source identities and honest "not proven" limitations were not removed or
rewritten to disguise AI usage. The explicit disclosure in the README is the
intended transparent public record of AI assistance.
