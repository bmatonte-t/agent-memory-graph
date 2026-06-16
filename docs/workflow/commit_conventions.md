# Commit Conventions

## Commit Message Format

The description contains a concise description of the change.

### Guidelines

- **Use the imperative, present tense**: "change" not "changed" nor "changes"
- You should be able to paste your commit message after "This commit will..." or "This commit should..." and the sentence should make sense.
- **Capitalize** the first letter.
- **No dot (.)** at the end of the first line.
- **Wrap first line to 50 characters** ideally.
- **Add more context**: Use blank line after summary, then add details (wrapped to 72 characters).

### Examples

#### Good

```text
Resolve login timeout issue

The authentication service was timing out after 30 seconds
when connecting to the external OAuth provider. Increased
the timeout to 60 seconds and added retry logic.

Fixes #123.
```

```text
Add user profile management

- Add profile editing functionality
- Implement avatar upload
- Add profile validation
- Update user settings UI

Co-authored-by: Jane Smith <jane@example.com>
```

```text
fix: prevent race condition in user session handling

When multiple requests tried to access the same user session
simultaneously, it could lead to inconsistent state. Added
proper locking mechanism to ensure thread safety.

Fixes #234
```

#### Bad

```text
fixed stuff
```

## Best Practices

### Atomic Commits

Each commit should represent a single logical change:

- **One concept per commit:** Don't mix feature development with bug fixes.
- **Complete changes:** Ensure the codebase works after each commit.
- **Reviewable size:** Keep commits small enough for easy review.

### Descriptive Messages

- **Explain the why:** Not just what was changed, but why.
- **Reference issues:** Use "Fixes #123" or "Closes #456".
- **Include context:** Help future developers understand decisions.

### Don't use commits as a save button

You should use (and probably abuse) `git rebase --interactive` while you develop. If you have to make a change due to a PR review, it's always better to add a new commit and squash it with the original commit that added the code you're changing than leaving both commits.

Remember, from `main`'s perspective nobody cares that you implemented a function to do X and then fixed a bug in the implementation that was caught during PR review.
