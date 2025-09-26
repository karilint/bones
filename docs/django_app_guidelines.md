# Django App Coding Guidelines

This document establishes shared conventions for building Django applications in this repository. It consolidates expectations around front-end technologies, Django integrations, and test practices while defining common page archetypes.

## Technology Stack Requirements

### HTML5 foundations
- Author templates using semantic HTML5 elements (`<header>`, `<main>`, `<section>`, `<article>`, `<aside>`, `<footer>`).
- Include the `<!DOCTYPE html>` declaration and `<meta charset="utf-8">` in every base template.
- Use responsive `<meta name="viewport" content="width=device-width, initial-scale=1">` metadata and ensure forms leverage native HTML5 validation attributes where appropriate.

### W3.CSS styling
- Load the official W3.CSS stylesheet from the CDN in the base layout and scope project-specific overrides to additional stylesheets.
- Prefer W3.CSS utility classes for layout (e.g., `w3-container`, `w3-row`, `w3-col`) and responsive behavior before introducing custom CSS.
- Define any custom classes in a dedicated stylesheet loaded **after** W3.CSS so overrides are predictable.

### Font Awesome icons
- Add Font Awesome via its CDN in the shared base template.
- Use descriptive `<i>` or `<span>` elements with `aria-hidden="true"` and provide visually hidden text for assistive technologies when icons convey meaning.
- Reuse icon class combinations for consistent semantics across pages (e.g., `fa-plus` for creation actions, `fa-edit` for editing).

### Django integrations
- **django-select2**: apply to `<select>` fields that benefit from search or async loading. Initialize widgets via Django form widgets (e.g., `ModelSelect2Widget`) and ensure accompanying static files are collected.
- **django-simple-history**: register models with `HistoricalRecords()` to enable history tracking. Expose history views under an authenticated route and use the historical model for audit displays.
- Structure reusable components as class-based views and pluggable apps when possible to keep templates and forms modular.

### Testing expectations
- Back new features with `django.test.TestCase` or `pytest` test cases located in each app's `tests` module.
- Cover both view behavior and template context, including integration of select2 widgets and history features.
- Use `Client` or `RequestFactory` to assert HTML5 structure, W3.CSS classes, and Font Awesome icon usage where critical.

## Responsive, Mobile-First Strategy
- Design layouts mobile-first, progressively enhancing from small screens to larger viewports to ensure performance and usability.
- Target primary breakpoints for phones (~0–600px), tablets (601–992px), laptops (993–1366px), and desktops (1367px+) when structuring CSS and W3.CSS utility classes.
- Ensure navigation, forms, and interactive components remain accessible and touch-friendly across breakpoints, using responsive typography and spacing.
- Verify select2 widgets, Font Awesome icons, and custom components render appropriately across devices using responsive previews or device emulators.
- Apply responsive testing in automated suites when feasible, and include manual validation for major templates before release.

## Page Archetypes
The following terminology describes common page types for documentation and planning:

| Archetype | Common Name | Description | Example Use |
|-----------|-------------|-------------|-------------|
| **List View** | Index / Collection | Displays tabular or card-based collections of entities with filtering, sorting, and pagination controls. | "Project List" page showing all projects with select2-powered filters. |
| **Detail View** | Record View / Form | Presents the full details for a single entity, often with editable form fields and contextual actions. | "Project Detail" form allowing edits to project metadata. |
| **Detail + Sub-list View** | Master-Detail / Nested List | Combines a primary entity detail with related collection data (inline tables, tabs, or accordions). | "Project Detail" page showing project info plus a list of associated tasks. |
| **Create/Edit Form** | Modal / Wizard Form | Dedicated form view for creating or updating records, potentially multi-step. | "New Task" wizard using select2 dropdowns. |
| **Dashboard View** | Overview / Landing | Aggregates key metrics, charts, and navigation shortcuts for quick orientation. | Administrative dashboard summarizing recent history changes. |
| **History View** | Audit Log | Surfaces django-simple-history entries with comparisons and metadata. | "Project History" timeline displaying edits made by users. |

Use these terms consistently in user stories, code comments, and documentation to keep planning and implementation aligned.

### Tabbed Interfaces
- Use tabs to consolidate related content within a single archetype when separate pages would create unnecessary navigation steps.
- Standard tabs often include **Overview** (primary detail content), **Related Items** (associated lists, e.g., tasks or attachments), and **Audit Log** (django-simple-history snapshots for the current record).
- Additional tabs may cover **Comments**, **Activity**, or **Settings**; name tabs with concise nouns and ensure they map to the underlying data source or action.
- Implement tabs with accessible markup: leverage W3.CSS tab components or ARIA-compliant patterns so keyboard and screen-reader users can move between sections.
- Keep tab content modular by storing each tab body in a dedicated include template to promote reuse and maintainability.

## Template Structure
1. Start from a shared `base.html` that loads HTML5 boilerplate, W3.CSS, Font Awesome, and project-wide scripts.
2. Compose page-specific templates by extending the base and populating semantic blocks (`<main>`, `<nav>`, etc.).
3. Extract reusable components (navigation bars, forms, lists) into `{% include %}` templates to encourage reuse across archetypes.
4. Place static assets in app-specific `static/` directories, namespaced by app label.

## Code Comment Expectations
- Write clear, concise comments that explain *why* complex decisions or non-obvious implementations exist rather than repeating what the code already states.
- Document integration nuances for select2 widgets, simplehistory usage, or custom W3.CSS overrides directly above the relevant code blocks.
- Update or remove stale comments during refactors to keep guidance trustworthy.

## Accessibility and Internationalization
- Ensure color contrast meets WCAG AA when layering custom CSS over W3.CSS.
- Provide `aria-label`, `aria-describedby`, and `aria-live` attributes to enhance screen reader support, especially around dynamic select2 widgets.
- Mark strings for translation with `gettext`/`gettext_lazy` and keep `.po` files updated.

## Deployment and Maintenance Notes
- Collect static files (including W3.CSS overrides, select2 assets, and Font Awesome) via `python manage.py collectstatic` during deployments.
- Document new page archetypes or component patterns in this file to keep the guidelines current.
- Review tests and linting outputs in CI to ensure adherence to these conventions.
