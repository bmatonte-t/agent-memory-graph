# Automation & Maintenance

## GitHub Actions Workflows

The template includes several automated workflows:

### Code Quality

Runs linting, formatting, docstring coverage, pytest with coverage and static type checking on push (i.e., on each new pushed commit).

### Code Metrics

Calculate and compare code complexity metrics using `radon` on each opened PR.

### PR Style Checker

Ensures titles are well formatted and warns when PRs are missing assignees or tags so that automatic release notes stay tidy without blocking merges.

### Pre-commit Auto-update

Automatically keeps pre-commit hooks up-to-date by running `pre-commit autoupdate` weekly and creating a pull request with the updates.

#### Schedule

Runs every Monday at midnight (UTC) and can be manually triggered from the Actions tab.

#### Workflow

The workflow automatically updates all pre-commit hooks to their latest versions and creates a PR with the changes.

Once open, someone from your team should review the PR. Check the releases of the updated hooks to see if there are new functionalities or breaking changes that may affect your workflow.

Ensure you switch to the branch and run the hooks as indicated in the PR.

Once you're sure the updates are compatible, merge the change.

#### Why Auto-update Pre-commit Hooks?

- **Security:** Keeps hooks patched with latest security fixes.
- **Features:** Access to new hook functionalities automatically.
- **Maintenance:** Reduces manual effort in keeping hooks current.
- **Consistency:** Ensures all team members use the same hook versions.

### Documentation Deployment

Automatically builds and publishes project documentation to the bucket configured in `just docs-publish-site` when merging to `main`. See the [documentation page](./documentation.md#automatic-deployment) for more.

## Dependabot

Dependabot automatically keeps dependencies up-to-date by creating pull requests for updates.

### Workflow

Dependabot opens PRs with dependency updates every once in a while (see [configuration](#configuration)).

Once open, someone from your team should review the PR. Checkout the code, sync the dependencies and test your code to ensure nothing broke.

Once you're sure, merge the change.

### Configuration

The `.github/dependabot.yml` file configures the bot's behavior.

By default, we run Python and GitHub Action version updates weekly, and open up to 5 PRs per week with a `dependencies` label.

You may check [Dependabot's configuration documentation](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference) for more.

### Why Dependabot?

- **Security:** Automatically patches vulnerabilities.
- **Maintenance:** Keeps dependencies current.
- **Efficiency:** Reduces manual dependency management.
- **Visibility:** Clear tracking of dependency changes.
- **Integrated with GitHub:** Easy to integrate with our GitHub repos.
