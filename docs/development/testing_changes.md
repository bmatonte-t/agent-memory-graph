# Testing Changes to the Template

## Development Workflow

When working on improvements to the template itself, use the following script to test your changes safely:

```shell
#!/usr/bin/env bash
set -euo pipefail

# Create a temporary directory
tmpdir=$(mktemp -d)

# Ensure cleanup on exit (success, error, or interrupt)
trap 'rm -rf -- "$tmpdir"' EXIT

# Copy all contents from the current directory:
rsync -a --exclude='.git' --exclude='.venv' ./ "$tmpdir/"

cd "$tmpdir"

git init
git config --local commit.gpgsign false

# Execute init.sh.
chmod +x init.sh

if test=true ./init.sh test-instantiation; then
  echo "✔️ Success: initialization completed"
else
  echo "❌ Error: initialization failed" >&2
  exit 1
fi

exit 0
```

This will instantiate the template in a temporary directory, so you can at least ensure the process works fine.

If stuff fails, you may run the code till the execution of the `init.sh` and, once done, open a VSCode window in the temporary directory to investigate the template's status.

You can now inspect the `test-instantiation/test.py` file to see if linting works and if dependencies were properly installed.
