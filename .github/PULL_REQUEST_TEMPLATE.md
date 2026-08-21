## Summary

<!-- Explain the outcome and why the change is needed. -->

## Related issue

<!-- Use "Closes #123" when applicable. -->

## Validation

<!-- List the exact checks run and their results. -->

- [ ] Relevant Django checks and tests pass.
- [ ] Container validation passes when runtime or dependencies changed.
- [ ] I documented anything that could not be verified locally.

## User-facing evidence

<!-- Add sanitized screenshots or output for visible changes, or write "Not applicable". -->

## Checklist

- [ ] The change is focused and follows the existing Bones architecture.
- [ ] Tests cover changed behavior without requiring a live production database.
- [ ] Documentation and release notes are updated when needed.
- [ ] No credentials, personal data, private field records, or `.env` contents are included.
- [ ] Database changes account for unmanaged SQL Server tables.
