# Contributing

Thanks for your interest in contributing.

## Development setup

1. Create and activate a virtual environment.
2. Install project dependencies:

```bash
pip install -r requirements.txt
pip install -e .[dev]
```

3. Install git hooks:

```bash
pip install pre-commit
pre-commit install
```

## Quality checks

Run these before opening a pull request:

```bash
ruff check .
mypy backend edge_ml sensor_sim shared
pytest
```

## Pull request expectations

- Keep PRs focused and small.
- Add or update tests for behavior changes.
- Update README.md when introducing user-facing features.
- Include clear reproduction steps for bug fixes.

## Commit style

Use concise, action-oriented commit messages.
Recommended format:

- feat: add room scenario matrix
- fix: accept body-less ACK requests
- docs: update real-audio training section

## Reporting issues

When filing issues, include:

- Environment (OS, Python version)
- Steps to reproduce
- Expected vs actual behavior
- Logs or stack traces
