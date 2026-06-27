"""POLE+O entity classifier using Gemini for BigQuery columns.

Classifies BigQuery columns into POLE+O entity types (People, Objects,
Locations, Events, Organizations) using Gemini structured outputs.
Supports multi-label classification (e.g., a column can be both OBJECT
and TEMPORAL).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import vertexai
from pydantic import BaseModel, Field
from vertexai.generative_models import GenerativeModel, Part

if TYPE_CHECKING:
    from src.pipelines.bigquery_ingestion.schema_analyzer import (
        TableMetadata,
    )

logger = logging.getLogger(__name__)


# POLE+O Entity Types
POLE_ENTITY_TYPES = [
    "PERSON",
    "OBJECT",
    "LOCATION",
    "EVENT",
    "ORGANIZATION",
    "TEMPORAL",
    "IDENTIFIER",
    "CATEGORY",
    "NUMERIC",
    "RELATIONSHIP",
]


class ColumnClassification(BaseModel):
    """Classification result for a single column."""

    column_name: str
    column_type: str
    entity_types: list[str] = Field(
        description="Multi-label entity types (e.g., ['PERSON', 'IDENTIFIER'])"
    )
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence 0.0-1.0")
    rationale: str = Field(description="Reasoning for classification")


class TableClassification(BaseModel):
    """Classification result for entire table."""

    table_id: str
    dataset_id: str
    project_id: str
    classified_columns: list[ColumnClassification]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    classification_timestamp: str


class ClassificationCache:
    """Simple in-memory cache for POLE+O classifications (2-week TTL)."""

    def __init__(self, ttl_hours: int = 336) -> None:
        """Initialize cache with TTL (default 2 weeks = 336 hours).

        Args:
            ttl_hours: Time-to-live in hours.
        """
        self.cache: dict[str, tuple[TableClassification, datetime]] = {}
        self.ttl = timedelta(hours=ttl_hours)

    def get(self, cache_key: str) -> TableClassification | None:
        """Get cached classification if exists and not expired.

        Args:
            cache_key: Cache key (e.g., "project.dataset.table").

        Returns:
            Cached classification or None if expired/missing.
        """
        if cache_key not in self.cache:
            return None

        cached_result, cached_time = self.cache[cache_key]
        if datetime.now(UTC) - cached_time > self.ttl:
            del self.cache[cache_key]
            logger.debug("Cache expired for %s", cache_key)
            return None

        logger.debug("Cache hit for %s", cache_key)
        return cached_result

    def set(self, cache_key: str, result: TableClassification) -> None:
        """Store classification in cache.

        Args:
            cache_key: Cache key.
            result: Classification result to cache.
        """
        self.cache[cache_key] = (result, datetime.now(UTC))
        logger.debug("Cached classification for %s", cache_key)

    def clear(self) -> None:
        """Clear entire cache."""
        self.cache.clear()
        logger.debug("Cleared classification cache")


class POLEClassifier:
    """Classifies BigQuery columns using Gemini 2.5 Flash.

    Uses structured outputs to enforce consistent multi-label
    classification into POLE+O entity types.
    """

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "gemini-2.5-flash",
        cache: ClassificationCache | None = None,
    ) -> None:
        """Initialize POLE+O classifier.

        Args:
            project_id: GCP project ID for Vertex AI.
            location: Vertex AI location.
            model_name: Gemini model to use.
            cache: Classification cache instance.
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.cache = cache or ClassificationCache()

        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model_name)

    def classify_columns(
        self,
        table_metadata: TableMetadata,
        sample_rows: list[dict[str, object]] | None = None,
    ) -> TableClassification:
        """Classify columns in a table.

        Args:
            table_metadata: Table schema metadata.
            sample_rows: Sample rows for context (optional).

        Returns:
            TableClassification with multi-label entity types.

        Raises:
            ValueError: If classification fails.
        """
        cache_key = (
            f"{table_metadata.project_id}.{table_metadata.dataset_id}.{table_metadata.table_id}"
        )

        # Check cache first
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        logger.info("Classifying columns for table %s", cache_key)

        # Prepare context for Gemini
        column_descriptions = "\n".join(
            [f"- {col.name} ({col.field_type}, mode={col.mode})" for col in table_metadata.columns]
        )

        sample_data = ""
        if sample_rows:
            sample_data = "\n\nSample rows (first 3):\n" + json.dumps(
                sample_rows[:3], indent=2, default=str
            )

        prompt = (
            "You are a data analyst expert in entity classification "
            "using the POLE+O framework.\n\n"
            "Classify each column in the following BigQuery table into "
            "one or more POLE+O entity types:\n"
            "- PERSON: Individual people, names, employees, customers\n"
            "- OBJECT: Physical or abstract objects, products, devices\n"
            "- LOCATION: Geographic locations, addresses, regions\n"
            "- EVENT: Events, transactions, activities, actions\n"
            "- ORGANIZATION: Companies, departments, teams, groups\n"
            "- TEMPORAL: Dates, times, timestamps\n"
            "- IDENTIFIER: IDs, codes, unique identifiers\n"
            "- CATEGORY: Categories, statuses, types, classifications\n"
            "- NUMERIC: Measurements, counts, amounts\n"
            "- RELATIONSHIP: Represents relationships between entities\n"
            f"\nTable: {table_metadata.dataset_id}."
            f"{table_metadata.table_id}\n\n"
            f"Columns:\n{column_descriptions}{sample_data}\n\n"
            "For each column, provide:\n"
            "1. The entity types (choose 1-3 that best describe)\n"
            "2. A confidence score (0.0-1.0)\n"
            "3. Brief rationale\n\n"
            "You must return valid JSON matching the schema."
        )

        try:
            # Call Gemini with structured outputs
            response = self.model.generate_content(
                [
                    Part.from_text(prompt),
                ],
                generation_config={
                    "response_mime_type": "application/json",
                    "response_schema": {
                        "type": "object",
                        "properties": {
                            "classifications": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "column_name": {"type": "string"},
                                        "entity_types": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "confidence_score": {"type": "number"},
                                        "rationale": {"type": "string"},
                                    },
                                    "required": [
                                        "column_name",
                                        "entity_types",
                                        "confidence_score",
                                        "rationale",
                                    ],
                                },
                            },
                            "overall_confidence": {"type": "number"},
                        },
                        "required": [
                            "classifications",
                            "overall_confidence",
                        ],
                    },
                },
            )

            # Parse response
            response_json = json.loads(response.text)
            classified_columns: list[ColumnClassification] = []

            for item in response_json.get("classifications", []):
                # Match column schema
                col_schema = next(
                    (c for c in table_metadata.columns if c.name == item["column_name"]),
                    None,
                )
                if not col_schema:
                    logger.warning(
                        "Column %s not found in schema",
                        item["column_name"],
                    )
                    continue

                classification = ColumnClassification(
                    column_name=item["column_name"],
                    column_type=col_schema.field_type,
                    entity_types=item["entity_types"],
                    confidence_score=item["confidence_score"],
                    rationale=item["rationale"],
                )
                classified_columns.append(classification)

            # Create result
            result = TableClassification(
                table_id=table_metadata.table_id,
                dataset_id=table_metadata.dataset_id,
                project_id=table_metadata.project_id,
                classified_columns=classified_columns,
                overall_confidence=response_json.get("overall_confidence", 0.8),
                classification_timestamp=datetime.now(UTC).isoformat(),
            )

            # Cache result
            self.cache.set(cache_key, result)

            logger.info(
                "Classified %d columns for %s (confidence=%.2f)",
                len(classified_columns),
                cache_key,
                result.overall_confidence,
            )

        except Exception as e:
            msg = f"Failed to classify columns for {cache_key}: {e!s}"
            logger.exception(msg)
            raise ValueError(msg) from e
        else:
            return result
