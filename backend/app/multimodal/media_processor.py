"""Image, audio, and media processing pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ImageAnalysis:
    """Result of image analysis.

    Attributes:
        text_content: Text extracted via OCR.
        objects_detected: List of detected object labels.
        sentiment: Overall sentiment inferred from image content.
        metadata: Extracted EXIF or other metadata.
        dimensions: Image dimensions dict (width, height).
    """

    text_content: str = ""
    objects_detected: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    metadata: dict[str, Any] = field(default_factory=dict)
    dimensions: dict[str, int] = field(default_factory=dict)


@dataclass
class ImageContent:
    """Semantic content of an image.

    Attributes:
        description: LLM-generated image description.
        labels: Classification labels.
        faces_detected: Whether faces were detected.
        text_regions: Text regions identified.
    """

    description: str = ""
    labels: list[str] = field(default_factory=list)
    faces_detected: bool = False
    text_regions: list[str] = field(default_factory=list)


@dataclass
class AudioAnalysis:
    """Result of audio analysis.

    Attributes:
        transcript: Speech-to-text transcript.
        language: Detected language code.
        duration_seconds: Audio duration.
        sentiment: Overall audio sentiment.
        speaker_count: Estimated number of speakers.
    """

    transcript: str = ""
    language: str = "unknown"
    duration_seconds: float = 0.0
    sentiment: str = "neutral"
    speaker_count: int = 1


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------


class MediaProcessor:
    """Image, video, and audio processing pipeline.

    Dispatches to the best available backend for each modality.  All
    dependencies are optional; the processor degrades gracefully.
    """

    # ------------------------------------------------------------------
    # Image processing
    # ------------------------------------------------------------------

    async def process_image(
        self,
        image_data: bytes,
        extract_text: bool = True,
    ) -> ImageAnalysis:
        """Process an image and return combined analysis.

        Args:
            image_data: Raw image bytes.
            extract_text: Whether to run OCR.

        Returns:
            :class:`ImageAnalysis` with all available fields populated.
        """
        analysis = ImageAnalysis()

        # Extract metadata
        try:
            analysis.metadata = await self.extract_metadata(image_data, "image")
        except Exception:
            pass

        # OCR
        if extract_text:
            try:
                analysis.text_content = await self.extract_text_from_image(
                    image_data
                )
            except Exception:
                pass

        # Object detection / classification
        try:
            content = await self.analyze_image_content(image_data)
            analysis.objects_detected = content.labels
        except Exception:
            pass

        # Image dimensions
        try:
            from PIL import Image as PILImage  # type: ignore
            import io

            img = PILImage.open(io.BytesIO(image_data))
            analysis.dimensions = {"width": img.width, "height": img.height}
        except Exception:
            pass

        return analysis

    async def extract_text_from_image(self, image_data: bytes) -> str:
        """Run OCR on an image using pytesseract.

        Args:
            image_data: Raw image bytes.

        Returns:
            Extracted text string, or empty string on failure.
        """
        try:
            import asyncio
            import io

            from PIL import Image as PILImage  # type: ignore
            import pytesseract  # type: ignore

            img = PILImage.open(io.BytesIO(image_data))
            text: str = await asyncio.to_thread(pytesseract.image_to_string, img)
            return text.strip()
        except ImportError:
            logger.warning("pytesseract or Pillow not installed; OCR unavailable")
        except Exception as exc:
            logger.warning("OCR failed: %s", exc)
        return ""

    async def analyze_image_content(self, image_data: bytes) -> ImageContent:
        """Detect objects and generate a description for an image.

        Uses OpenCV for object detection when available, with an LLM
        vision model fallback.

        Args:
            image_data: Raw image bytes.

        Returns:
            :class:`ImageContent`.
        """
        content = ImageContent()
        try:
            import asyncio
            import base64
            from app.config import settings as _settings

            if _settings.OPENAI_API_KEY:
                from langchain_openai import ChatOpenAI  # type: ignore
                from langchain_core.messages import HumanMessage  # type: ignore

                b64 = base64.b64encode(image_data).decode()
                llm = ChatOpenAI(
                    model="gpt-4-vision-preview",
                    api_key=_settings.OPENAI_API_KEY,
                    max_tokens=500,
                )
                msg = HumanMessage(
                    content=[
                        {"type": "text", "text": "Describe this image briefly and list any text and key objects."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ]
                )
                response = await asyncio.to_thread(llm.invoke, [msg])
                content.description = response.content
        except Exception as exc:
            logger.warning("Image content analysis failed: %s", exc)
        return content

    # ------------------------------------------------------------------
    # Audio processing
    # ------------------------------------------------------------------

    async def process_audio(self, audio_data: bytes) -> AudioAnalysis:
        """Process audio data for transcription and analysis.

        Args:
            audio_data: Raw audio bytes (WAV or MP3).

        Returns:
            :class:`AudioAnalysis`.
        """
        analysis = AudioAnalysis()
        try:
            import asyncio
            import tempfile, os

            from app.config import settings as _settings

            if _settings.OPENAI_API_KEY:
                import openai  # type: ignore

                client = openai.AsyncOpenAI(api_key=_settings.OPENAI_API_KEY)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                try:
                    with open(tmp_path, "rb") as f:
                        transcript = await client.audio.transcriptions.create(
                            model="whisper-1", file=f
                        )
                    analysis.transcript = transcript.text
                finally:
                    os.unlink(tmp_path)
        except Exception as exc:
            logger.warning("Audio transcription failed: %s", exc)
        return analysis

    # ------------------------------------------------------------------
    # Metadata extraction
    # ------------------------------------------------------------------

    async def extract_metadata(
        self, media_data: bytes, media_type: str
    ) -> dict[str, Any]:
        """Extract metadata from a media blob.

        Args:
            media_data: Raw media bytes.
            media_type: "image", "audio", or "video".

        Returns:
            Metadata dict.
        """
        metadata: dict[str, Any] = {"size_bytes": len(media_data)}
        if media_type == "image":
            try:
                from PIL import Image as PILImage  # type: ignore
                from PIL.ExifTags import TAGS  # type: ignore
                import io

                img = PILImage.open(io.BytesIO(media_data))
                metadata["format"] = img.format
                metadata["mode"] = img.mode
                exif_data = img._getexif()  # type: ignore[attr-defined]
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        if isinstance(value, (str, int, float)):
                            metadata[str(tag_name)] = value
            except Exception:
                pass
        return metadata


# Module-level singleton
media_processor = MediaProcessor()
