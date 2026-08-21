# Contributing to Bones

Thank you for helping improve Bones. Keep changes focused, explain their user
impact, and follow the existing Django architecture documented in
[`AGENTS.md`](AGENTS.md), [`docs/architecture.md`](docs/architecture.md), and
[`docs/django_app_guidelines.md`](docs/django_app_guidelines.md).

## Before opening an issue

- Use the bug or feature issue form and search existing issues first.
- Do not disclose vulnerabilities publicly. Follow
  [the security policy](.github/SECURITY.md) instead.
- Include only sanitized examples; never attach credentials, `.env` contents,
  private database records, or identifiable field data.

## Development workflow

1. Branch from the latest `main`; do not commit directly to `main`.
2. Use Python 3.14 and install the locked CI dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --require-hashes -r app\requirements-ci.txt
   ```

3. Make a narrow change that follows the existing app, template, and test
   patterns. SQL Server application tables are unmanaged; use the established
   raw migration approach for production indexes and avoid schema assumptions.
4. Add or update deterministic, offline-safe tests under `app/bones/tests/`.
5. Run the relevant checks from the repository root:

   ```powershell
   $env:DEBUG='0'
   .\.venv\Scripts\python.exe app\manage.py check
   .\.venv\Scripts\python.exe app\manage.py test bones.tests
   .\.venv\Scripts\python.exe -m ruff check --select E9,F63,F7,F82 app
   ```

6. Push the branch and open a pull request using the repository template.

## Dependency updates

Edit `app/requirements.in` for runtime dependencies or
`app/requirements-ci.in` for CI-only tools. Under Python 3.14, regenerate and
commit both hash-locked outputs:

```powershell
Set-Location app
python -m piptools compile --generate-hashes --strip-extras --output-file=requirements.txt requirements.in
python -m piptools compile --allow-unsafe --generate-hashes --strip-extras --output-file=requirements-ci.txt requirements-ci.in
```

CI repeats these commands without upgrading already valid pins and fails when
the generated files differ from the committed lock files.

## Pull requests and commits

- Keep each pull request reviewable and limited to one coherent outcome.
- Describe validation and any behavior that could not be tested locally.
- Keep required checks passing and update the branch when GitHub reports it as
  behind `main`.
- Do not rewrite public or shared history. `main` requires verified signatures
  and linear history, and GitHub merges accepted pull requests by squash only.
- Update user-facing documentation and release notes when behavior or
  deployment requirements change.

By contributing, you agree that your contribution is licensed under the
repository's [MIT License](LICENSE).
