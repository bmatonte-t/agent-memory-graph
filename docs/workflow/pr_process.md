# Pull Request Process

## Creating a Pull Request

### Before Opening a PR

1. **Ensure your branch is up to date:**

   ```bash
   git fetch origin
   git rebase origin/dev  # or origin/main depending on target
   ```

2. **Run tests locally:**

   ```bash
   just test
   just lint
   just format
   ```

3. **Review your changes:**
   - Check for debugging code or temporary changes.
   - Ensure all files are properly formatted.
   - Verify commit messages follow conventions.

## Best Practices

### PR Size

- **Keep PRs small:** Easier to review and less risky. Aim for ~300 lines, and no more than 1000 lines (excluding unreviewable files like lock files).
- **One feature per PR:** Easier to understand and revert if needed. Do not implement huge changes in a single PR.
- **Split large changes:** Use multiple related PRs.

### Communication

- **Use draft PRs** for work-in-progress or early feedback.
- **Tag reviewers** mention specific people for targeted review.
- **Update stakeholders:** Keep interested parties informed via Slack.

### Documentation

Don't forget to update documentation when changing code.
