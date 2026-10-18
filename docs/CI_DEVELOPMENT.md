# Private Development CI

Proposed on `prep/public-preview`; not merged into protected main. Nothing in
these workflows publishes packages, images, releases, websites or media.

## The Problem

The normalized main branch inherited three required GitHub Actions contexts:

- `Private RC and DCO`
- `qualification / verify`
- `qualification / Full controller reproduction`

The original normal CI disabled the full benchmark and emitted no authorization
context. A new main PR could therefore remain blocked despite passing core tests.
The frozen RC workflow must not become the development branch's dependency.

## Proposed Behavior

Normal branch pushes, PRs and manual runs now first require a private repository
and DCO, then run the existing reusable qualification with `full-benchmark: true`.
The legacy authorization job name stays to satisfy the existing protection
without removing a required check. Its implementation no longer checks the RC ref
or assumes a single contributor's identity.

DCO code is loaded from the trusted PR base or default branch. Contribution
history is checked out separately as data, without persisted credentials,
submodules or LFS; only the trusted checker executes. PRs check base..head;
development branch pushes check current default..head; default-branch pushes
check the event's before..head; manual default-branch runs check the latest
first-parent range. Missing/bad/empty ranges fail, not silently pass.

The separate trusted `pull_request_target` DCO workflow remains unchanged.
It never executes PR source. PR qualification tests GitHub's merge revision;
push qualification tests the branch SHA. Verify both identities rather than
calling a merge-revision run proof of a different source commit.
[GitHub event semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).

All full benchmark shards and independent reproduction remain required, alongside
clean Compose startup, integration/browser/recovery, security, SBOM and license
gates. Tests do not skip merely because a change is documentation-only. This is
deliberately expensive; a future reduced-cost policy needs a separate owner
decision and cannot masquerade as full reproduction.

## Review Boundary

No protection is weakened and no branch is merged automatically. Required review,
stale dismissal, up-to-date status, resolved conversations and no bypass/force push/
deletion remain. The existing three contexts are emitted by the preparation
branch's proposed workflow, so its first PR does not need a temporary protection
exception. Confirm actual emitted job names on hosted PR checks before review.
[GitHub protection semantics](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

After owner-approved merge, new main pushes use this normal path. Until then,
canonical main still has its frozen workflow. Read-only tokens and full-SHA pinned
actions are retained. Artifacts remain private and expire per their retention;
download evidence before expiry. Failed/changed/expired applicability reviews
block the new branch even though the older RC passed.

The private guard intentionally prevents public CI after any future visibility
change. Public operation requires separately reviewed CI/security/artifact policy
before the owner authorizes that change; do not remove the guard during this goal.

## Merge Commit Sign-Off

The normal main push checks every new commit, including a merge or squash commit.
After separate merge approval, its author must retain their own matching
`Signed-off-by: Name <email>` trailer when composing the merge message. Contributor
and coauthor sign-offs must also remain intact. GitHub's default generated message
does not certify DCO on an author's behalf. No merge or history rewrite is performed
by this proposal; failing DCO on main is not waived as a special merge exception.

## Merge History Coverage

The first hosted PR test exposed a coverage mismatch: GitHub's synthetic merge
made 12 available commits, but the previous default patch mode scanned only 11.
History scanning now requests `--all --full-history --diff-merges=first-parent`.
This includes merge-resolution changes while traversing both ancestries; it is
not `--first-parent` traversal. The exact commit-count, nonempty scan, no-error and
no-warning requirements remain unchanged. A real two-parent Git fixture checks
side-branch, mainline and merge-only changes. See
[Git diff formatting](https://git-scm.com/docs/git-log#_diff_formatting) and the
[pinned scanner implementation](https://github.com/gitleaks/gitleaks/blob/v8.30.1/sources/git.go).
Empty/deletion-only histories that cannot establish the required nonempty coverage
still fail closed; no automatic exception is added.
