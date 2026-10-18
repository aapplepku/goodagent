# Dependency Patches

These are local changes to pinned upstream dependencies, not new upstream releases.
pnpm applies them during installation and binds their content in `pnpm-lock.yaml`.
Both client Docker builds copy this directory before frozen installation. Public
source exports must retain it. A changed patch invalidates deployment review.

## braces 3.0.3

`braces@3.0.3.patch` adds a non-configurable recursion-depth limit of 128 to the
parser and AST/string/array walkers. It also bounds parent-chain traversal. Excess
depth fails with a specific `RangeError` before native stack exhaustion. Escaped
or quoted literal braces are not counted as structural nesting. The parser allows
up to 127 nested syntax containers, leaving room for their leaf nodes in the AST.
Caller-supplied ASTs and internal module entry points are guarded too.
An iterative preflight caps child traversal at 20,000 nodes and rejects cycles,
shared child subtrees and non-string scalar values. It ignores ordinary `parent`
and `prev` backreferences. Non-finite `maxLength` options cannot bypass the
upstream 10,000-character ceiling. Numeric AST counters must remain numbers
(including parser-produced `NaN` counters); range/coercion options reject objects
and arrays before downstream numeric/string conversion. These malformed inputs
fail with deliberate `TypeError`s. Callers still need to handle rejection errors;
the patch does not make an uncaught exception safe for a long-lived process.
These limits are local compatibility choices,
not newly documented upstream guarantees.

This is scoped remediation for
[GHSA-vfj7-8cjw-p6xm / CVE-2026-93687](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
The advisory lists no upstream patched version as of October 16, 2026. The package
version remains 3.0.3, so a version-based scanner will still report the advisory.
Do not hide that output or treat passing regression tests as release qualification.

The patch is not a general glob/regex complexity guarantee. Expansion cardinality,
large numeric ranges, executable JavaScript getters and arbitrary untrusted plugin
code are outside this patch's scope. Existing upstream length/range limits remain.
Next.js's compiled `@vercel/nft` embeds a separate copy: **this pnpm patch does not
change that bundle**. Its production/build reachability and exact-image review
remain separate release requirements.

Run `node --test --test-timeout=10000 tests/dependencies/braces.test.cjs` after a
frozen install. The contract suite runs the same tests, verifies the lock hash,
and checks Docker/public-export inclusion. Regressions cover both client dependency
chains, ordinary globs, nested/unclosed/mixed patterns, direct/cyclic ASTs, cyclic
parent links, wide/shared ASTs and flattening. Caller options cannot disable the
hard limit or trigger recursive array conversion in range helpers. A local Node 22
container run is useful evidence, but it does not
replace rebuilding and qualifying the final application images.

Original code remains under the [upstream MIT license](braces-3.0.3/LICENSE).
The patch includes unchanged upstream context and locally authored guards; it does
not change the repository's Apache-2.0 license. Remove it only after a reviewed
upstream replacement passes equivalent tests and refreshes the exact-artifact scans.
