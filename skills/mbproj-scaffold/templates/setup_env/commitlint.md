## commitlint

Validates commit messages against Conventional Commits, run by prek at the
`commit-msg` stage. Node-based (like `markdownlint-cli2`) — install Node.js first
(see [markdownlint-cli2](#markdownlint-cli2)), then:

```bash
npm install -g @commitlint/cli @commitlint/config-conventional
```

The rules live in the versioned `commitlint.config.js`.

Verify:

```bash
commitlint --version
```
