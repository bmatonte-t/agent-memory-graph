# Initialization Modes

When initializing the template, you'll be prompted to select an initialization mode. The template supports three modes with different quality vs speed tradeoffs to match your project's needs.

These modes are simply collections of curated configurations that are more or less permissive. In line with the template's ethos, you can always adjust individual settings after initialization by editing the generated configuration files. The mode just sets sensible defaults for your use case.

!!! note
    For detailed technical information about how modes work and how to modify them, see the [Initialization Modes Development Guide](../development/initialization_modes.md).

## Mode Overview

| Dimension | `poc` | `normal` | `long-term` |
| --- | --- | --- | --- |
| **Summary** | Fast prototyping with guardrails. | Balanced quality and velocity. | Production-grade quality. |
| **Type Checking** | Basic (catches obvious errors). | A bit more stringent. | Strict (comprehensive type hints required). |
| **Test Coverage** | 0% required (reports still generated). | 60% required. | 85% required. |
| **Docstring Coverage** | 25% required. | 80% required. | 90% required. |
| **Linting** | Relaxed (allows for some "slop"). | Comprehensive with sensible defaults. | Strict with minimal exceptions. |
| **Best For** | Experiments and proof-of-concepts; hackathons; learning; short-lived prototypes. | Most projects and MVPs; team collaboration; medium-lifespan projects; standard workflows. | Production systems; critical services and infrastructure; public libraries and packages; long-lived projects. |

## Choosing the Right Mode

There are several factors to consider when choosing a mode. Here we offer some *guidance*, but feel free to stray from these recommendations as this documentation can't possibly contemplate the full reality of every project.

!!! tip
    We recommend you use `normal` mode if you don't have any strong reasons to prefer another mode.

### Project Lifespan

Do we expect to have to maintain the project in the long term, or is this just a small PoC? Here are some guidelines:

- Short-term (days/weeks): `poc`.
- Medium-term (months-few years): `normal`.
- Long-term (years): `long-term`.

### Team Size

The bigger the team, the more we need to enforce good practices and follow a standard, so our efforts can be focused on delivering real impact and not on irrelevant style or correctness discussions.

!!! quote "As `black` best puts it"
    (...) By using (`black`), you agree to cede control over minutiae of hand-formatting. In return, Black gives you speed, determinism, and freedom (...). You will save time and mental energy for more important matters.

    Blackened code looks the same regardless of the project you're reading. Formatting becomes transparent after a while and you can focus on the content instead.

- Solo/small team (1-2): `poc` or `normal`.
- Medium team (3-5): `normal`.
- Large team (6+): `normal` or `long-term`.

### Project Criticality

The more critical the project is to the client or Tryolabs, the more stringent we have to be with our rules. Think about what would happen if the project fails, or if it becomes excruciating to maintain due to poor quality and design.

- Experimental: `poc`.
- Internal tools or typical production workloads: `normal`.
- Stuff that can't fail: `long-term`.

### Development Speed Priority

While style, formatting, type and linting checks help increase code quality and uniformity, they can also slow down progress. Sometimes, this isn't necessary, so if you're sure you need blazing delivery, consider lower modes.

- Speed > Quality: `poc`.
- Balanced: `normal`.
- Quality > Speed: `long-term`.
