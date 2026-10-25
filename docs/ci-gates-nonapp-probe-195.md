# Temporary documentation-only CI trigger probe (DO NOT MERGE)

This disposable document exists only to validate that PR #206's removal of
workflow-level pull_request path filters triggers full Core API CI and Web CI
for pull requests with no app, runtime, policy, script or workflow changes.

Parent issue: #195. Diagnostic PR base: ci/always-present-api-web-checks-195.
No production configuration, code, dependency, secrets or runner labels changed.
Close the diagnostic pull request without merge after observing exact-SHA jobs.
