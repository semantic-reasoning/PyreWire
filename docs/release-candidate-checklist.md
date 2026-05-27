# v1.0.0 release candidate checklist

The v1.0.0 tag must not be cut until every gate below passes on the exact release commit.
Freeze the release commit first:

```bash
git rev-parse HEAD
```

Record that SHA in the release issue or release PR. The `v1.0.0` tag must point to that exact SHA before any publication step. If any gate fails, do not tag or publish; open or link a GitHub issue, PR, or follow-up task that captures the failure before retrying.

| Gate | Owner | Verification | Required evidence | Failure action |
| --- | --- | --- | --- | --- |
| Release commit freeze | Release manager | Command: `git rev-parse HEAD`; manual verification that `v1.0.0` will be created at that SHA. | Recorded release commit SHA and confirmation that the `v1.0.0` tag points to the same SHA. | Link a GitHub issue, PR, or follow-up task and restart the checklist from the corrected commit. |
| Formatting | Release manager | Command: `black --check .`; command: `isort --check-only .`. | Passing command logs from the frozen release commit. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Lint and typing | Release manager | Command: `flake8 .`; command: `mypy src/pyrewire`. | Passing command logs from the frozen release commit. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Test suite | Release manager | Command: `pytest -q`. | Passing pytest log from the frozen release commit. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Documentation build | Docs owner | Command: `mkdocs build --strict`. | Passing strict documentation build log from the frozen release commit. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Source distribution | Packaging owner | Command: `python -m build --sdist`. | The generated `dist/pyrewire-*.tar.gz` path and command log. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| CI workflow | Release manager | Workflow: `.github/workflows/ci.yml` on the frozen release commit. | Successful GitHub Actions run URL for `ci.yml`. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Docs workflow | Docs owner | Workflow: `.github/workflows/docs.yml` on the frozen release commit. | Successful GitHub Actions run URL for `docs.yml`. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Wheel workflow | Packaging owner | Workflow: `.github/workflows/wheels.yml` on the frozen release commit. | Successful GitHub Actions run URL for `wheels.yml`, including Python 3.11, 3.12, 3.13, and 3.14 wheel jobs. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Release workflow dry run review | Release manager | Manual verification of `.github/workflows/release.yml`: it builds wheels, runs dynamic-link verification, performs clean install tests, verifies artifacts, and publishes only after tag-triggered gates pass. Do not actually tag or publish during RC validation. | Linked review note confirming the tag-triggered `release.yml` gates and no pre-tag publish occurred. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Wheel dynamic-link check | Packaging owner | Command: `python scripts/ci/check_dynamic_link.py wheelhouse/*.whl`. | Passing command log for the release wheel artifacts. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Clean wheel install | Bindings owner | Manual verification in a clean environment with no system `libwirelog`: install the candidate wheel, import `pyrewire`, confirm PyreWire version, confirm bundled wirelog version, and run integration tests. | Environment description, install command log, import/version log, wirelog version log, and integration test log. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Release notes and changelog | Release manager | Manual verification that the v1.0.0 changelog section is extractable and matches the GitHub Release body generated from `CHANGELOG.md`. | Extracted release notes artifact or command log plus reviewer confirmation. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
| Metadata, API, support, and security consistency | Release manager | Manual verification that package metadata, public API stability, support matrix, and security policy all describe the same v1.0.0 contract. | Linked review note covering `pyproject.toml`, API stability docs, support docs, and `SECURITY.md`. | Link a GitHub issue, PR, or follow-up task before retrying or tagging. |
