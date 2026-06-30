# Generic Enterprise Presentations

This folder contains client-agnostic presentations of Agent Memory Graph, suitable for positioning the product to any enterprise customer. All LATAM Airlines-specific references and internal platform integrations (Cosmos, DataHub, ADO) have been removed and generalized.

## Three Decks Included

### 1. Executive Presentation (`executive-presentation.html`)

**Audience**: C-suite executives, product leads, decision makers

**Duration**: 8–10 slides | **Format**: HTML (print to PDF, landscape orientation)

**Content**:
- Business problem (agents without shared context)
- Customer value (eliminate hallucination, reduce token spend, preserve compliance)
- Generic enterprise use cases (multi-agent coordination across finance, operations, analytics)
- Deployment model (project-based architecture for any organization)
- ROI and time-to-value

**How to customize**:
- Replace `[Your Company Name]` tokens with the actual customer name
- Adjust use-case examples to match customer's domain
- Update contact/footer information

### 2. Engineers Deep Dive (`engineers-deep-dive.html`)

**Audience**: Data engineers, ML engineers, platform engineers

**Duration**: 12–14 slides | **Format**: HTML (print to PDF, landscape orientation)

**Content**:
- System architecture (tripartite memory, MindMap pipeline)
- Technical stack (Python, FastAPI, Cloud Spanner Graph, MCP protocol)
- API surface and integration patterns
- Code quality metrics (843 tests, 93.6% docstring coverage, 0 type errors)
- Deployment and operations

**How to customize**:
- Point to customer's GCP project IDs
- Adapt integration examples to customer's LLM choices
- Highlight specific deployment topology (dev/intg/prod or multi-team)

### 3. Technical Stakeholders (`technical-stakeholders.html`)

**Audience**: Architects, DevOps, security teams, platform leads

**Duration**: 10–12 slides | **Format**: HTML (print to PDF, landscape orientation)

**Content**:
- Technical problem statement (stateless models, coordination gaps, auditability)
- System design and data flow
- Security architecture (ABAC, tenant isolation, audit trails)
- Integration points and APIs
- Deployment topology and operational considerations

**How to customize**:
- Adapt security model to match customer's compliance requirements
- Update deployment examples to customer's infrastructure setup
- Highlight governance and policy integration points

## Design Specifications

- **Color scheme**: Indigo (#4257E8) and Coral (#ED1650) — professional, accessible, WCAG AA compliant
- **Typography**: Sans-serif (Tailwind defaults)
- **Orientation**: Landscape (A4, 16:9 aspect ratio)
- **Export**: Print to PDF via browser (`Cmd+P` / `Ctrl+P`)

## How to Use

1. **Open in browser**: Double-click any HTML file or open via `file:///` URL
2. **Scroll through slides**: Each presentation can be viewed sequentially
3. **Print to PDF**:
   - Press `Cmd+P` (macOS) or `Ctrl+P` (Windows/Linux)
   - Select **Orientation: Landscape**
   - Save as PDF
4. **Present online**: Open in browser, press `F11` for fullscreen, use arrow keys to navigate

## White-Labeling Guide

To fully customize these presentations for a specific customer:

1. **Create a copy** of this folder: `reports/generic-enterprise-[CustomerName]/`
2. **Update branding**:
   - Replace generic company references with the customer's name
   - Update slide numbers and footer text
   - Adjust use-case examples to customer's industry
3. **Customize architecture**:
   - Point deployment examples to customer's GCP projects/regions
   - Highlight customer-specific integrations
   - Reference customer's existing tools/platforms
4. **Print and deliver**: Export each deck to PDF per the instructions above

## File Naming Convention

Generic presentations use ISO date-agnostic names:
- `executive-presentation.html`
- `engineers-deep-dive.html`
- `technical-stakeholders.html`

Customer-specific versions should use:
- `executive-presentation-[CustomerName].html`
- `engineers-deep-dive-[CustomerName].html`
- `technical-stakeholders-[CustomerName].html`

## Versioning

These presentations are generated from the current state of the Agent Memory Graph codebase. Update them when:
- Major features ship (new MCP tools, pipeline stages, etc.)
- Code quality metrics improve significantly
- Deployment model changes
- Security model updates

Current version reflects: **Agent Memory Graph v0.2 · Production-Ready**

## Support

For questions about customizing these presentations or adapting them for a specific customer, refer to:
- Architecture documentation: [docs/architecture.md](../../docs/architecture.md)
- API reference: [docs/user-guide/api-reference.md](../../docs/user-guide/api-reference.md)
- Deployment guide: [docs/deployment.md](../../docs/deployment.md)
