# Coding Agents

The template includes a comprehensive coding agent setup for GitHub Copilot that helps enforce coding standards, provides context-aware assistance, and streamlines code review workflows.

The template organizes agent configuration files in the [`.github/`](https://github.com/tryolabs/repo-template/tree/main/.github) directory.

## Overview

Coding agents are AI-powered assistants that understand your codebase's specific conventions and requirements. The template configures GitHub Copilot with:

- **Global instructions** that apply across your entire project. These are always active.
- **Scoped instructions** that adapt based on the file you're working in.
- **Custom specialized agents** for specific workflows like code review.

!!! tip "Adding Your Own Scoped Instructions"
    Create new instruction files in `.github/instructions/` with the `.instructions.md` extension and YAML frontmatter specifying the `applyTo` pattern:

    ```yaml
    ---
    applyTo: "src/api/**/*.py"
    ---

    # API-specific guidelines...
    ```

This ensures that Copilot provides consistent, project-aware suggestions that follow your team's established patterns and practices.

The **`.github/agents/`** directory contains specialized agents for specific workflows.

## Using the Coding Agents

### Automatic Context

When you work on files in your repository, GitHub Copilot automatically loads:

1. Global instructions from `.github/copilot-instructions.md`.
2. Any scoped instructions matching the current file's path pattern.

This means you get context-aware suggestions without any extra steps.

### Invoking Custom Agents

To use a specialized agent like the code review agent:

1. Open GitHub Copilot Chat.
2. Reference the agent with `@code-review` or use the Copilot agent picker.
3. Provide context about what to review.
4. The agent will follow its specialized workflow and provide structured output.

!!! example "Using the Code Review Agent"
    After implementing a new feature:

    ```
    @code-review Please review the authentication implementation in src/auth.py. It should handle OAuth2 flow with proper error handling and token refresh.
    ```

## Customization

The template's coding agent setup is designed to be customized for your specific project needs.

### Updating Global Instructions

Edit `.github/copilot-instructions.md`.

### Modifying Scoped Instructions

Update files in `.github/instructions/`.

### Creating New Agents

To create a new specialized agent:

1. Create a new `.agent.md` file in `.github/agents/`.
2. Add YAML frontmatter with name, description, and tools.
3. Define the agent's purpose and workflow.
4. Specify the expected output format.

Example structure:

```yaml
---
name: security-audit
description: 'Perform security analysis on code changes.'
tools: ['search', 'read']
---

You are a SECURITY AUDIT AGENT...

[Define workflow and output format]
```

## Best Practices

### Writing Effective Instructions

- **Be specific:** Instead of "write good code," specify "use type hints for all function parameters and return values".
- **Provide examples:** Show the preferred pattern when possible.
- **Keep updated:** Review and revise instructions as your practices evolve.

### Scoped vs. Global

- **Global:** Conventions that apply everywhere (tooling, general principles).
- **Scoped:** Context-specific guidance (testing patterns for test files, API conventions for API code).

### Agent Design

- **Single responsibility:** Each agent should have one clear purpose.
- **Structured output:** Define consistent output formats for predictable results.
- **Tool restrictions:** Limit agents to only the tools they need (e.g., read-only agents shouldn't need edit tools).

## Further Reading

- [GitHub Copilot Agent Customization Documentation](https://code.visualstudio.com/docs/copilot/copilot-customization)
- [Writing Effective Instructions for AI Coding Assistants](https://github.blog/developer-skills/github/how-to-write-better-prompts-for-github-copilot/)
