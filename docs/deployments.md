# Deployment workflow

Bones release containers are built once by the release workflow and published
to `ghcr.io/karilint/bones`. Deployments must consume those release artifacts by
digest; staging and production must not rebuild source or use a mutable tag.

## Approve an artifact

1. Open **Actions**, select **Deployment gate**, and choose **Run workflow** from
   the release tag that produced the image.
2. Select the `staging` or `production` GitHub Environment.
3. Enter the image's complete `sha256:` digest from the corresponding release
   workflow or GHCR package version.
4. Review the job summary and use its exact `ghcr.io/karilint/bones@sha256:...`
   reference in the target platform's deployment configuration.

The gate rejects tags, verifies the image's GitHub artifact attestation against
this repository, and pulls the immutable image before recording a successful
GitHub Environment deployment. It intentionally does not receive application
secrets or connect to a host: the repository does not currently define a
hosting platform. A platform-specific rollout step can be added after the
verification steps when that target is known.

## Environment policy

The `staging` and `production` environments accept deployments only from
semantic-version release tags (`v*.*.*`). Production should gain required
reviewers when a second maintainer is available; enabling self-review
prevention for a sole maintainer would otherwise block all deployments.

The former Docker Hub workflows were removed because their `staging` and `prod`
branches did not exist, their required secrets were not configured, and they
rebuilt and published mutable `latest` images independently of the verified
release pipeline.
