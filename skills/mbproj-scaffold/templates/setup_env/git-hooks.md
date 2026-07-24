## Git hooks

Hooks are declared in `prek.toml`: the `pre-commit` stage runs `make lint`, the
`commit-msg` stage runs `commitlint`. Activate the shims once per clone:

```bash
make install-hooks
```

`make install-hooks` also works when a global `core.hooksPath` is set (e.g. a
token-tracking hooks directory): it scopes the path to `.git/hooks` for the install,
then restores it so any global delegation keeps running.
