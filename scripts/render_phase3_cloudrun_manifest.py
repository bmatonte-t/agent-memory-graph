"""Render Phase 3 Cloud Run manifest from template placeholders."""

from __future__ import annotations

import argparse
from pathlib import Path


def render_manifest(
    template_path: Path,
    output_path: Path,
    project_id: str,
    image_tag: str,
    region: str,
    artifact_repository: str,
    image_name: str,
    service_name: str,
) -> None:
    """Render Cloud Run YAML template using provided variables.

    Args:
        template_path: Path to template YAML file.
        output_path: Path to write rendered YAML.
        project_id: Google Cloud project identifier.
        image_tag: Container image tag.
        region: Cloud Run and Artifact Registry region.
        artifact_repository: Artifact Registry repository name.
        image_name: Container image name.
        service_name: Cloud Run service name.
    """
    template = template_path.read_text(encoding="utf-8")
    rendered = (
        template.replace("PROJECT_ID", project_id)
        .replace("IMAGE_TAG", image_tag)
        .replace("REGION", region)
        .replace("ARTIFACT_REPOSITORY", artifact_repository)
        .replace("IMAGE_NAME", image_name)
        .replace("SERVICE_NAME", service_name)
    )
    output_path.write_text(rendered, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for rendering Cloud Run manifest.

    Returns:
        argparse.ArgumentParser: Parser for CLI arguments.
    """
    parser = argparse.ArgumentParser(description="Render Phase 3 Cloud Run service manifest.")
    parser.add_argument("--project-id", required=True, help="Google Cloud project id")
    parser.add_argument("--image-tag", default="latest", help="Container image tag")
    parser.add_argument("--region", default="us-central1", help="Cloud Run region")
    parser.add_argument(
        "--artifact-repository",
        default="agent-memory-graph",
        help="Artifact Registry repository",
    )
    parser.add_argument("--image-name", default="phase3", help="Container image name")
    parser.add_argument(
        "--service-name",
        default="agent-memory-graph-phase3",
        help="Cloud Run service name",
    )
    parser.add_argument(
        "--template",
        default="infrastructure/phase3/cloudrun-service.yaml",
        help="Template YAML path",
    )
    parser.add_argument(
        "--output",
        default="infrastructure/phase3/cloudrun-service.rendered.yaml",
        help="Rendered YAML output path",
    )
    return parser


def main() -> None:
    """CLI entrypoint for manifest rendering."""
    parser = build_parser()
    args = parser.parse_args()

    render_manifest(
        template_path=Path(args.template),
        output_path=Path(args.output),
        project_id=args.project_id,
        image_tag=args.image_tag,
        region=args.region,
        artifact_repository=args.artifact_repository,
        image_name=args.image_name,
        service_name=args.service_name,
    )


if __name__ == "__main__":
    main()
