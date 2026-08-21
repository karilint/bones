# Security Policy

## Supported Versions

Security fixes are developed on `main` and released for the current major
version when users need an updated deployable artifact.

| Version | Supported |
| --- | --- |
| `1.x` | Yes |
| `main` | Development |
| `< 1.0` | No |

## Reporting a Vulnerability

Please report suspected vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/karilint/bones/security/advisories/new).
Do not open a public issue or pull request containing vulnerability details.

Include, where possible:

- a description of the vulnerability and its potential impact;
- the affected component, configuration, or dependency;
- steps or a minimal example that reproduces the issue;
- any known mitigations or workarounds; and
- whether the vulnerability has been disclosed elsewhere.

The maintainer will make a reasonable effort to acknowledge a report within
seven days, keep the reporter informed while it is investigated, and coordinate
disclosure after a fix or mitigation is available. Please allow time for a fix
before publishing details.

## Security Updates

Security fixes are delivered through the protected pull-request workflow and
the automated checks configured for this repository. Dependency alerts, secret
scanning, push protection, and code scanning supplement private reports but do
not replace them.
