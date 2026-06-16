# Using the Template

## Prerequisites

| Tool   | Install Instructions                                        |
| ------ | ----------------------------------------------------------- |
| `uv`   | [Installation guide](../batteries/dev_environment.md#setup) |
| `just` | [Installation guide](../batteries/task_runner.md#setup)     |

If any of these are missing, the instantiation script will fail.

## Quick Start

1. Click the `Use this template` button at the top of this repo's homepage or the button below to spawn a new repo from this template.

    [Use this template :octicons-rocket-24:](https://github.com/new?owner=tryolabs&template_name=repo-template&template_owner=tryolabs){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank" }

2. Clone the new repo to your local environment.

3. Choose your initialization mode. You may review the [initialization modes guide](initialization_modes.md) to understand which mode best fits your project.

4. Run `chmod +x init.sh && ./init.sh <your_project_name>`.

    !!! note
        The project's accepted Python version will be set to `~=<python version>`, which means it'll accept all patch updates released after the one you specified.

        Feel free to change this manually in the `pyproject.toml` file after running the script.

    !!! warning
        You'll be prompted about enabling/disabling certain settings/features, so pay attention!

5. The init script automatically adds and commits all generated files to Git — including `uv.lock` and `.secrets.baseline` files.

6. Review the commit and push your changes when you're ready — your project is all set up!

    !!! tip
        Your project's source code should be placed in the newly-created folder with your project's name, so that absolute imports (`from my_project.my_module import func`) work everywhere.

7. You may now optionally [configure your repository](configure_your_repository.md).

## How to use the template on clients outside of Tryolabs's GitHub

1. Click the `Download as ZIP` button below to download a ZIP of the template to your computer.

    [Download as ZIP :octicons-desktop-download-24:](https://github.com/tryolabs/repo-template/archive/refs/heads/main.zip){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank" }

2. Clone client's repo to your local environment.
3. Delete everything on the client's repo in your local environment, except for the `.git` folder.

    !!! tip
        Use the following command:
        ```bash
        find . -mindepth 1 -maxdepth 1 -not -name .git -exec rm -rf {} +
        ```

4. Copy all the contents of the repo template (unzipped) to the client's repo.
5. Go to step 4. of the Quick Start section and continue from there.
