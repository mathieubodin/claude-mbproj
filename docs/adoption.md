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

## The five classes, and what each one costs

The report separates them because their consequences are not comparable.

| Class | Reported as | What happens if you ignore it |
| --- | --- | --- |
| Hand-written owned file | `overwrite-handwritten` | **The file is replaced.** Content is lost |
| Unwritable path | `blocked` / `unreadable` | Applying dies part-way, leaving the repo half written |
| Tool section already documented | `duplicate` in `SETUP_ENV.md` | `make lint` fails on MD024 |
| Target the socle also defines | `collision` in `Makefile` | make warns; your recipe wins, the generic one is shadowed |
| Prose the imports also carry | `review` in `CLAUDE.md` | Nothing breaks; the project says the same thing twice |

Only the first two are destructive. The other three are editorial: the tool reports them and
stops there, because deciding what to keep in your own Makefile is a judgement call.

## The migration, in the order that works

1. **Owned files first.** For each `overwrite-handwritten` path, decide: does your version say
   something the generic one does not? If yes, move that content somewhere mbproj does not own
   — a project rule file, a section of your `CLAUDE.md`. If no, let it be replaced.
2. **Clear the blocked paths.** A directory sitting where a file belongs, or a file that cannot
   be read: these fail mid-apply, so they have to go before anything else runs.
3. **Strip the superseded sections** from `SETUP_ENV.md`. The managed block will carry them,
   and a duplicated heading fails the lint you are about to generate.
4. **Decide on each colliding target.** Keep yours (the include is anchored first, so it wins),
   delete yours to take the generic one, or — better, when you only need to *add* something —
   use the extension pattern below.
5. **Read the nominated headings** in `CLAUDE.md`. The imported prose may cover what you wrote,
   or complement it. Nobody but you can tell.
6. **Apply.** If you chose to let hand-written files be replaced, pass
   `--acknowledge-conflicts` — that flag records your decision in the manifest, it does not
   suppress the question.
7. **Re-run the preflight.** It should be silent. If it is not, something in step 1–5 was
   missed.

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
generated checks *and* the project's, with no warning. Give `check-dev-env` a recipe of its own
instead, and make answers `warning: overriding recipe for target 'check-dev-env'` while the
generated checks stop running altogether. Both halves are exercised by the check below, the
counter-example included — a test that only confirms the good case would also pass on a make
that never warns.

## Verifying all of it

```bash
python3 skills/mbproj-scaffold/tests/brownfield_check.py
```

It builds a repository carrying all five conflict classes, asserts the report names each one,
asserts the engine refuses to write, and checks the extension pattern against `make -n`. The
fixture is generated rather than committed, so it cannot drift from the layer registry it is
written against.
