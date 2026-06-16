# How to deploy documentation

Deploying documentation is very project-specific. However, it's also easy.

The output of `mkdocs build` is a `site/` directory which contains the `.html` files for a static website. These are very easy to host.

This tutorial only covers hosting mechanisms similar to the template's. This doesn't mean that there aren't other solutions that would work, as requirements vary per deployment.

As such, you can deviate from the setup described here. However, you should have good reasons for this. If you want to deviate from this for any reason, you should ask the [:material-slack: #team-repo-template](https://tryo.slack.com/archives/C08TL160ZLK) to review your setup, just in case.

!!! success "Contributions welcome"
    As usual, if you have other approved setups that work fine, PRs to this page are welcome so we can spread the knowledge.

Here's a quick checklist of some questions to answer to help you evaluate your setup before sending the message:

- [ ] Does the client have some de facto standard for documentation hosting?
- [ ] Can the documentation be open to the world or does it need authentication?
- [ ] Is the method under evaluation expensive to run?
- [ ] Is the method under evaluation easy to access?

If you want to see how to deploy documentation using a setup similar to the template's, read the [standard deploy page](./standard_deploy.md).
