## Git hooks

Hooks are declared in `prek.toml`: the `pre-commit` stage runs `make lint`, the
`commit-msg` stage runs `commitlint`. Activate the shims once per clone:

```bash
make install-hooks
```

`make install-hooks` also works when a global `core.hooksPath` is set (e.g. a
token-tracking hooks directory): it scopes the path to `.git/hooks` for the install,
then restores it so any global delegation keeps running.

If you change `prek.toml`, stage it before committing. While the file is modified but
unstaged, prek refuses to run at all — every commit fails with `prek configuration file
is not staged`, whatever the change or the commit message. The commit is rejected, so it
looks like a hook doing its job, while in fact no hook ran.
