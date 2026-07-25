## Agentic tooling (BMAD + compound-engineering)

Applying the agentic layer installs this tooling automatically (guarded — a re-run is a
no-op). It requires **Node.js 20+**.

**compound-engineering** — a Claude Code plugin, installed at project scope so the whole team
gets it:

```bash
claude plugin marketplace add EveryInc/compound-engineering-plugin --scope project
claude plugin install compound-engineering@compound-engineering-plugin --scope project
```

**BMAD-Method** — the `bmm` module with the Claude Code integration:

```bash
npx --yes bmad-method install --directory . --modules bmm --tools claude-code --yes
```

To upgrade BMAD later, re-run the `npx bmad-method install` command.

If the compound-engineering skills do not appear, the plugin may be installed but disabled —
check the `Status:` line of `claude plugin list`, then:

```bash
claude plugin enable compound-engineering@compound-engineering-plugin
```
