# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts
with project-specific meaning. Seeded with core domain vocabulary, then accretes as
ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only,
not a spec or catch-all.

## The scaffolding model

### Layer

An à-la-carte unit of tooling a repository opts into. A layer decides which files are brought,
which tools they assume, and what each shared file receives — nothing outside a layer's
declaration reaches a repository that did not select it.

Layers may depend on one another, and a dependency is enforced rather than assumed: selecting a
layer whose prerequisite is neither selected nor already applied is refused outright rather
than silently repaired.

### Owned file

A file whose entire content belongs to the scaffolder. It is rewritten in full on every run —
that rewrite *is* the update mechanism — and carries a banner saying so. A project that edits
one loses those edits on the next run, by design.

### Shared file

A file the target project also writes to, so the scaffolder may not own it wholesale. It is
only ever *added to*: existing content is never rewritten or removed. This is the promise that
makes adopting an existing repository safe, and the one whose violation is treated as the most
serious class of defect.

### Banner

The generated-do-not-edit marker placed in every owned file. It answers the question the file
tree cannot: whether a file was written by the scaffolder — and may therefore be rewritten
freely — or by a person, in which case rewriting it destroys work. Authorship is decided by
where the banner sits, not merely by whether the text appears somewhere.

### Anchor line

A single self-identifying pointer line placed in a shared file, referring to an owned file that
holds the real content. Reconciling anchors means removing the ones the scaffolder owns and
re-adding the desired set — which is why anything that stops the scaffolder from recognising
its own anchors makes them accumulate on every run.

### Managed block

A delimited region of a shared file that the scaffolder owns and regenerates in full, used
where the file format offers no indirection. Regenerating rather than appending is what keeps
it idempotent: entries that stop applying disappear instead of lingering. Content outside the
delimiters is never touched.

### Manifest

The record of what a repository has adopted — which layers, at which version, with which
parameters — and the single source of truth for a re-run. State lives there rather than being
inferred from the tree, because the tree cannot answer every question: once a hand-written file
has been overwritten it carries the banner and is indistinguishable from one the scaffolder has
always owned.

## Adoption

### Preflight

The report of what applying would do, computed without writing anything, and the gate applying
must pass. It distinguishes what would be *lost* (an owned file written by hand, a path that
cannot be written) from what would merely be *stated twice* (a duplicated section, a colliding
target, prose that overlaps). Only the first kind stops a run.

### Acknowledgement

The maintainer's recorded decision to let the scaffolder overwrite hand-written content. It
covers a loss someone is entitled to accept, and nothing else: a path that cannot be written is
refused whatever the answer, since agreeing to it would not make the write possible. Once given
it stays on record, because the next run can no longer tell that anything was ever at risk.

### Brownfield / greenfield

The two grounds any change to the scaffolder is validated against: a repository that already
carries hand-written equivalents of what the scaffolder brings, and one that carries nothing at
all. They fail in different ways — one loses content, the other produces a tree that fails its
own generated checks — so a change proven on one is not proven.
