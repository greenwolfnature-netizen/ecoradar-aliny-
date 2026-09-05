#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "update-current-fire-danger.yml"
text = WORKFLOW.read_text(encoding="utf-8")

required = (
    "uses: actions/checkout@v5",
    "uses: actions/setup-python@v6",
    'base_sha=$(git rev-parse HEAD)',
    'git fetch origin "${GITHUB_REF_NAME}"',
    'remote_sha=$(git rev-parse "origin/${GITHUB_REF_NAME}")',
    'if [ "$base_sha" != "$remote_sha" ]; then',
    'if git push origin "HEAD:${GITHUB_REF_NAME}"; then',
    'if [ "$remote_sha" = "$base_sha" ]; then',
    'echo "skip=true" >> "$GITHUB_OUTPUT"',
    "if: steps.commit.outputs.skip != 'true' && env.NETLIFY_AUTH_TOKEN != '' && env.NETLIFY_SITE_ID != ''",
    "if: steps.commit.outputs.skip != 'true'",
)
for fragment in required:
    assert fragment in text, f"Missing workflow safety contract: {fragment}"

assert text.index('git fetch origin "${GITHUB_REF_NAME}"') < text.index("git add index.html")
assert text.count("schedule:") == 1
assert text.count("cron:") == 1

print("ALINYA_WORKFLOW_SAFETY=PASS")
