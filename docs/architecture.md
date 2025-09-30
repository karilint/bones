# Bones application architecture

The Bones Django app is organised around reusable archetypes that align with the
[project guidelines](https://github.com/karilint/bones/blob/main/docs/django_app_guidelines.md).
This document summarises the key modules so contributors can quickly orient
themselves when extending navigation, list pages, detail screens, dashboard
widgets, and history timelines.

## Navigation

* `app/bones/navigation.py` defines the primary sections (Dashboard, Transects,
  Occurrences, Workflows, Templates, Reference Data, Data Logs, and History) and
  resolves URL names lazily. Each section is surfaced through the navigation
  context processor registered in `app/config/settings.py`.
* `templates/bones/partials/navigation.html` renders the structure with W3.CSS
  components and Font Awesome icons. Links gracefully fall back to `#` when a
  route has not yet been implemented, ensuring incremental development remains
  navigable.

## Forms, filters, and widgets

* `app/bones/forms.py` exposes select2-backed `ModelForm` classes for the core
  entities. The `Select2ModelFormMixin` applies consistent width and placeholder
  attributes so relationship fields stay searchable in large datasets.
* `app/bones/filters.py` collects django-filter definitions and the
  `FilteredListViewMixin`, which attaches select2 styling to filter widgets,
  applies W3.CSS classes to native inputs, and shields views from database or
  configuration errors by returning safe empty querysets.

## List view archetype

* `app/bones/views/lists.py` implements `BonesListView`, a base class that
  combines authentication, filtering, pagination, and action buttons.
* Entity-specific subclasses (for completed transects, occurrences, workflows,
  templates, questions, reference data, and data logs) focus on table headers,
  row formatting, and queryset optimisation by leveraging the managers in
  `app/bones/models/`.
* Templates such as `templates/bones/completed_transect_list.html` extend the
  base layout and include shared partials (`partials/list_page.html`,
  `partials/table.html`, `partials/filter_form.html`) to keep structure
  consistent.

## Detail view archetype

* `app/bones/views/detail.py` supplies `BonesDetailView`, wrapping Django’s
  `UpdateView` to add breadcrumbs, inline editing panels, and select2-aware form
  styling. Detail implementations exist for questions, data types, project
  configs, and data log files, each using dedicated templates under
  `templates/bones/` and action/metadata partials.

## Master-detail experiences

* `app/bones/views/master_detail.py` introduces `BonesMasterDetailView` and the
  completed transect/occurrence master-detail screens. These pages prefetch
  related responses, workflows, and track points, then expose tabbed layouts
  (Overview, Related Items, History) rendered via
  `templates/bones/partials/tabs.html`.
* Each tab body lives in an include template (for example,
  `templates/bones/completed_transects/_overview.html`) to maintain modularity.

## Dashboard widgets

* `app/bones/views/dashboard.py` aggregates counts, recent activity, and quick
  actions using the optimised managers defined in `app/bones/models/`. The
  accompanying template (`templates/bones/dashboard.html`) uses W3.CSS cards to
  surface the metrics and call-to-action panels described in the guidelines.

## History timelines

* `app/bones/views/history.py` implements login-protected list, record, and
  entry views backed by `django-simple-history` data for transects, occurrences,
  workflows, and questions.
* Templates under `templates/bones/history/` present timelines, diffs, and
  breadcrumbs so users can review change metadata alongside the related records
  and navigation actions.

## Static assets and styling

* `templates/bones/base.html` loads W3.CSS, Font Awesome, and the project’s
  override stylesheet (`static/bones/css/bones.css`). Reusable partials provide
  navigation, tables, filter forms, action panels, breadcrumbs, and tabs that
  share the same visual language across archetypes.

## Testing approach

* Automated tests live in `app/bones/tests/` and cover forms, filters,
  navigation, list views, detail views, master-detail tabs, history access, and
  template markup expectations. The suite focuses on verifying select2 widget
  integration, W3.CSS classes, and graceful handling of database outages without
  requiring a live SQL Server instance.
