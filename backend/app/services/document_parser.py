"""
AI Interview Coach - Document Parser

Extracts text from PDF, DOCX, TXT, and Markdown files.
Returns normalized raw text for further processing by the profile extraction service.
"""

from __future__ import annotations
import io
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ParsedDocument:
    """Result of document parsing."""

    raw_text: str
    filename: str
    file_type: str
    page_count: int = 1
    sections: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class DocumentParser:
    """Multi-format document parser for CVs and job descriptions."""

    SUPPORTED_TYPES = {".pdf", ".docx", ".doc", ".txt", ".md", ".markdown"}

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Parse a document from bytes based on file extension."""
        ext = Path(filename).suffix.lower()

        if ext not in self.SUPPORTED_TYPES:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(self.SUPPORTED_TYPES)}"
            )

        if ext == ".pdf":
            return self._parse_pdf(file_bytes, filename)
        elif ext in (".docx", ".doc"):
            return self._parse_docx(file_bytes, filename)
        elif ext in (".txt", ".md", ".markdown"):
            return self._parse_text(file_bytes, filename, ext)
        else:
            raise ValueError(f"Unhandled file type: {ext}")

    def _parse_pdf(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Extract text from PDF using PyMuPDF."""
        import fitz  # pymupdf

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        warnings = []

        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text)
            else:
                # Try OCR-like extraction for image-based pages
                text = page.get_text("blocks")
                block_text = "\n".join(
                    block[4] for block in text if block[6] == 0  # text blocks only
                )
                if block_text.strip():
                    pages_text.append(block_text)
                else:
                    warnings.append(
                        f"Page {page_num + 1} appears to be image-based and could not be extracted."
                    )

        raw_text = "\n\n".join(pages_text)
        sections = self._detect_sections(raw_text)
        
        # Calculate page count before closing the document
        page_count = len(doc) if hasattr(doc, '__len__') else len(pages_text)

        doc.close()

        return ParsedDocument(
            raw_text=raw_text.strip(),
            filename=filename,
            file_type="pdf",
            page_count=page_count,
            sections=sections,
            metadata={"pages_extracted": len(pages_text)},
            warnings=warnings,
        )

    def _parse_docx(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Extract text from DOCX using python-docx."""
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)

        raw_text = "\n".join(paragraphs)
        sections = self._detect_sections(raw_text)

        return ParsedDocument(
            raw_text=raw_text.strip(),
            filename=filename,
            file_type="docx",
            sections=sections,
            metadata={"paragraphs": len(paragraphs), "tables": len(doc.tables)},
        )

    def _parse_text(
        self, file_bytes: bytes, filename: str, ext: str
    ) -> ParsedDocument:
        """Parse plain text or markdown files."""
        # Try UTF-8 first, fall back to latin-1
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1")

        sections = self._detect_sections(raw_text)
        file_type = "markdown" if ext in (".md", ".markdown") else "text"

        return ParsedDocument(
            raw_text=raw_text.strip(),
            filename=filename,
            file_type=file_type,
            sections=sections,
        )

    def _detect_sections(self, text: str) -> list[str]:
        """Detect common CV section headers."""
        common_headers = [
            "summary", "objective", "profile", "about",
            "experience", "employment", "work history", "professional experience",
            "education", "academic",
            "skills", "technical skills", "competencies", "technologies",
            "certifications", "certificates", "licenses",
            "projects", "portfolio",
            "achievements", "awards", "honors",
            "languages",
            "references",
            "publications",
            "volunteer", "activities",
            # Arabic headers
            "الملخص", "الخبرات", "التعليم", "المهارات", "الشهادات", "المشاريع",
        ]

        found_sections = []
        text_lower = text.lower()

        for header in common_headers:
            if header in text_lower:
                found_sections.append(header)

        return found_sections


# Singleton instance
document_parser = DocumentParser()
