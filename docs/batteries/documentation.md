# Documentation Setup

The template uses and provides [MkDocs](https://www.mkdocs.org/) with the [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) theme to build and serve project documentation.

The configuration is managed in `mkdocs.yml`, which defines the site structure, theme, plugins, and navigation.

## Automatic code reference generation

The template automatically generates API reference documentation from your Python code using [mkdocstrings](https://mkdocstrings.github.io/).

You document your code using [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings) and the built in `mkdocs` site automagically generates an API Reference tab in the site that shows your code objects and their documentation.

## Basics of Usage

### Local serving

To serve the documentation locally, just run `just serve-docs`. This will spin up a local server and make you project's documentation available.

### Building

If you want to build the documentation, for sharing or deploying, just run `just build-docs`. This will output the static site to the local `site/` directory.

!!! tip
    To see how to build the template's documentation, consult the [documentation development page](../development/documentation.md).

## Deployment

The Repo Template provides a basic authenticated hosting option that you may use to host your project's documentation. To access it, visit `documentation.tryolabs.com`.

!!! note
    There's no documentation index on purpose. You *must* add the path to your project to access its documentation. For example: `documentation.tryolabs.com/repo-template`.

!!! danger "Security warning"
    While secured by authentication, any user with an `@tryolabs.com` Google Workspace account will have access to **all subsites** pushed to this bucket.

    If you require more fine grained control (i.e., restricting to a subset of people at Tryolabs) or need to give access to a client, please host your own documentation. See [the deployment tutorial](../tutorials/documentation/deployments/introduction.md) for some guidance.

    **Do not, under any circumstance**, make access to `documentation.tryolabs.com` less restrictive by permitting access to anyone outside of `@tryolabs.com` without consulting with [:material-slack: #team-repo-template](https://tryo.slack.com/archives/C08TL160ZLK) first.

### Automatic Deployment

The template provides a GitHub Action that builds and publishes your project's documentation to [`documentation.tryolabs.com`](https://documentation.tryolabs.com).

No manual intervention is required! Your documentation will be automatically updated whenever you merge changes to the `main` branch.

!!! tip
    You can also trigger the deployment manually using the "Actions" tab in your GitHub repository.

For more info on deployments, including hosting your own, see the [documentation deployment tutorial](../tutorials/documentation/deployments/introduction.md).

### Manual Deployment

If you need to deploy manually or want more control over the process, follow these steps:

1. **Build:**
    - To build your project's documentation, follow [these steps](#building).
    - To build the template's documentation, follow [these steps](../development/documentation.md#build-and-serve) instead.
2. **Publish:** Push to the Bucket by following [these steps](../tutorials/documentation/deployments/standard_deploy.md#multisite-mode-push).
