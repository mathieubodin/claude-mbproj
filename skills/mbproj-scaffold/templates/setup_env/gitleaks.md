## gitleaks

Secret scanner, run by prek at the `pre-commit` stage. Go binary, standalone, no build
step — download the prebuilt release for your platform onto your `PATH`; other options at
<https://github.com/gitleaks/gitleaks#installing>:

```bash
# Linux x86_64 — latest release binary into a directory on your PATH
URL=$(curl -s https://api.github.com/repos/gitleaks/gitleaks/releases/latest \
  | grep -o 'https://[^"]*linux_x64\.tar\.gz' | head -1)
curl -sL "$URL" | tar -xz -C /tmp gitleaks
install -m755 /tmp/gitleaks ~/.local/bin/gitleaks
```

Shortcut on macOS: `brew install gitleaks`.

The hook scans the **staged diff**, not the working tree, so content already committed is
never re-examined: documentation that discusses tokens cannot start failing commits it
already passed. It **blocks** — a secret is the one finding whose cost outlives the commit,
since undoing it means rewriting history *and* rotating the credential.

Three ways to clear a false positive, in order of preference:

1. Append `#gitleaks:allow` to the offending line.
2. Add a rule or an allowlist to `.gitleaks.toml`, **outside** the `mbproj:managed` block —
   what you write there survives re-runs.
3. Record the finding's fingerprint (printed by the hook) in `.gitleaksignore`.

`git commit --no-verify` also works and leaves no trace in the diff, which is exactly why
it is the last resort rather than the first.

The default catalogue carries no rule for every provider; `.gitleaks.toml` is where a
project adds its own `[[rules]]` for the credentials it actually issues.

Verify:

```bash
gitleaks version
```
