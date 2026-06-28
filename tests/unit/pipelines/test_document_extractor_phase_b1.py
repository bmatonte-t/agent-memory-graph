"""Unit tests for Phase B1: Document Extractor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipelines.document_ingestion.document_extractor import (
    DocumentExtractor,
    DocumentFormat,
    DocumentMetadata,
    DocumentPage,
    ExtractedDocument,
    ExtractionError,
    PageMetadata,
    PDFExtractor,
    PowerPointExtractor,
)

# Test constants
SAMPLE_PDF_PATH = "/tmp/sample.pdf"
SAMPLE_PPTX_PATH = "/tmp/sample.pptx"
SAMPLE_PPT_PATH = "/tmp/sample.ppt"
UNSUPPORTED_FILE_PATH = "/tmp/sample.txt"
NONEXISTENT_FILE_PATH = "/tmp/nonexistent.pdf"
EXTRACTED_TEXT_SHORT = "Sample PDF text"
EXTRACTED_TEXT_MEDIUM = "This is a longer sample text for testing"
EXTRACTED_TEXT_LONG = " ".join(["word"] * 100)
EXPECTED_WORD_COUNT = 100
EXPECTED_CHAR_COUNT = 400  # "word" * 100 without spaces
PDF_FILE_SIZE = 4096
PAGE_NUMBER_TWO = 2
WORD_COUNT_THREE = 3
CHAR_COUNT_TEN = 10
WORD_COUNT_FIVE = 5
BATCH_SIZE_TWO = 2
PPTX_FILE_SIZE = 8192
PAGE_COUNT_SINGLE = 1
PAGE_COUNT_MULTIPLE = 5
SLIDE_COUNT = 3
TITLE_PDF = "Test PDF Document"
AUTHOR_PDF = "Test Author"
TITLE_PPTX = "Test Presentation"
FIRST_PAGE_NUMBER = 1
SECOND_PAGE_NUMBER = 2


class TestDocumentFormat:
    """Tests for DocumentFormat enum."""

    def test_format_pdf(self) -> None:
        """Test PDF format value."""
        assert DocumentFormat.PDF.value == "pdf"

    def test_format_pptx(self) -> None:
        """Test PPTX format value."""
        assert DocumentFormat.PPTX.value == "pptx"

    def test_format_ppt(self) -> None:
        """Test PPT format value."""
        assert DocumentFormat.PPT.value == "ppt"


class TestExtractionError:
    """Tests for ExtractionError exception."""

    def test_initialization_basic(self) -> None:
        """Test ExtractionError initialization without page number."""
        error = ExtractionError(
            error_code="PDF_EXTRACTION_FAILED",
            error_message="Failed to read PDF",
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
        )

        assert error.error_code == "PDF_EXTRACTION_FAILED"
        assert error.error_message == "Failed to read PDF"
        assert error.file_path == SAMPLE_PDF_PATH
        assert error.file_format == "pdf"
        assert error.page_number is None

    def test_initialization_with_page(self) -> None:
        """Test ExtractionError initialization with page number."""
        error = ExtractionError(
            error_code="PAGE_EXTRACTION_FAILED",
            error_message="Failed to extract page",
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            page_number=2,
        )

        assert error.page_number == PAGE_NUMBER_TWO

    def test_error_message_formatting(self) -> None:
        """Test error message includes all context."""
        error = ExtractionError(
            error_code="TEST_CODE",
            error_message="Test message",
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
        )

        error_str = str(error)
        assert "TEST_CODE" in error_str
        assert "Test message" in error_str
        assert SAMPLE_PDF_PATH in error_str
        assert "pdf" in error_str


class TestPageMetadata:
    """Tests for PageMetadata dataclass."""

    def test_initialization_basic(self) -> None:
        """Test basic PageMetadata initialization."""
        meta = PageMetadata(
            page_number=FIRST_PAGE_NUMBER,
            page_count=PAGE_COUNT_SINGLE,
        )

        assert meta.page_number == FIRST_PAGE_NUMBER
        assert meta.page_count == PAGE_COUNT_SINGLE
        assert meta.title == ""
        assert meta.language == "en"
        assert meta.has_images is False
        assert meta.has_tables is False

    def test_initialization_full(self) -> None:
        """Test PageMetadata initialization with all fields."""
        meta = PageMetadata(
            page_number=2,
            page_count=5,
            title="Chapter 1",
            language="es",
            has_images=True,
            has_tables=True,
        )

        assert meta.page_number == PAGE_NUMBER_TWO
        assert meta.title == "Chapter 1"
        assert meta.language == "es"
        assert meta.has_images is True
        assert meta.has_tables is True


class TestDocumentPage:
    """Tests for DocumentPage dataclass."""

    def test_initialization(self) -> None:
        """Test DocumentPage initialization."""
        meta = PageMetadata(page_number=1, page_count=1)
        page = DocumentPage(
            page_number=1,
            text=EXTRACTED_TEXT_MEDIUM,
            metadata=meta,
        )

        assert page.page_number == 1
        assert page.text == EXTRACTED_TEXT_MEDIUM
        assert page.metadata == meta

    def test_word_count(self) -> None:
        """Test word counting."""
        meta = PageMetadata(page_number=1, page_count=1)
        page = DocumentPage(
            page_number=1,
            text="hello world test",
            metadata=meta,
        )

        assert page.word_count() == WORD_COUNT_THREE

    def test_character_count(self) -> None:
        """Test character counting without spaces."""
        meta = PageMetadata(page_number=1, page_count=1)
        page = DocumentPage(
            page_number=1,
            text="hello world",
            metadata=meta,
        )

        assert page.character_count() == CHAR_COUNT_TEN  # "helloworld"


class TestDocumentMetadata:
    """Tests for DocumentMetadata dataclass."""

    def test_initialization_basic(self) -> None:
        """Test basic DocumentMetadata initialization."""
        meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=PAGE_COUNT_SINGLE,
        )

        assert meta.file_path == SAMPLE_PDF_PATH
        assert meta.file_format == "pdf"
        assert meta.file_size_bytes == PDF_FILE_SIZE
        assert meta.page_count == PAGE_COUNT_SINGLE
        assert meta.title == ""
        assert meta.author == ""

    def test_initialization_full(self) -> None:
        """Test DocumentMetadata initialization with all fields."""
        meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=PAGE_COUNT_MULTIPLE,
            title=TITLE_PDF,
            author=AUTHOR_PDF,
            created_at="2026-01-01T00:00:00",
        )

        assert meta.title == TITLE_PDF
        assert meta.author == AUTHOR_PDF
        assert meta.created_at == "2026-01-01T00:00:00"


class TestExtractedDocument:
    """Tests for ExtractedDocument dataclass."""

    def test_initialization(self) -> None:
        """Test ExtractedDocument initialization."""
        doc_meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=PAGE_COUNT_SINGLE,
        )
        doc = ExtractedDocument(metadata=doc_meta)

        assert doc.metadata == doc_meta
        assert len(doc.pages) == 0

    def test_total_words(self) -> None:
        """Test total word count calculation."""
        doc_meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=2,
        )
        page_meta1 = PageMetadata(page_number=1, page_count=2)
        page1 = DocumentPage(page_number=1, text="hello world", metadata=page_meta1)

        page_meta2 = PageMetadata(page_number=2, page_count=2)
        page2 = DocumentPage(
            page_number=2,
            text="foo bar baz",
            metadata=page_meta2,
        )

        doc = ExtractedDocument(metadata=doc_meta, pages=[page1, page2])
        assert doc.total_words() == WORD_COUNT_FIVE

    def test_total_characters(self) -> None:
        """Test total character count calculation."""
        doc_meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=2,
        )
        page_meta1 = PageMetadata(page_number=1, page_count=2)
        page1 = DocumentPage(page_number=1, text="hello", metadata=page_meta1)

        page_meta2 = PageMetadata(page_number=2, page_count=2)
        page2 = DocumentPage(page_number=2, text="world", metadata=page_meta2)

        doc = ExtractedDocument(metadata=doc_meta, pages=[page1, page2])
        assert doc.total_characters() == CHAR_COUNT_TEN  # "helloworld"


class TestDocumentExtractorFormatDetection:
    """Tests for DocumentExtractor format detection."""

    def test_detect_pdf_format(self) -> None:
        """Test PDF format detection."""
        fmt = DocumentExtractor.detect_format(SAMPLE_PDF_PATH)
        assert fmt == DocumentFormat.PDF

    def test_detect_pptx_format(self) -> None:
        """Test PPTX format detection."""
        fmt = DocumentExtractor.detect_format(SAMPLE_PPTX_PATH)
        assert fmt == DocumentFormat.PPTX

    def test_detect_ppt_format(self) -> None:
        """Test PPT format detection."""
        fmt = DocumentExtractor.detect_format(SAMPLE_PPT_PATH)
        assert fmt == DocumentFormat.PPT

    def test_unsupported_format_raises_error(self) -> None:
        """Test that unsupported format raises ExtractionError."""
        with pytest.raises(ExtractionError) as exc_info:
            DocumentExtractor.detect_format(UNSUPPORTED_FILE_PATH)

        assert exc_info.value.error_code == "UNSUPPORTED_FORMAT"


class TestPDFExtractor:
    """Tests for PDFExtractor class."""

    def test_extract_file_not_found(self) -> None:
        """Test extraction with nonexistent file."""
        with pytest.raises(ExtractionError) as exc_info:
            PDFExtractor.extract(NONEXISTENT_FILE_PATH)

        assert exc_info.value.error_code == "PDF_FILE_NOT_FOUND"
        assert exc_info.value.file_format == "pdf"

    @patch("src.pipelines.document_ingestion.document_extractor.PdfReader")
    @patch("builtins.open", create=True)
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_extract_success(
        self,
        mock_stat: MagicMock,
        mock_exists: MagicMock,
        mock_open: MagicMock,
        mock_pdf_reader: MagicMock,
    ) -> None:
        """Test successful PDF extraction."""
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = PDF_FILE_SIZE
        mock_stat.return_value = mock_stat_result

        mock_page = MagicMock()
        mock_page.extract_text.return_value = EXTRACTED_TEXT_SHORT
        mock_page.images = []
        mock_page.__getitem__.return_value = 0

        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_reader_instance.metadata = {
            "/Title": TITLE_PDF,
            "/Author": AUTHOR_PDF,
        }
        mock_pdf_reader.return_value = mock_reader_instance

        doc = PDFExtractor.extract(SAMPLE_PDF_PATH)

        assert doc.metadata.file_format == "pdf"
        assert doc.metadata.page_count == 1
        assert doc.metadata.file_size_bytes == PDF_FILE_SIZE
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1


class TestPowerPointExtractor:
    """Tests for PowerPointExtractor class."""

    def test_extract_file_not_found(self) -> None:
        """Test extraction with nonexistent file."""
        with pytest.raises(ExtractionError) as exc_info:
            PowerPointExtractor.extract(NONEXISTENT_FILE_PATH)

        assert exc_info.value.error_code == "PPTX_FILE_NOT_FOUND"
        assert exc_info.value.file_format == "pptx"

    @patch("src.pipelines.document_ingestion.document_extractor.Presentation")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.stat")
    def test_extract_success(
        self,
        mock_stat: MagicMock,
        mock_exists: MagicMock,
        mock_presentation: MagicMock,
    ) -> None:
        """Test successful PowerPoint extraction."""
        mock_stat_result = MagicMock()
        mock_stat_result.st_size = PPTX_FILE_SIZE
        mock_stat.return_value = mock_stat_result

        mock_shape = MagicMock()
        mock_shape.text = EXTRACTED_TEXT_SHORT

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]
        mock_slide.notes_slide.notes_text_frame.text = ""

        mock_pres_instance = MagicMock()
        mock_pres_instance.slides = [mock_slide]
        mock_pres_instance.core_properties.title = TITLE_PPTX
        mock_pres_instance.core_properties.author = AUTHOR_PDF
        mock_pres_instance.core_properties.created = None
        mock_presentation.return_value = mock_pres_instance

        doc = PowerPointExtractor.extract(SAMPLE_PPTX_PATH)

        assert doc.metadata.file_format == "pptx"
        assert doc.metadata.page_count == 1
        assert doc.metadata.file_size_bytes == PPTX_FILE_SIZE


class TestPowerPointExtractorHelpers:
    """Tests for PowerPointExtractor helper methods."""

    def test_extract_slide_text_empty_slide(self) -> None:
        """Test text extraction from empty slide."""
        mock_slide = MagicMock()
        mock_slide.shapes = []

        text = PowerPointExtractor._extract_slide_text(mock_slide)
        assert text == ""

    def test_extract_slide_text_multiple_shapes(self) -> None:
        """Test text extraction from slide with multiple shapes."""
        mock_shape1 = MagicMock()
        mock_shape1.text = "Shape 1 text"
        mock_shape2 = MagicMock()
        mock_shape2.text = "Shape 2 text"

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape1, mock_shape2]

        text = PowerPointExtractor._extract_slide_text(mock_slide)
        assert "Shape 1 text" in text
        assert "Shape 2 text" in text

    def test_has_images_in_slide_true(self) -> None:
        """Test image detection returns True."""
        mock_shape = MagicMock()
        mock_shape.shape_type = 13  # Picture type

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        result = PowerPointExtractor._has_images_in_slide(mock_slide)
        assert result is True

    def test_has_images_in_slide_false(self) -> None:
        """Test image detection returns False."""
        mock_shape = MagicMock()
        mock_shape.shape_type = 1  # Non-picture type

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        result = PowerPointExtractor._has_images_in_slide(mock_slide)
        assert result is False

    def test_has_tables_in_slide_true(self) -> None:
        """Test table detection returns True."""
        mock_shape = MagicMock()
        mock_shape.shape_type = 14  # Table type

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        result = PowerPointExtractor._has_tables_in_slide(mock_slide)
        assert result is True

    def test_has_tables_in_slide_false(self) -> None:
        """Test table detection returns False."""
        mock_shape = MagicMock()
        mock_shape.shape_type = 1  # Non-table type

        mock_slide = MagicMock()
        mock_slide.shapes = [mock_shape]

        result = PowerPointExtractor._has_tables_in_slide(mock_slide)
        assert result is False


class TestDocumentExtractorBatchExtraction:
    """Tests for batch extraction functionality."""

    @patch("src.pipelines.document_ingestion.document_extractor.DocumentExtractor.extract")
    def test_batch_extract_success_only(self, mock_extract: MagicMock) -> None:
        """Test batch extraction with all successful."""
        doc_meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=1,
        )
        mock_extract.return_value = ExtractedDocument(metadata=doc_meta)

        file_paths = [SAMPLE_PDF_PATH, SAMPLE_PPTX_PATH]
        results = DocumentExtractor.batch_extract(file_paths)

        assert len(results) == BATCH_SIZE_TWO
        for _file_path, result in results:
            assert isinstance(result, ExtractedDocument)

    @patch("src.pipelines.document_ingestion.document_extractor.DocumentExtractor.extract")
    def test_batch_extract_mixed_results(self, mock_extract: MagicMock) -> None:
        """Test batch extraction with mixed success/failure."""
        doc_meta = DocumentMetadata(
            file_path=SAMPLE_PDF_PATH,
            file_format="pdf",
            file_size_bytes=PDF_FILE_SIZE,
            page_count=1,
        )
        mock_extract.side_effect = [
            ExtractedDocument(metadata=doc_meta),
            ExtractionError(
                error_code="TEST_ERROR",
                error_message="Test error",
                file_path=SAMPLE_PPTX_PATH,
                file_format="pptx",
            ),
        ]

        file_paths = [SAMPLE_PDF_PATH, SAMPLE_PPTX_PATH]
        results = DocumentExtractor.batch_extract(file_paths)

        assert len(results) == BATCH_SIZE_TWO
        assert isinstance(results[0][1], ExtractedDocument)
        assert isinstance(results[1][1], ExtractionError)

    @patch("src.pipelines.document_ingestion.document_extractor.DocumentExtractor.extract")
    def test_batch_extract_empty_list(self, mock_extract: MagicMock) -> None:
        """Test batch extraction with empty list."""
        results = DocumentExtractor.batch_extract([])
        assert len(results) == 0
