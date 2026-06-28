"""Document extraction from PDF and PowerPoint files.

This module extracts text and metadata from various document formats:
  - PDF files via PyPDF2
  - PowerPoint presentations via python-pptx
  - Structured metadata extraction
  - Page/slide-level chunking support

All extraction is performed with error resilience and detailed logging.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pptx import Presentation
from PyPDF2 import PdfReader

SLIDE_TITLE_PLACEHOLDER_TYPE = 1
IMAGE_SHAPE_TYPE = 13
TABLE_SHAPE_TYPE = 14

logger = logging.getLogger(__name__)


def _to_iso8601(value: Any) -> str:
    """Convert value to ISO8601 timestamp string.

    Handles datetime objects, strings, and None values gracefully.

    Args:
        value: Value to convert (datetime, str, or other type).

    Returns:
        str: ISO8601 formatted string or empty string if value is None/invalid.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return ""


class DocumentFormat(StrEnum):
    """Supported document formats."""

    PDF = "pdf"
    PPTX = "pptx"
    PPT = "ppt"


class ExtractionError(Exception):
    """Error during document extraction.

    Attributes:
        error_code: Machine-readable error code for diagnostics.
        error_message: Human-readable error description.
        file_path: Path to file that failed extraction.
        file_format: Document format (pdf, pptx, etc.).
        page_number: Page/slide number (if applicable).
    """

    def __init__(
        self,
        error_code: str,
        error_message: str,
        file_path: str,
        file_format: str,
        page_number: int | None = None,
    ) -> None:
        """Initialize ExtractionError.

        Args:
            error_code: Machine-readable error code.
            error_message: Human-readable error message.
            file_path: Path to problematic file.
            file_format: Document format identifier.
            page_number: Optional page/slide number for context.
        """
        self.error_code = error_code
        self.error_message = error_message
        self.file_path = file_path
        self.file_format = file_format
        self.page_number = page_number
        super().__init__(
            f"[{self.error_code}] {self.error_message} "
            f"(file: {self.file_path}, format: {self.file_format})"
        )


@dataclass
class PageMetadata:
    """Metadata for a document page/slide.

    Attributes:
        page_number: 1-based page number.
        page_count: Total pages in document.
        title: Page/slide title if available.
        language: Detected language code (e.g., 'en').
        has_images: Whether page contains images.
        has_tables: Whether page contains tables.
    """

    page_number: int
    page_count: int
    title: str = ""
    language: str = "en"
    has_images: bool = False
    has_tables: bool = False


@dataclass
class DocumentPage:
    """Extracted content from a single page/slide.

    Attributes:
        page_number: 1-based page number.
        text: Extracted text content.
        metadata: Page-level metadata.
        raw_attributes: Format-specific attributes for analysis.
    """

    page_number: int
    text: str
    metadata: PageMetadata
    raw_attributes: dict[str, object] = field(default_factory=dict)

    def word_count(self) -> int:
        """Count words in extracted text.

        Returns:
            int: Number of words.
        """
        return len(self.text.split())

    def character_count(self) -> int:
        """Count characters in extracted text.

        Returns:
            int: Number of characters (excluding whitespace).
        """
        return len(self.text.replace(" ", "").replace("\n", ""))


@dataclass
class DocumentMetadata:
    """Metadata for entire document.

    Attributes:
        file_path: Path to source file.
        file_format: Document format (pdf, pptx, etc.).
        file_size_bytes: Size of file in bytes.
        page_count: Total number of pages/slides.
        title: Document title if available.
        author: Document author if available.
        created_at: Creation timestamp if available.
    """

    file_path: str
    file_format: str
    file_size_bytes: int
    page_count: int
    title: str = ""
    author: str = ""
    created_at: str = ""


@dataclass
class ExtractedDocument:
    """Complete extracted document with all pages and metadata.

    Attributes:
        metadata: Document-level metadata.
        pages: List of extracted pages in order.
    """

    metadata: DocumentMetadata
    pages: list[DocumentPage] = field(default_factory=list)

    def total_words(self) -> int:
        """Calculate total word count across all pages.

        Returns:
            int: Total word count.
        """
        return sum(page.word_count() for page in self.pages)

    def total_characters(self) -> int:
        """Calculate total character count across all pages.

        Returns:
            int: Total character count (excluding whitespace).
        """
        return sum(page.character_count() for page in self.pages)


class PDFExtractor:
    """Extract text and metadata from PDF files."""

    @staticmethod
    def extract(file_path: str) -> ExtractedDocument:
        """Extract all pages from a PDF file.

        Args:
            file_path: Path to PDF file.

        Returns:
            ExtractedDocument: Extracted content and metadata.

        Raises:
            ExtractionError: If PDF extraction fails.
        """
        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                msg = f"File not found: {file_path}"
                raise FileNotFoundError(msg)  # noqa: TRY301

            file_size = file_obj.stat().st_size

            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                page_count = len(reader.pages)

                metadata_dict: dict[str, Any] = cast(dict[str, Any], reader.metadata or {})
                title: str = ""
                author: str = ""
                created: str = ""

                if "/Title" in metadata_dict:
                    title_val = metadata_dict["/Title"]
                    if isinstance(title_val, bytes):
                        title = title_val.decode("utf-8", errors="ignore")
                    elif isinstance(title_val, str):
                        title = title_val

                if "/Author" in metadata_dict:
                    author_val = metadata_dict["/Author"]
                    if isinstance(author_val, bytes):
                        author = author_val.decode("utf-8", errors="ignore")
                    elif isinstance(author_val, str):
                        author = author_val

                if "/CreationDate" in metadata_dict:
                    created_val = metadata_dict["/CreationDate"]
                    if isinstance(created_val, bytes):
                        created = created_val.decode("utf-8", errors="ignore")
                    elif isinstance(created_val, str):
                        created = created_val

                doc_metadata = DocumentMetadata(
                    file_path=file_path,
                    file_format="pdf",
                    file_size_bytes=file_size,
                    page_count=page_count,
                    title=title,
                    author=author,
                    created_at=created,
                )

                pages: list[DocumentPage] = []
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        text = page.extract_text()
                        page_meta = PageMetadata(
                            page_number=page_num,
                            page_count=page_count,
                            has_images=len(page.images) > 0,
                            has_tables=False,
                        )

                        doc_page = DocumentPage(
                            page_number=page_num,
                            text=text,
                            metadata=page_meta,
                            raw_attributes={
                                "rotation": page["/Rotate"],
                                "media_box": page.mediabox,
                            },
                        )
                        pages.append(doc_page)

                        logger.debug(
                            "Extracted PDF page %d/%d: %d chars",
                            page_num,
                            page_count,
                            len(text),
                        )

                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "Failed to extract PDF page %d: %s",
                            page_num,
                            e,
                        )
                        continue

                return ExtractedDocument(metadata=doc_metadata, pages=pages)

        except FileNotFoundError as e:
            msg = f"PDF file not found: {e!s}"
            logger.exception(msg)
            raise ExtractionError(
                error_code="PDF_FILE_NOT_FOUND",
                error_message=msg,
                file_path=file_path,
                file_format="pdf",
            ) from e

        except Exception as e:
            msg = f"Failed to extract PDF: {e!s}"
            logger.exception(msg)
            raise ExtractionError(
                error_code="PDF_EXTRACTION_FAILED",
                error_message=msg,
                file_path=file_path,
                file_format="pdf",
            ) from e


class PowerPointExtractor:
    """Extract text and metadata from PowerPoint presentations."""

    @staticmethod
    def extract(file_path: str) -> ExtractedDocument:
        """Extract all slides from a PowerPoint file.

        Args:
            file_path: Path to PPTX/PPT file.

        Returns:
            ExtractedDocument: Extracted content and metadata.

        Raises:
            ExtractionError: If PowerPoint extraction fails.
        """
        try:
            file_obj = Path(file_path)
            if not file_obj.exists():
                msg = f"File not found: {file_path}"
                raise FileNotFoundError(msg)  # noqa: TRY301

            file_size = file_obj.stat().st_size
            presentation = Presentation(file_path)

            slide_count = len(presentation.slides)
            title_val: Any = presentation.core_properties.title or ""
            author_val: Any = presentation.core_properties.author or ""
            created_val: Any = getattr(presentation.core_properties, "created", None)  # type: ignore[assignment]

            title_str: str = str(title_val) if title_val else ""
            author_str: str = str(author_val) if author_val else ""
            created_str: str = _to_iso8601(created_val)

            doc_metadata = DocumentMetadata(
                file_path=file_path,
                file_format="pptx",
                file_size_bytes=file_size,
                page_count=slide_count,
                title=title_str,
                author=author_str,
                created_at=created_str,
            )

            pages: list[DocumentPage] = []
            for slide_num, slide in enumerate(presentation.slides, start=1):
                try:
                    text_content = PowerPointExtractor._extract_slide_text(slide)
                    has_images = PowerPointExtractor._has_images_in_slide(slide)
                    has_tables = PowerPointExtractor._has_tables_in_slide(slide)

                    slide_title: str = PowerPointExtractor._extract_slide_title(slide)

                    page_meta = PageMetadata(
                        page_number=slide_num,
                        page_count=slide_count,
                        title=slide_title,
                        has_images=has_images,
                        has_tables=has_tables,
                    )

                    doc_page = DocumentPage(
                        page_number=slide_num,
                        text=text_content,
                        metadata=page_meta,
                        raw_attributes={
                            "shape_count": len(slide.shapes),
                            "has_speaker_notes": (
                                len(
                                    getattr(
                                        getattr(
                                            getattr(slide, "notes_slide", None),
                                            "notes_text_frame",
                                            None,
                                        ),
                                        "text",
                                        "",
                                    )
                                )
                                > 0
                            ),
                        },
                    )
                    pages.append(doc_page)

                    logger.debug(
                        "Extracted PowerPoint slide %d/%d: %d chars",
                        slide_num,
                        slide_count,
                        len(text_content),
                    )

                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "Failed to extract PowerPoint slide %d: %s",
                        slide_num,
                        e,
                    )
                    continue

            return ExtractedDocument(metadata=doc_metadata, pages=pages)

        except FileNotFoundError as e:
            msg = f"PowerPoint file not found: {e!s}"
            logger.exception(msg)
            raise ExtractionError(
                error_code="PPTX_FILE_NOT_FOUND",
                error_message=msg,
                file_path=file_path,
                file_format="pptx",
            ) from e

        except Exception as e:
            msg = f"Failed to extract PowerPoint: {e!s}"
            logger.exception(msg)
            raise ExtractionError(
                error_code="PPTX_EXTRACTION_FAILED",
                error_message=msg,
                file_path=file_path,
                file_format="pptx",
            ) from e

    @staticmethod
    def _extract_slide_text(slide: object) -> str:
        """Extract text from all shapes in a slide.

        Args:
            slide: python-pptx Slide object.

        Returns:
            str: Concatenated text from slide.
        """
        text_parts: list[str] = []
        shapes: Any = getattr(slide, "shapes", [])
        for shape in shapes:
            if hasattr(shape, "text"):
                shape_text: Any = getattr(shape, "text", "")
                if isinstance(shape_text, str) and shape_text:
                    text_parts.append(shape_text)
        return "\n".join(text_parts)

    @staticmethod
    def _extract_slide_title(slide: object) -> str:
        """Extract title from slide.

        Args:
            slide: python-pptx Slide object.

        Returns:
            str: Slide title if available.
        """
        try:
            shapes: Any = getattr(slide, "shapes", None)
            if shapes is None:
                return ""

            for shape in shapes:
                is_placeholder: bool = getattr(shape, "is_placeholder", False)
                if is_placeholder:
                    placeholder_format: Any = getattr(shape, "placeholder_format", None)
                    if placeholder_format is not None:
                        phf_type: Any = getattr(placeholder_format, "type", None)
                        if phf_type == SLIDE_TITLE_PLACEHOLDER_TYPE:
                            title_text: Any = getattr(shape, "text", "")
                            if isinstance(title_text, str):
                                return title_text
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to extract title shape: %s", e)
        return ""

    @staticmethod
    def _has_images_in_slide(slide: object) -> bool:
        """Check if slide contains images.

        Args:
            slide: python-pptx Slide object.

        Returns:
            bool: True if slide has image shapes.
        """
        try:
            for shape in slide.shapes:  # type: ignore[attr-defined]
                if (
                    shape.shape_type == IMAGE_SHAPE_TYPE  # type: ignore[attr-defined]
                ):  # Picture shape type
                    return True
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to extract shape: %s", e)
            return False
        return False

    @staticmethod
    def _has_tables_in_slide(slide: object) -> bool:
        """Check if slide contains tables.

        Args:
            slide: python-pptx Slide object.

        Returns:
            bool: True if slide has table shapes.
        """
        try:
            for shape in slide.shapes:  # type: ignore[attr-defined]
                if (
                    shape.shape_type == TABLE_SHAPE_TYPE  # type: ignore[attr-defined]
                ):  # Table shape type
                    return True
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to extract shape: %s", e)
            return False
        return False


class DocumentExtractor:
    """Main document extraction orchestrator.

    Supports multiple formats and delegates to format-specific extractors.
    """

    @staticmethod
    def detect_format(file_path: str) -> DocumentFormat:
        """Detect document format from file extension.

        Args:
            file_path: Path to document file.

        Returns:
            DocumentFormat: Detected format.

        Raises:
            ExtractionError: If format not supported.
        """
        suffix = Path(file_path).suffix.lower()
        suffix_map: dict[str, DocumentFormat] = {
            ".pdf": DocumentFormat.PDF,
            ".pptx": DocumentFormat.PPTX,
            ".ppt": DocumentFormat.PPT,
        }

        if suffix not in suffix_map:
            msg = f"Unsupported file format: {suffix}. Supported: {', '.join(suffix_map.keys())}"
            raise ExtractionError(
                error_code="UNSUPPORTED_FORMAT",
                error_message=msg,
                file_path=file_path,
                file_format=suffix,
            )

        return suffix_map[suffix]

    @staticmethod
    def extract(file_path: str) -> ExtractedDocument:
        """Extract document based on detected format.

        Args:
            file_path: Path to document file.

        Returns:
            ExtractedDocument: Extracted content and metadata.

        Raises:
            ExtractionError: If extraction fails.
        """
        doc_format = DocumentExtractor.detect_format(file_path)

        logger.info("Extracting document: %s (format: %s)", file_path, doc_format)

        if doc_format == DocumentFormat.PDF:
            return PDFExtractor.extract(file_path)
        if doc_format in (DocumentFormat.PPTX, DocumentFormat.PPT):
            return PowerPointExtractor.extract(file_path)
        msg = f"Unsupported format: {doc_format}"
        raise ExtractionError(
            error_code="UNSUPPORTED_FORMAT",
            error_message=msg,
            file_path=file_path,
            file_format=str(doc_format),
        )

    @staticmethod
    def batch_extract(
        file_paths: list[str],
    ) -> list[tuple[str, ExtractedDocument | ExtractionError]]:
        """Extract multiple documents with error resilience.

        Args:
            file_paths: List of file paths to extract.

        Returns:
            list: Tuples of (file_path, result or error).
                  Results always include one element per input file.
        """
        results: list[tuple[str, ExtractedDocument | ExtractionError]] = []

        for file_path in file_paths:
            try:
                doc = DocumentExtractor.extract(file_path)
                results.append((file_path, doc))
                logger.info(
                    "Successfully extracted %s (%d pages)",
                    file_path,
                    len(doc.pages),
                )

            except ExtractionError as e:
                results.append((file_path, e))
                logger.exception("Extraction failed for %s", file_path)

            except Exception as e:
                error = ExtractionError(
                    error_code="EXTRACTION_FAILED",
                    error_message=str(e),
                    file_path=file_path,
                    file_format="unknown",
                )
                results.append((file_path, error))
                logger.exception("Unexpected error extracting %s", file_path)

        return results
