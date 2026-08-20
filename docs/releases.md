# Release process

Bones uses Semantic Versioning and intentional releases. Individual merges do
not automatically create versions.

## Version policy

- Patch releases contain backward-compatible fixes and dependency updates.
- Minor releases contain backward-compatible features.
- Major releases contain breaking application, configuration, data, API, or
  deployment changes.

The canonical release version is stored in `app/VERSION`. Each release also has
an entry in `CHANGELOG.md` and a notes file at `docs/releases/vX.Y.Z.md`.

## Preparing a release

1. Create a release branch from current `main`.
2. Update `app/VERSION`, `CHANGELOG.md`, and the versioned release-notes file.
3. Merge the release pull request after all required checks pass.
4. Create and push the matching `vX.Y.Z` tag at the merge commit.
5. Wait for the `Release` workflow to verify the tag, rerun the application
   checks, publish the container, attest it, and create the GitHub release.

The workflow rejects tags whose version differs from `app/VERSION`, tags that
are not contained in `main`, and releases without versioned notes. Published
tags must never be moved or reused; issue a new patch release instead.

## Release artifacts

Release containers are published to `ghcr.io/karilint/bones` with these tags:

- the complete version, such as `1.0.0`;
- compatible major/minor aliases, such as `1.0` and `1`;
- the source commit, such as `sha-<full-commit>`; and
- `latest` for the newest stable release.

Production deployments should pin the complete version or source-commit tag.
Every image includes an SBOM and BuildKit provenance, plus a GitHub artifact
attestation bound to the published digest.
