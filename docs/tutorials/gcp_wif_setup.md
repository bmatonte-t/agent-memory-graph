# Workload Identity Federation

This document provides instructions for configuring Workload Identity Federation (WIF) in Google Cloud Platform (GCP).

!!! note
    If you want to publish to [`documentation.tryolabs.com`](https://documentation.tryolabs.com), you may authenticate as the documentation publishing SA using the organization-wide secrets and variables. The publishing GitHub Action bundled with your repo spawned from the template should already be configured for that, check its Auth step.

## What is WIF?

WIF enables secure authentication between external identity providers and GCP services without requiring service account keys, allowing workloads running outside of GCP to access Google Cloud resources using federated credentials.

In a WIF setup, there are 4 relevant entities:

- **External Identity Provider:** The external service trying to authenticate. For example, GitHub.
- **Provider:** Defines the trust relationship with the External Identity Provider. That is, defines
    - *Who to trust:* I trust the token issuer at `https://token.actions.githubusercontent.com`.
    - *What to check:* The token must be for my `my-org/my-repo` repository. These are referred to as attribute conditions and there are many, many more.
    - *How to map identities:* Map the GitHub repository claim to a GCP attribute.
- **Pool:** Simply a collection of external identity validators.
- **Service Account:** An account (i.e., an email) within GCP that has certain rights to do certain things.

You may think of this by means of an analogy: the WIF Pool is a security checkpoint with many lanes. When a person (External Identity Provider) arrives, an agent directs them to the correct lane based on their passport's origin, where they speak to an agent (the Provider) who asks different questions to determine if the person should clear the security checkpoint or not.

If they get cleared, they're granted temporary rights to operate as a Service Account (SA) :disguised_face: and perform the actions the SA can perform.

## Prerequisites

1. Go to `console.cloud.google.com`.
2. Select your project from the top right box.
3. Note your `PROJECT_NUMBER` and `PROJECT_ID` from the landing page.

!!! tip
    All steps must be performed from your GCP project, so ensure you've selected that correctly each time you go to perform an action.

## Create the Service Account

This identity will be assumed by your GitHub Action.

1. Click on the button to create a new service account [^1].

    [Create Service Account :octicons-hubot-24:](https://console.cloud.google.com/iam-admin/serviceaccounts/create){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank"}

2. Fill in the details:
    - Pick a descriptive *Name* (i.e., `github-actions-docs-deploy`).
    - Note the full email address generated under *Service account ID*, which is your `SERVICE_ACCOUNT_EMAIL`.
    - Add a description.
    - Click *Create and Continue*.
3. Click **Done**. We'll assign permissions later.

!!! danger
    Do **NOT** create or download any JSON keys for this Service Account.

## Grant Permissions to the Service Account

Give the new Service Account access to the specific resources it needs. You should grant it the least privileges possible.

In this example, we'll walk you through how to give it file creation access to a single GCS Bucket, but you'll have to see how to grant it access to the specific resources you want. You may use the [Google IAM Roles and Permissions](https://docs.cloud.google.com/iam/docs/roles-permissions) page to figure out what you need, or ask your favorite GenAI robot.

1. Go to the GCS Buckets page.

    [Buckets Browser :simple-googlecloudstorage:](https://console.cloud.google.com/storage/browser){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank"}

2. Click on the bucket you want to grant access to.
3. Grant access.
    1. Click the *Permissions* tab.
    2. Click *+ Grant Access*.
    3. Paste `SERVICE_ACCOUNT_EMAIL` in the *New principals* box.
    4. Select the *minimum* roles required. In our case *Storage Object Admin*.
    5. Click *Save*.

## Create the WIF Pool and Provider

1. Click on the button below to create a new Workload Identity Pool [^2].

    [Create Workload Identity Pool :material-account-group:](https://console.cloud.google.com/iam-admin/workload-identity-pools/create){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank"}

2. Create an Identity Pool.
    - Pick a descriptive *Name* (i.e. `github-pool`). This is your `WIF_POOL_NAME`.
    - We recommend that you use the name as the *Pool ID*.
    - Add a description (i.e. *GitHub authentication providers.*).
    - Ensure *Enabled Pool* is checked.
    - Click *Continue*.
3. Add a Provider to pool. Here we'll set up GitHub, but instructions for other External Identity Providers may vary.
    1. Select `OpenID Connect (OIDC)` from the *Select a provider* selectbox.
    2. Pick a descriptive *Name* (i.e. `github-provider`). This is your `WIF_PROVIDER_NAME`.
    3. In the *Issuer (URL)* box paste `https://token.actions.githubusercontent.com`.
    4. Leave the JWK field blank.
    5. Check *Default Audience*.
    6. Note the URL that appears below. In particular, the bit after `https://iam.googleapis.com/` is your `WIF_PROVIDER_RESOURCE_NAME`, which you'll need later.

4. Configure Provider Attributes.

    !!! info
        These attributes allow you to access information about the External Identity Provider in order to create assertions about them (i.e., get answers to your questions about who they are).

    1. In the first, pre-filled `google.subject` mapping, write `assertion.sub` in the *OIDC 1* field.
    2. Add the repo owner attribute to access the repository that's trying to validate's owner.
        1. Click *+ Add Mapping*.
        2. Write `attribute.repository_owner` in the Google (left) selectbox.
        3. Write `assertion.repository_owner` in the *OIDC 2* (right) selectbox.
    3. Optionally add the repo name value, if you intend to only validate a given repository.
        1. Click *+ Add Mapping*.
        2. Write `attribute.repository` in the Google (left) selectbox.
        3. Write `assertion.repository` in the *OIDC 3* (right) selectbox.

5. Tell the provider what to check. That is, determine what requesters you'll let through.
    1. Click *Add condition*.
    2. Enter a [CEL condition](https://cloud.google.com/iam/docs/workload-identity-federation#conditions) to restrict access. In our case, we want to write `attribute.repository_owner == 'tryolabs'` to allow access to any repo under our GitHub Organization.
6. Click *Save*.

## Bind the WIF Principal to the Service Account

This allows any External Identity Provider that passes any of the Provider checks to impersonate your Service Account.

1. Go to your Service Account by picking it from the page that gets opened when clicking the button below.

    [Service Accounts Page :octicons-hubot-24:](https://console.cloud.google.com/iam-admin/serviceaccounts){ .md-button style="display: block; margin: 0 auto; width: fit-content;" target="_blank"}

2. Grant access.
    1. Click on the *Principals with access* tab.
    2. Click *+ Grant Access*.
    3. In the *New Principals* textbox, paste the principal associated with your Pool.
        In this section, `... = iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/WIF_POOL_NAME`.

        !!! tip "TL;DR"
            If you're following along our tutorial and want to give access to all repos of an organization, replace `PROJECT_NUMBER`, `WIF_POOL_NAME` and `GITHUB_ORGANIZATION_NAME` and use this:

            ```text
            principalSet://.../attribute.repository_owner/GITHUB_ORGANIZATION_NAME
            ```

        You may determine the principal ID using the table below.

        | Grant Method | Example Use Cases | GitHub Principal ID | AWS Principal ID | Kubernetes Principal ID | Azure Principal ID |
        |---|---|---|---|---|---|
        | By Subject | Grant access to the main branch of a single repo or to one specific AWS role. | `principal://.../subject/repo:my-org/my-repo:ref:refs/heads/main` | `principal://.../subject/arn:aws:iam::123456789012:role/MyRole` | `principal://.../subject/system:serviceaccount:my-ns:my-ksa` | `principal://.../subject/a1b2c3d4-5678-90ab-cdef-1234567890ab` |
        | By Attribute | Allow any job from a specific GitHub organization or repo or any role from a specific AWS account. | `principalSet://.../attribute.repository_owner/my-org` or `principalSet://.../attribute.repository/my-org/my-repo` | `principalSet://.../attribute.aws_account/123456789012` | `principalSet://.../attribute.namespace/my-ns` | `principalSet://.../attribute.tenant_id/a1b2c3d4-5678-90ab-cdef-1234567890ab` |
        | By Group | Grant access to any member of the 'DevOps' Okta group or any job run by a member of the 'Backend-Team' in GitHub. | `principalSet://.../group/my-org:my-team` | N/A (Not supported by the AWS provider) | `principalSet://.../group/my-devs` | `principalSet://.../group/a1b2c3d4-5678-90ab-cdef-1234567890ab` |
        | By Pool | Allow any authenticated identity from this pool to have access (i.e., for low-sensitivity dev environments). | `principalSet://.../pools/WIF_POOL_NAME/*` | `principalSet://.../pools/WIF_POOL_NAME/*` | `principalSet://.../pools/WIF_POOL_NAME/*` | `principalSet://.../pools/WIF_POOL_NAME/*` |

        You may find more on Principal IDs in the [Principal Identifiers page](https://cloud.google.com/iam/docs/principal-identifiers).

    4. Select the *Workload Identity User* role from the *Role* selectbox.

        !!! warning
            Do not use the "Service Account User" role. It will fail.

    5. Click *Save*.

## Configure the GitHub Actions YAML

To authenticate to GCP, follow these steps:

1. Add necessary secrets and variables to your repo.
    1. Navigate to your repo in GitHub.
    2. Open the *Settings* tab from the bar up top.
    3. On the bar on the left, click on *Secrets and variables* near the bottom.
    4. Click on *Actions* in the options that appear.
    5. Click on the *Variables* tab.
    6. Add the `GCP_SERVICE_ACCOUNT_EMAIL` variable.
        1. Click on *New repository variable*.
        2. Under name type `GCP_SERVICE_ACCOUNT_EMAIL`.
        3. Under value type `SERVICE_ACCOUNT_EMAIL`.
        4. Click *Add variable*.
    7. Add the `GCP_WORKLOAD_IDENTITY_PROVIDER` variable.
        1. Click on the *New repository variable* button.
        2. Under name type `GCP_WORKLOAD_IDENTITY_PROVIDER`.
        3. Under value type the value of `WIF_PROVIDER_RESOURCE_NAME`.
        4. Click *Add variable*.
2. Add the `auth` step to your Action's YAML file.

    ```YAML
    - name: 'Authenticate to Google Cloud'
      id: 'auth'
      uses: 'google-github-actions/auth@v4'
      with:
        workload_identity_provider: '${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}'  # This is the full Resource Name of your WIF Provider
        service_account: '${{ vars.GCP_SERVICE_ACCOUNT_EMAIL }}'  # This is the email of the SA to impersonate
    ```

[^1]: This is equivalent to navigating to your project's [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) page and clicking *+ Create Service Account*.
[^2]: This is equivalent to navigating to your project's [Workload Identity Pools](https://console.cloud.google.com/iam-admin/workload-identity-pools) page and clicking either *Get started* or *+ Create pool*.
