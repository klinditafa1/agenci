# Security

## Reporting a vulnerability in Agenci

If you find a security vulnerability in Agenci itself (the CLI,
storage layer, dashboard, or GitHub Action — not findings from
*running* Agenci against your own agent), please report it privately
rather than opening a public issue:

- Open a [GitHub Security Advisory](https://github.com/agenci-dev/agenci/security/advisories/new)
  on the repository, or
- Email the maintainers (see the repository's contact information) with
  a description of the issue, steps to reproduce, and the potential
  impact.

Please give us a reasonable window to investigate and patch before any
public disclosure. We'll acknowledge reports and keep you updated as
we work on a fix.

## Scope of Agenci's security-testing framework

Agenci ships a security-testing framework (`agenci security`,
`agenci/security/`) intended **for authorized testing of AI systems
you own or are explicitly authorized to test**. Read this section
before relying on it.

### What it does

- Runs `type: security` test cases against your agent and checks the
  output/tool-calls against policies **you define**
  (`allowed_tools`/`forbidden_tools`/`max_tool_calls`/`forbidden_output_patterns`)
  and assertions **you write** (e.g. prompt-injection resistance
  checks).
- Aggregates results into a per-category, severity-weighted score.

### What it deliberately does not do

- It does not implement malware, credential theft, persistence
  mechanisms, or unauthorized exploitation of any kind.
- It does not attempt to find vulnerabilities you haven't described a
  policy or assertion for — it is not a fuzzer or a red-teaming tool.
- Its security score is a summary of *the checks you defined passing
  or failing*, not a penetration-test result or a formal security
  guarantee. See [docs/security.md](docs/security.md#what-the-security-score-is-and-is-not).

### Responsible use

Only run Agenci's security tests against AI systems you own or have
explicit authorization to test. Do not use `input` fields, custom
assertions, or `policy` configuration to build or store material meant
to facilitate attacks against systems you don't control — that is
outside the intended use of this project and its maintainers will not
support it.

## Using the GitHub Action and PR comments securely

If you use `action/action.yml` or `agenci pr-comment`, scope the token
you give it to the minimum required permissions
(`pull-requests: write`), and never trigger a workflow that checks out
and executes untrusted PR code on `pull_request_target` — see
[docs/github-actions.md#security-considerations](docs/github-actions.md#security-considerations)
for the full guidance and why this matters. This is a general GitHub
Actions security practice, not something specific to Agenci, but it's
directly relevant here because Agenci's action both runs your agent's
code and posts using a privileged token in the same job.

## Supported versions

Agenci is pre-1.0 (`0.x`); security fixes land on the latest release.
Once the project reaches 1.0, this section will list which major
versions receive security patches.
