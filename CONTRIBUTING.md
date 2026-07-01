# Contributing to Ethic Companion

Thanks for considering a contribution. Before opening a PR, please read this
file — it's short, and the parts about the Ethical Safeguard Layer are
non-negotiable.

## The one architectural invariant

**The Ethical Safeguard Layer (ESL) is mandatory.** Every user-facing action
must pass through `esl.evaluate_action()`. Changes that bypass it — even for
"just this one internal case" or "this is just a debug toggle" — will not be
merged.

If you're adding a new tool, a new scheduled job, or any code path that ends
in something the user sees, your PR must:

1. Show the ESL evaluation call.
2. Include a passing `pytest tests/test_esl.py` run.
3. Handle the `VETOED` case (which means *do nothing*, not "log a warning and
   continue anyway").

The ESL is the entire reason this project exists. We hold a very firm line on it.

## Getting set up

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
docker compose up -d   # Postgres + Weaviate
python main.py

# Frontend
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

If you work in git worktrees, run `scripts/sync-env.sh` once per worktree
to symlink `.env` files back to the primary checkout — otherwise OAuth
credentials drift.

## Before you open a PR

```bash
# Backend
pytest --tb=short -q              # full suite must pass (~440 tests)
black . && flake8 . && mypy .     # formatting + lint + types

# Frontend
npx tsc --noEmit                  # type check must be clean
npm run test
```

## How we work

- **One sprint, one plan file.** Big changes get a `docs/plans/YYYY-MM-DD-*.md`
  before any code is written. Problem → architecture decisions → tasks →
  verification. Look at `docs/plans/` for examples.
- **One commit per task** when implementing a planned sprint. Conventional
  commit prefixes (`feat:`, `fix:`, `chore:`, `docs:`) preferred but not
  required.
- **Tests first for anything that touches the ESL, the orchestrator, or
  retrieval ranking.** These are the load-bearing parts; we keep them tight.
- **No `datetime.utcnow()`.** Use `datetime.now(timezone.utc)`. The codebase
  was swept clean of utcnow; please keep it that way.

## Reporting bugs

Open an issue. Include:

- What you expected
- What actually happened
- Reproduction steps if you have them
- Backend log lines if relevant (`backend/main.py` logs to stdout)

If the bug is a **security issue** — anything that could let someone bypass
the ESL, read another user's data, or extract credentials — please follow
[`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## Pull request flow

1. Branch off `main`.
2. Make your change.
3. Run the verification commands above. All green.
4. Open a PR. Reference the issue or plan doc it addresses.
5. The PR template will ask you a few short questions — answer them honestly,
   especially "does this touch the ESL?"

Maintainers will review for:

- ESL compliance (always)
- Test coverage on new code paths
- Whether the change makes the assistant feel less manipulative, more
  trustworthy, or more useful in a way that respects user boundaries —
  and whether it does so without introducing engagement-bait patterns

Things we will push back on:

- New "notifications" without an ESL gate
- Anything that nudges the user toward longer sessions
- "Just one banner" / FOMO / urgency-manufacturing UX
- Removing tests to make a PR look smaller

## Code of conduct

Be kind. Assume good faith. Disagree about technical decisions all you want,
but don't make it personal. Especially in a project framed around ethics, the
maintainers will weigh tone heavily — both ours and yours.

## License

By contributing, you agree your contributions are licensed under
[Apache 2.0](LICENSE).
