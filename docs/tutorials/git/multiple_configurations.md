# How to have multiple git configurations for different clients

Sometimes you need different (local) `git` settings for different clients. For example, you might want to use your client-provided email to author commits for client projects and some personal email for personal and Tryolabs projects. You might also want to sign your commits to the client with GPG/SSH but not sign those made for other projects.

This guide doesn’t depend on the `git` host you use (like GitHub (GH) or GitLab (GL)).

!!! note "A note on [`user.email`](https://git-scm.com/docs/git-config#Documentation/git-config.txt-useremail)'s importance and the recommended value"
    :material-fast-forward: **In short:** use the `noreply` email address provided by your `git` hoster to author local commits to avoid headaches in the future.

    Git platforms like GH and GL link commits to users via the [`user.email`](https://git-scm.com/docs/git-config#Documentation/git-config.txt-useremail) that was used when authoring the commit. Therefore, if you want some commit done in your local machine to map to your GH/GL accounts, you **must** author it with an email that you’ve added to your GH/GL account.

    If you’re curious, you can read more about this in the [Setting your Commit email Address](https://docs.github.com/en/account-and-profile/setting-up-and-managing-your-personal-account-on-github/managing-email-preferences/setting-your-commit-email-address) article.

    A side effect of this is that you may push commits with the wrong email address and they will end up being attached to an account that’s not yours. You can read more about this in [Why are my commits linked to the wrong user?](https://docs.github.com/en/pull-requests/committing-changes-to-your-project/troubleshooting-commits/why-are-my-commits-linked-to-the-wrong-user).

    GH/GL (and probably other hosters) provide a “no reply” email that’s directly attached to your account and doesn’t change. Any time you can, you **should** use this email to author commits to avoid having to add a new email to your GH/GL accounts each time you change projects, clients or employers.

We’ll refer to “workspace” as a set of repos for which you want certain configurations. Picture having a `client_1` workspace for client 1, a `client_2` workspace for client 2 and some default settings for any repo outside of those workspaces.

To achieve this, we can use the `includeIf` directive on `.gitconfig` and a smart directory structure.

## Guide

1. Create a new directory somewhere to place all of this workspace’s repos within this directory. *Your custom settings will apply only to repos under this directory.*

    ??? example
        Some good locations are `~/<workspace_name>`, `~/Dev/<workspace_name>` or `~/workspaces/<workspace_name>`, but you can pick your poison.

2. Open your `.gitconfig` in a text editor.

    ??? example
        Running `code ~/.gitconfig` should do the trick.

3. Identify the configurations that need to be different for each workspace.

    ??? example
        For the example, let’s use `user.email` and `init.defaultBranch`.

4. Create new `.gitconfig.<workspace_name>` files next to your `.gitconfig` for each workspace other than the default one.

    ??? example
        `touch ~/.gitconfig.latam`.

5. In each of the created files, add your specific settings.

    ??? example

        `~/.gitconfig.latam`:

        ```toml
        [user]
        email = ID+username@users.noreply.gitlab.com

        [init]
        defaultBranch = master
        ```

6. Edit your `.gitconfig` file to include these new files by using `includeIf`.
    - Add, at the bottom, `[includeIf "..."]` directives. You can see all options [here](https://git-scm.com/docs/git-config#_conditional_includes), but yours will most likely look like `[includeIf "gitdir:~/..."]`.

        !!! tip
            To include subdirectories, it’s best to end your path with `/**`.

    - Each of these sections acts like a copy-paste: the contents of the included config will be added verbatim to your `.gitconfig` file.
    - When parsing configurations, `git` parses the file top to bottom and overrides any upper values with any bottom values. Therefore, *include the most general custom files at the top, and the most specific custom files at the bottom.*

    ??? example

        `~/.gitconfig`:

        ```toml
        [user]
        <other_settings>
        email = default_email@email.com

        [init]
        <other_settings>
        defaultBranch = main

        [includeIf "gitdir:~/Dev/LATAM/**"]
        path = .gitconfig.latam
        ```

7. Check that everything worked. If not, check [Troubleshooting](#troubleshooting).
    1. Go to one of your specific directories.
    2. Run `git config --list --show-origin`.
    3. Verify that your custom settings have the correct value and origin.
    4. Go to some non specific directory.
    5. Run `git config --list --show-origin`.
    6. Verify that your default settings have the correct value and origin.

## Troubleshooting

### Paths with Spaces

If your workspace path contains spaces, make sure to wrap the path in quotes in your `.gitconfig`:

```toml
[includeIf "gitdir:~/Projects Directory/client1/**"]
path = .gitconfig.client1
```

### Case Sensitivity

Git treats paths differently depending on your operating system:

- On Windows and macOS (case-insensitive by default): Path matching is case-insensitive
- On Linux (case-sensitive): Path matching is case-sensitive

Make sure your paths in `.gitconfig` match the exact case of your directory structure on case-sensitive systems.

## :material-magnify: Search Terms

- multiple git configurations
- git configurations per project
- git conditional include
- git different email per project
- git workspace specific settings
- git includeIf
- git config per directory
- git multiple accounts
- git multiple identities
- git different user per repository
- git client specific configuration
- git separate email addresses
- git conditional configuration
- git directory based config
- manage multiple git profiles
- git config for different clients
- git workspace isolation
- git config per client
- git multi-account setup
- git organization specific settings
- git custom configuration per project
- git config for work and personal
- git separate signing keys
- git multiple GPG keys