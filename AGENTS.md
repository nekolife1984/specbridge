# specbridge — AI Agent Workflow Guide

> **Documentation-first development.** Every code change MUST be accompanied by corresponding documentation updates in both EN and JA.

## Mandatory Workflow

When making changes to specbridge code, follow this **unbreakable sequence**:

```
1. CODE  → 2. DOCS (EN+JA)  → 3. SKILL (if applicable)  → 4. TEST  → 5. COMMIT
  ↑                                                                       │
  └───────────────────── specbridge drift gate ────────────────────────────┘
```

### Step-by-step

### 1. Before starting
Run `specbridge snapshot --reason "Session: <task>"` to baseline the project state.

### 2. Code changes
Make the implementation changes.

### 3. 📚 Documentation Sync (MANDATORY — DO NOT SKIP)
**Before committing ANY code change**, you MUST update ALL affected documentation:

| Changed area | EN doc | JA doc |
|-------------|--------|--------|
| CLI commands / options | `docs/en/07-cli-commands.md` | `docs/ja/07-cli-commands.md` |
| Output / rendering | `docs/en/08-output-rendering.md` | `docs/ja/08-output-rendering.md` |
| Configuration | `docs/en/09-configuration.md` | `docs/ja/09-configuration.md` |
| Adapter / plugin system | `docs/en/03-adapter-plugin-system.md` | `docs/ja/03-adapter-plugin-system.md` |
| Data model / core | `docs/en/02-data-model.md` | `docs/ja/02-data-model.md` |
| Architecture | `docs/en/01-architecture.md` | `docs/ja/01-architecture.md` |
| CLI help text | `specbridge/cli.py` (docstrings) | — |
| Hermes skill | `.agents/skills/specbridge/SKILL.md` | — |

**Checklist before commit:**
- [ ] EN docs updated for all new/modified features
- [ ] JA docs updated (mirror EN changes)
- [ ] CLI help strings updated (if options/commands changed)
- [ ] Specbridge SKILL.md updated (if Hermes-relevant behavior changed)
- [ ] `specbridge drift --gate` passes (ensures code↔doc traceability)

### 4. Testing
Run the full test suite and mypy:
```bash
pytest tests/ -q
mypy specbridge/ --strict
```

### 5. Commit & push
Use conventional commits format. Reference issues in the commit message.

---

## Convention

- Commit messages: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` prefix
- Issue references in commit body: `#123`
- One change per commit (atomic commits)
- All commits must pass `specbridge drift --gate`
