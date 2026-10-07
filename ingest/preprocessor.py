"""Image preprocessing for /ingest: PDF conversion to 300 DPI, deskew, and denoise."""

from pathlib import Path
from typing import Optional, Union
import cv2
import numpy as np
from PIL import Image

try:
    import pypdfium2 as pdfium
    HAS_PYPDFIUM = True
except ImportError:
    HAS_PYPDFIUM = False


def pdf_to_images(
    pdf_path: Union[str, Path],
    output_dir: Union[str, Path],
    dpi: int = 300,
) -> list[Path]:
    """Convert each page of a PDF document into a 300 DPI PNG image.
    
    Args:
        pdf_path: Path to the input PDF file.
        output_dir: Directory where rendered images will be saved.
        dpi: Target resolution in dots per inch (default 300).
        
    Returns:
        List of Paths to the saved page images.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not HAS_PYPDFIUM:
        raise ImportError(
            "pypdfium2 is required for PDF rendering. Install with: pip install pypdfium2"
        )

    pdf = pdfium.PdfDocument(str(pdf_path))
    scale = dpi / 72.0  # Standard PDF resolution is 72 pt/inch
    page_paths = []

    for idx, page in enumerate(pdf):
        page_num = idx + 1
        rendered = page.render(scale=scale).to_pil()
        out_file = output_dir / f"page_{page_num:03d}.png"
        rendered.save(out_file, format="PNG")
        page_paths.append(out_file)

    return page_paths


def calculate_skew_angle(image: np.ndarray) -> float:
    """Calculate the skew angle of text lines in a grayscale image.
    
    Uses cv2.minAreaRect on thresholded text pixels.
    """
    # Threshold inverted so text is foreground (white)
    thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]

    # Find coordinates of all white (text) pixels
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return 0.0

    rect = cv2.minAreaRect(coords)
    angle = rect[-1]

    # Normalize angle to [-45, 45] degrees
    if angle < -45.0:
        angle = -(90.0 + angle)
    elif angle > 45.0:
        angle = 90.0 - angle
    else:
        angle = -angle

    return float(angle)


def deskew_image(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate image around its center to correct skew."""
    if abs(angle) < 0.2:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        rot_mat,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255) if len(image.shape) == 3 else 255,
    )
    return rotated


def denoise_image(gray_image: np.ndarray) -> np.ndarray:
    """Remove background scan noise and dust artifacts using OpenCV."""
    # Apply bilateral filter to preserve text edges while smoothing background noise
    denoised = cv2.bilateralFilter(gray_image, d=7, sigmaColor=50, sigmaSpace=50)
    return denoised


def preprocess_page_image(
    image_input: Union[str, Path, np.ndarray, Image.Image],
    output_path: Optional[Union[str, Path]] = None,
) -> np.ndarray:
    """Convert page to clean grayscale, deskew, and denoise for optimal OCR.
    
    Args:
        image_input: File path, numpy array, or PIL Image.
        output_path: Optional path to save the preprocessed PNG.
        
    Returns:
        Preprocessed image as a 2D uint8 numpy array.
    """
    # 1. Load image as numpy array
    if isinstance(image_input, (str, Path)):
        img = cv2.imread(str(image_input))
        if img is None:
            raise FileNotFoundError(f"Could not load image at {image_input}")
    elif isinstance(image_input, Image.Image):
        img = np.array(image_input)
        if len(img.shape) == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif isinstance(image_input, np.ndarray):
        img = image_input.copy()
    else:
        raise TypeError(f"Unsupported image input type: {type(image_input)}")

    # 2. Convert to Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # 3. Deskew
    skew_angle = calculate_skew_angle(gray)
    deskewed = deskew_image(gray, skew_angle)

    # 4. Denoise
    cleaned = denoise_image(deskewed)

    # 5. Save if output path requested
    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_p), cleaned)

    return cleaned
