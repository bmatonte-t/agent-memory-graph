# Release and Communication Strategy

This document outlines how we communicate changes, updates, and releases to users of the repo-template.

## Communication Channels

### Weekly Updates

- **Where:** [:material-slack: #team-repo-template](https://tryo.slack.com/archives/C08TL160ZLK).
- **When:** Once per week.
- **What:** Communicate newly merged PRs, including:
    - Brief description of the changes.
    - Links to the merged PRs.
    - Author shoutouts to recognize contributors.
- **Purpose:** Keep the team informed of ongoing improvements and acknowledge contributors' efforts.

### Monthly Releases

- **Where:** [:material-slack: #programming](https://tryo.slack.com/archives/C025F78FC).
- **When:** Approximately last Friday of each month.
- **What:** Announce a new GitHub release with a summary of all changes since the previous release.
- **Purpose:** Provide a clear, versioned reference point for all template changes making it easier for users to track what's new.

## Release Process

### Creating a Release

1. Go to the Draft GitHub Release page by clicking on the button below.

    [New Release :material-github:](https://github.com/tryolabs/repo-template/releases/new){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank"}

2. Decide how to tag the release.
    1. Use [CalVer](https://calver.org/) to tag the release with today's date in the `YYYY.0M.0D` format.

        !!! example
            - If today is December 30, 2025, pick the `2025.12.30` tag.
            - If today is December 3, 2025, pick the `2025.12.03` tag.
            - If today is July 30, 2025, pick the `2025.07.30` tag.
            - If today is July 3, 2025, pick the `2025.07.03` tag.

3. Assign a tag to the release.
    1. Click on the *Tag: Select Tag* dropdown.
    2. Write the tag you selected in the previous step.
    3. Click on the *Create new tag* button.
4. Write the release notes.
    1. Click on *Generate release notes*.
    2. Add a `# <tag> - Version Title` title.
    3. Write a short description of this release.
        - What's the biggest change?
        - Are there any breaking changes? If so, maybe include some guidance on what to do.
    4. Inspect the What's new sections.
    5. Add a small thank you note at the end in the New Contributors section, if present.
5. Post the release announcement in [:material-slack: #programming](https://tryo.slack.com/archives/C025F78FC). Include:
    - Link to the GitHub release (full changelog).
    - Brief highlights of the most important changes.
    - Call to action for users to review changes that might need backporting.

### Notifying Template Users

When a release includes changes that template users might want to backport to their repositories, we may proactively notify them.

#### Finding Template Users

Use the following script to identify repositories created from the repo-template:

```bash
#!/usr/bin/env bash

# Find repos in the tryolabs org created from the "repo-template" template and output a pretty table.

# jq filter: select templateRepository == "repo-template", exclude names containing "onboarding",
# and created after 2025-01-01.
JQ_FILTER='[.[]
  | select(
      .templateRepository.name == "repo-template" and
      (.name | contains("onboarding") | not) and
      .createdAt >= "2025-01-01T00:00:00Z"
    )
  | {name, createdAt}
] | sort_by(.createdAt) | reverse'

# Python formatter — keep as a heredoc for readability
PY_SCRIPT=$(cat <<'PY'
import sys
import json
from rich.console import Console
from rich.table import Table

table = Table()
table.add_column('Created At')
table.add_column('Name')

data = json.load(sys.stdin)
for x in data:
    table.add_row(x['createdAt'], x['name'])

Console().print(table)
PY
)

# Execute the pipeline
gh repo list tryolabs --limit 2000 --json name,createdAt,templateRepository --jq "$JQ_FILTER" \
  | uv run --no-project --python 3.14 --with rich python -c "$PY_SCRIPT"
```

!!! tip
    Adjust the `createdAt` filter date as needed to target specific repositories or time periods.

## Benefits of This Strategy

1. **Regular Communication:** Weekly updates keep the team engaged and informed.
2. **Predictable Releases:** Monthly release schedule helps users plan when to review and adopt changes.
3. **Version Tracking:** CalVer-style versioning (`YYYY.0M.0D`) makes it easy to identify when changes were released.
4. **Proactive Outreach:** Ability to notify specific template users ensures critical changes are communicated effectively.
5. **Contributor Recognition:** Regular shoutouts encourage and acknowledge contributions to the template.
