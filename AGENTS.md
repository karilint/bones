# AGENTS.md

Repository-specific instructions for Codex sessions in this repository.

These instructions apply to all work in the Bones Django project unless the user
gives a more specific direct instruction for the current task. Codex loads this
file before coding, so keep it practical and aligned with the current app.

## Source Policy Files

Codex must follow the repository guidance described in:

- `docs/architecture.md`
- `docs/django_app_guidelines.md`

Treat those files as the canonical architecture and coding policy for this
repository. If implementation details conflict, prefer the concrete architecture
already present in the codebase.

## Project Orientation

This is a Django application centered on the `bones` app under `app/bones/`.
The app uses reusable page archetypes and shared partials rather than one-off
templates.

Key areas:

- `app/bones/navigation.py` defines primary navigation sections and lazy URL
  resolution.
- `app/bones/forms.py` contains select2-backed model forms and shared widget
  styling.
- `app/bones/filters.py` contains django-filter definitions and
  `FilteredListViewMixin`.
- `app/bones/views/lists.py` contains the list view archetype via
  `BonesListView`.
- `app/bones/views/detail.py` contains the detail/edit archetype via
  `BonesDetailView`.
- `app/bones/views/master_detail.py` contains master-detail screens and tabbed
  experiences.
- `app/bones/views/dashboard.py` contains dashboard aggregation and quick
  actions.
- `app/bones/views/history.py` contains django-simple-history backed audit
  views.
- `templates/bones/` contains base templates and reusable partials for
  navigation, tables, filters, actions, breadcrumbs, tabs, details, and history.
- `static/bones/css/bones.css` contains project overrides loaded after W3.CSS.
- `app/bones/tests/` contains the automated test suite.

## Default Workflow

For any non-trivial feature, bug fix, refactor, migration, or test change:

1. Read the relevant code and templates before changing anything.
2. Check `docs/architecture.md` and `docs/django_app_guidelines.md` when the
   task touches page structure, styling, navigation, forms, history, or tests.
3. Make a short internal plan for the implementation.
4. Implement narrowly, following existing project patterns.
5. Run the narrowest useful validation commands.
6. Summarize changed files, validation performed, and remaining risks.

For very small requests, Codex may skip writing out a formal plan, but it must
still inspect the relevant code before editing.

## Protected Branch Workflow

The main branch is protected. For changes intended for main:

1. Do not develop, commit, or push directly on main.
2. Create a focused feature or fix branch.
3. Commit only the reviewed files and push that branch.
4. Open a pull request targeting main.
5. Wait for the required "Django checks and tests", "Docker image build and
   tests", "CodeQL", and "Dependency review" status checks to pass, and update
   the branch if GitHub reports it is behind main.
6. Resolve all review conversations before merging.

The repository requires a pull request but does not require an approving review,
so a solo maintainer may merge their own pull request after the required check
passes. Force-pushing to or deleting main is prohibited.

## Windows Local Tooling

This repository is commonly edited from Windows under a Group Policy that may
block Codex's filesystem sandbox helper. If the normal `apply_patch` tool fails
with `CreateProcessWithLogonW 1385`, `CreateProcessAsUserW 1260`, or a message
that the filesystem helper is blocked by policy, do not keep retrying the same
launcher and do not switch to `Set-Content`, `WriteAllText`, Python file writes,
or other direct rewriting commands.

Use the established elevated Codex patch-engine fallback instead:

1. Request escalation for the patch operation.
2. Resolve the installed patch launcher with `Get-Command apply_patch` and read
   its source to obtain the current VS Code extension's `codex.exe` path. Do not
   hard-code the extension version.
3. Invoke that executable with `--codex-run-as-apply-patch`, passing the normal
   `*** Begin Patch` / `*** End Patch` payload as one argument.
4. In PowerShell, normalize the patch to LF, trim trailing newlines, and escape
   literal double quotes before invoking the native executable so the quotes
   survive Windows argument parsing.
5. Keep each patch payload small (preferably under roughly 6,000 characters) to
   avoid Windows command-line truncation. Split larger changes into atomic
   patches with class- or function-specific context.
6. Inspect `git diff` after each split patch. Generic context such as a repeated
   `get_queryset()` or state-widget line can match the wrong class.

The local `.env` may contain a non-numeric deployment value for `DEBUG`. Prefix
local Django validation with `$env:DEBUG='0'` so settings import reliably, for
example `$env:DEBUG='0'; .venv\Scripts\python.exe app\manage.py test ...`.

## Django Architecture Rules

- Prefer existing class-based view archetypes over creating unrelated view
  structures.
- Extend `BonesListView` for collection/index pages with filtering, pagination,
  optimized querysets, table headers, and action buttons.
- Extend `BonesDetailView` for record detail/edit pages that need breadcrumbs,
  inline editing panels, select2-aware forms, and metadata/actions.
- Use `BonesMasterDetailView` and modular tab include templates for pages that
  combine a primary entity with related lists, history, or workflow data.
- Keep dashboard work in `app/bones/views/dashboard.py` and aggregate through
  optimized managers where available.
- Keep history/audit work in `app/bones/views/history.py` and back it with
  django-simple-history historical models.
- Add navigation entries in `app/bones/navigation.py`; links may safely fall
  back to `#` while routes are developed.
- Use managers and queryset optimization (`select_related`, `prefetch_related`)
  where list/detail/master-detail pages traverse related data.
- SQL Server tables are unmanaged. Performance-sensitive indexes should be
  maintained through raw `RunSQL` migrations under `app/bones/migrations/`.

## Template And UI Rules

- Author templates with semantic HTML5 (`header`, `main`, `section`, `article`,
  `aside`, `footer`) and keep the base template responsible for boilerplate.
- `templates/bones/base.html` should load W3.CSS, Font Awesome, select2 assets
  as needed, and project styles.
- Prefer W3.CSS utility classes for layout and responsive behavior before adding
  custom CSS.
- Put project-specific CSS in `static/bones/css/bones.css` or another
  namespaced static stylesheet loaded after W3.CSS.
- Use Font Awesome consistently for actions such as create, edit, navigation,
  filters, and history. Icons that convey meaning need accessible text or labels.
- Extract repeated markup into `templates/bones/partials/` includes instead of
  duplicating tables, filter forms, tabs, action panels, breadcrumbs, or
  navigation blocks.
- Keep tab bodies in dedicated include templates. Standard tab names are concise
  nouns such as Overview, Related Items, and Audit Log.
- Preserve responsive, mobile-first behavior. Navigation, forms, tables, tabs,
  and select2 widgets must remain usable on phone, tablet, laptop, and desktop
  widths.
- Do not introduce unrelated frontend frameworks or large custom styling systems
  when W3.CSS and the existing partials solve the problem.

## Forms, Filters, Select2, And History

- Use Django forms and widgets rather than ad hoc template-only form markup.
- Apply django-select2 to relationship fields that benefit from search or async
  loading. Prefer existing form mixins and widget conventions in
  `app/bones/forms.py`.
- Keep filter behavior in django-filter filter sets and shared filter mixins.
- Filter widgets should follow the existing W3.CSS and select2 styling.
- Views that handle database/configuration errors should follow existing safe
  empty-queryset patterns instead of exposing raw failures to users.
- Register models requiring audit trails with `HistoricalRecords()` and expose
  history under authenticated routes.
- Mark user-facing strings with `gettext` or `gettext_lazy` when adding new
  interface text.

## Testing Policy

When changing Django code, templates, filters, forms, navigation, or history:

- Add or update tests in `app/bones/tests/` when behavior changes.
- Use Django `TestCase`, `Client`, or `RequestFactory` patterns already present
  in the suite.
- Cover both view behavior and template context when adding or changing page
  archetypes.
- Assert important HTML5 structure, W3.CSS classes, Font Awesome icon usage,
  select2 widget integration, and history behavior where those are part of the
  feature.
- Keep tests deterministic and offline-safe. Do not require a live SQL Server
  instance unless the task explicitly concerns live database integration.
- Preserve graceful handling of database outages and configuration errors in
  filters and list views.
- Keep test changes focused on the behavior under test. Do not weaken assertions
  broadly to hide regressions.

## Validation Expectations

Before finishing, run the narrowest useful checks for the task and broaden them
when the change affects shared behavior.

Common commands from the repository root:

- `.venv\Scripts\python.exe app\manage.py test bones.tests`
- `.venv\Scripts\python.exe app\manage.py test bones.tests.<module_or_class>`
- `python -m py_compile app\bones\views\*.py app\bones\*.py`
- `docker compose run --rm test python manage.py test --keepdb bones.tests`

Use the command style that matches the current environment and installed
dependencies. If validation cannot be run locally, say exactly what was not run
and why.

## Scope Control

- Implement only the requested task and directly necessary supporting changes.
- Do not add unrelated cleanup, formatting churn, new dependencies, or broad
  refactors unless they are required for correctness.
- Keep changes consistent with existing module boundaries and page archetypes.
- Prefer narrow, local fixes over global rewrites.
- Do not revert user changes in the working tree unless explicitly asked.

## Priority Order For Decisions

When tradeoffs appear, prefer:

1. Correctness and data integrity.
2. Existing Django and Bones app patterns.
3. Stable tests and deterministic behavior.
4. Accessibility and responsive usability.
5. Narrow implementation scope.
6. Speed.

## Output Expectations

- Be concise and practical.
- Mention files changed, validation performed, and unresolved risks.
- If a task was only partially verifiable locally, say so clearly.
