# Branch Management & Naming Conventions

## Why Use `dev` and `main` Branches?

Using separate `dev` and `main` branches helps maintain a clean and stable codebase. Here are the key reasons:

1. **Stability**: The `main` branch remains stable and production-ready, containing only thoroughly tested and approved changes.
2. **Isolation**: Development happens in the `dev` branch, allowing for continuous integration and testing without affecting the main codebase.
3. **Controlled Releases**: Changes are promoted from `dev` to `main` only after they meet quality standards, ensuring reliable releases.

## Branch Naming Conventions

Adopting a consistent branch naming convention improves the clarity and manageability of your repository:

### Feature Branches

- **Naming**: `feature/<short-description>`
- **Example**: `feature/user-authentication`
- **Use for**: New features or enhancements

### Bug Fixes

- **Naming**: `bugfix/<short-description>`
- **Example**: `bugfix/login-error`
- **Use for**: Fixing bugs or issues

### Hotfixes

- **Naming**: `hotfix/<short-description>`
- **Example**: `hotfix/critical-security-patch`
- **Use for**: Urgent fixes that need to be applied to the `main` branch immediately

### Release Branches

- **Naming**: `release/<version-number>`
- **Example**: `release/1.0.0`
- **Use for**: Preparing a new production release

### Chore/Documentation

- **Naming**: `chore/<short-description>` or `docs/<short-description>`
- **Example**: `chore/cleanup-scripts` or `docs/update-readme`
- **Use for**: Maintenance tasks or documentation updates

## Merge Workflow

1. **Develop features:** Create feature branches off from `dev`.
2. **Merge to dev:** Use **merge** or **rebase and merge** to merge feature branches into `dev`. If using **merge** be sure to manually rebase before merging to maintain linear history.
3. **Stabilize dev:** Ensure `dev` is stable and tested.
4. **Merge to main:** Create a pull request from `dev` to `main`.
5. **Review and merge:** Use **rebase and merge** or **merge commit** for `dev` to `main`.
6. **Version tagging:** Consider using [CalVer](https://calver.org/), [SemVer](https://semver.org/) or other versioning schemes.
