# Adopting mbproj in an existing repository

What a maintainer does when `/mbproj-scaffold` reports conflicts, and how to keep a project's
own tooling alongside the generated socle. Written from adopting the reference project by
hand, where every step below was discovered the hard way.

Greenfield adoption needs none of this: an empty repository has nothing to conflict with, and
the preflight says so in one line.

## The preflight decides whether you have work to do

Run it before applying. It writes nothing:

```bash
python3 "$SKILL_DIR/scripts/mbproj_apply.py" <repo> --layer lint_format --preflight
```

Exit `0` means nothing would be lost — apply and move on. Exit `1` means there is a migration
to do, and the report names every file involved. The engine refuses to write while conflicts
stand, so nothing is at risk while you work through them.

## What the report finds, and what each finding costs

Five of these are the collision classes adopting the reference project hit by hand; the sixth,
an unwritable path, is not a collision but a write that cannot happen. The report separates
them because their consequences are not comparable.

| Class | Reported as | What happens if you ignore it |
| --- | --- | --- |
| Hand-written owned file | `overwrite-handwritten` | **The file is replaced.** Content is lost |
| Unwritable path | `blocked` / `unreadable` | Nothing runs at all: this one cannot be acknowledged |
| Tool section already documented | `duplicate` in `SETUP_ENV.md` | `make lint` fails on MD024 |
| Target the socle also defines | `collision` in `Makefile` | make warns; your recipe wins, the generic one is shadowed |
| Ignore line the block also carries | `duplicate` in `.gitignore` | Nothing at all — git treats a restated pattern as redundant |
| Prose the imports also carry | `review` in `CLAUDE.md` | Nothing breaks; the project says the same thing twice |

Only the first two stop anything. The rest are editorial — the tool reports them and stops
there, because deciding what to keep in your own Makefile is a judgement call — and the
`.gitignore` one is editorial to the point of being optional.

## The migration, in the order that works

1. **Owned files first.** For each `overwrite-handwritten` path, decide: does your version say
   something the generic one does not? If yes, move that content somewhere mbproj does not own
   — a project rule file, a section of your `CLAUDE.md`. If no, let it be replaced.
2. **Clear the blocked paths.** A directory sitting where a file belongs, or a file that cannot
   be read. `--acknowledge-conflicts` does **not** cover these, by design: accepting a loss is
   a decision you are entitled to make, but a path that cannot be written is not a loss to
   accept — saying "go ahead" would only trade a clean refusal for a repo left half written.
3. **Strip the superseded sections** from `SETUP_ENV.md`. The managed block will carry them,
   and a duplicated heading fails the lint you are about to generate.
4. **Decide on each colliding target.** Keep yours (the include is anchored first, so it wins),
   delete yours to take the generic one, or — better, when you only need to *add* something —
   use the extension pattern below.
5. **Read the nominated headings** in `CLAUDE.md`. The imported prose may cover what you wrote,
   or complement it. Nobody but you can tell.
6. **Leave the `.gitignore` duplicates alone**, unless tidiness moves you. They are listed for
   completeness, and cost nothing: git ignores a pattern the same whether it appears once or
   twice. This is the one class you can close by deciding not to act.
7. **Apply.** If you chose to let hand-written files be replaced, pass
   `--acknowledge-conflicts` — that flag records your decision in the manifest, it does not
   suppress the question.
8. **Re-run the preflight.** What must be clear is the **gate**: exit `0`, no
   `overwrite-handwritten`, no `blocked`. The report itself may still carry findings, and on a
   project that extends a generated target it permanently will — the `check-dev-env`
   prerequisite from step 4 is a collision by construction, reported for as long as it exists.
   Expect a quiet gate, not a silent report.

## Extending a generated target without overriding it

The pattern that makes step 4 painless. A project needing one extra check does **not** have to
redefine `check-dev-env`:

```make
include mbproj.mk

check-dev-env: _check_docker
```

That one line is the whole pattern. `_check_docker` is then an ordinary rule of your own,
carrying its command on a tab-indented recipe line as usual.

A rule with prerequisites and **no recipe** *adds* to the target instead of replacing it. Both
the generated checks and yours run, make emits no warning, and the placement relative to the
`include` stops mattering — the ordering rule that governs recipes does not apply here.

Verified by expansion rather than asserted. `make -n check-dev-env` on that form runs the
generated checks *and* the project's, with no warning.

Give `check-dev-env` a recipe of its own instead, and make answers `warning: overriding recipe
for target 'check-dev-env'`. What that costs is narrower than it sounds, and worth stating
precisely: make merges the *prerequisites* of every rule for a target and replaces only the
*recipe*, so the generated checks still run — what is lost is the recipe line itself. The
warning is the real signal, not a broken build. Prefer the prerequisite form anyway: it says
what you mean, and it keeps the report quiet about a collision you did not need to create.

## Verifying all of it

```bash
python3 skills/mbproj-scaffold/tests/brownfield_check.py
```

It builds a repository carrying the five collision classes and asserts the report names each
one, asserts the engine refuses to write and that an unwritable path cannot be acknowledged
past it, and checks the extension pattern against `make -n`. The fixture is generated rather
than committed, so it cannot drift from the layer registry it is written against.

It also pins the parser behaviours directly — every shape that once produced a wrong report
gets its own case, since an end-to-end fixture only proves them for the one shape it happens
to carry.
