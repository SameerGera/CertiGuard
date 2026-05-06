import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class OCRResult:
    text: str
    confidence: float
    method: str = "unknown"
    bounding_boxes: list[dict] = None


class OCREngine:
    def __init__(self, tesseract_path: str = ""):
        self.tesseract_path = tesseract_path

    def ocr(self, file_path: str | Path) -> OCRResult:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            return self._ocr_pdf(file_path)
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
            return self._ocr_image(file_path)
        return OCRResult(text="", confidence=0.0)

    def _ocr_image(self, file_path: Path) -> OCRResult:
        result = self._ocr_tesseract(file_path)
        if result.confidence > 0.5:
            return result
        result = self._ocr_pytesseract(file_path)
        return result

    def _ocr_pdf(self, file_path: Path) -> OCRResult:
        all_text = ""
        total_confidence = 0.0
        count = 0

        try:
            import pdf2image
            images = pdf2image.convert_from_path(file_path)
            for img in images:
                result = self._ocr_pil_image(img)
                all_text += "\n" + result.text
                total_confidence += result.confidence
                count += 1
            if count > 0:
                return OCRResult(
                    text=all_text.strip(),
                    confidence=total_confidence / count,
                    method="pdf2image+tesseract",
                )
        except Exception:
            pass

        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text += "\n" + text
                        count += 1
                if all_text.strip():
                    return OCRResult(
                        text=all_text.strip(),
                        confidence=0.9,
                        method="pdfplumber",
                    )
        except Exception:
            pass

        return OCRResult(text="", confidence=0.0)

    def _ocr_tesseract(self, file_path: Path) -> OCRResult:
        if not self.tesseract_path:
            self.tesseract_path = self._find_tesseract()

        if not self.tesseract_path:
            return OCRResult(text="", confidence=0.0)

        try:
            result = subprocess.run(
                [self.tesseract_path, str(file_path), "-"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                text = result.stdout.strip()
                confidence = 0.7 if text else 0.0
                return OCRResult(text=text, confidence=confidence, method="tesseract-cli")
        except Exception as e:
            print(f"[WARN] Tesseract CLI failed: {e}")

        return OCRResult(text="", confidence=0.0)

    def _ocr_pytesseract(self, file_path: Path) -> OCRResult:
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang="eng+hin")

            return OCRResult(
                text=text.strip(),
                confidence=0.7 if text.strip() else 0.0,
                method="pytesseract",
            )
        except Exception as e:
            print(f"[WARN] Pytesseract OCR failed: {e}")
            return OCRResult(text="", confidence=0.0)

    def _ocr_pil_image(self, image) -> OCRResult:
        try:
            import pytesseract
            text = pytesseract.image_to_string(image, lang="eng+hin")
            return OCRResult(
                text=text.strip(),
                confidence=0.7 if text.strip() else 0.0,
                method="pytesseract",
            )
        except Exception:
            return OCRResult(text="", confidence=0.0)

    def _find_tesseract(self) -> Optional[str]:
        import shutil

        tesseract = shutil.which("tesseract")
        if tesseract:
            return tesseract

        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"/usr/bin/tesseract",
            r"/usr/local/bin/tesseract",
        ]
        for path in common_paths:
            if Path(path).exists():
                return path
        return None

    def is_available(self) -> bool:
        return self._find_tesseract() is not None