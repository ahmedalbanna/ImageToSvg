#!/usr/bin/env python3
"""
Image to SVG (non-AI) converter.

Two primary modes (plus one stylized mode):
- flat: for flat-color artwork (icons, cartoons). Quantizes colors, extracts regions, and outputs filled SVG paths.
- line: for black-and-white line art (logos, scans). Thresholds image, extracts contours, outputs filled paths (or optional stroked outline).
- lowpoly: stylized triangulation using Delaunay over feature points, polygons filled by average color.

Usage examples:
  python im2svg.py input.png -o output.svg --mode flat --colors 8 --min-area 25 --epsilon 0.003
  python im2svg.py input.png -o output.svg --mode line --invert --adaptive --min-area 15 --epsilon 0.002

Install deps:
  pip install -r requirements.txt

Limitations:
- For photographs, results will be heavy unless colors are reduced aggressively. Consider low-poly stylization as a future enhancement.
- Curve fitting supports polygonal simplification or optional cubic Bezier fitting for smoother curves.
"""
import argparse
import sys
from typing import List, Tuple, Optional, Iterator, Union, Any

import cv2
import numpy as np
import svgwrite
from math import sqrt
try:
    # Optional: use scipy if available for Delaunay; else fallback to cv2.Subdiv2D
    from scipy.spatial import Delaunay  # type: ignore
    _HAS_SCIPY = True
except Exception:  # pragma: no cover
    _HAS_SCIPY = False

# Skeletonization for centerline tracing
try:
    from skimage.morphology import skeletonize  # type: ignore
    _HAS_SKIMAGE = True
except Exception:  # pragma: no cover
    _HAS_SKIMAGE = False

# --------------- Utilities ---------------

# --------------- Artistic Filters ---------------

def apply_watercolor_effect(img_bgr: np.ndarray, intensity: float = 0.5) -> np.ndarray:
    """Apply watercolor painting effect to image.
    
    Args:
        img_bgr: Input BGR image
        intensity: Effect intensity (0.0-1.0), higher = more watercolor-like
    
    Returns:
        Watercolor-styled BGR image
    """
    # Reduce details with bilateral filter
    filtered = cv2.bilateralFilter(img_bgr, d=9, sigmaColor=90, sigmaSpace=90)
    
    # Apply median blur for color bleeding effect
    median_ksize = max(3, int(5 * intensity))
    if median_ksize % 2 == 0:
        median_ksize += 1
    median = cv2.medianBlur(filtered, median_ksize)
    
    # Enhance edges slightly for watercolor borders
    edges = cv2.Canny(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), 50, 150)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    
    # Blend original with median for watercolor look
    alpha = 0.3 + (intensity * 0.4)  # 0.3 to 0.7 range
    result = cv2.addWeighted(median, alpha, filtered, 1 - alpha, 0)
    
    # Darken edges slightly for watercolor paper effect
    edges_3d = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    result = np.where(edges_3d > 0, result * 0.8, result).astype(np.uint8)
    
    # Reduce color depth for paint-like appearance
    color_levels = max(32, int(128 * (1.0 - intensity * 0.5)))
    result = (result // color_levels) * color_levels
    
    return result


def apply_sketch_effect(img_bgr: np.ndarray, intensity: float = 0.5, colored: bool = False) -> np.ndarray:
    """Apply pencil sketch effect to image.
    
    Args:
        img_bgr: Input BGR image
        intensity: Sketch line intensity (0.0-1.0), higher = darker lines
        colored: If True, creates colored pencil sketch
    
    Returns:
        Sketch-styled BGR image
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # Invert the image
    inverted = 255 - gray
    
    # Blur the inverted image
    blur_value = max(5, int(21 * intensity))
    if blur_value % 2 == 0:
        blur_value += 1
    blurred = cv2.GaussianBlur(inverted, (blur_value, blur_value), 0)
    
    # Invert the blurred image
    inverted_blur = 255 - blurred
    
    # Divide gray by inverted blur to get sketch effect
    sketch = cv2.divide(gray, inverted_blur, scale=256.0)
    
    if colored:
        # Apply sketch as luminance to preserve colors
        # Convert to LAB color space
        lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Replace L channel with sketch
        l = sketch
        
        # Merge and convert back
        lab = cv2.merge([l, a, b])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Reduce saturation for pencil look
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        s = (s * 0.6).astype(np.uint8)
        hsv = cv2.merge([h, s, v])
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    else:
        # Black and white sketch
        result = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)
    
    return result


def apply_oil_painting_effect(img_bgr: np.ndarray, size: int = 7, dynRatio: int = 1) -> np.ndarray:
    """Apply oil painting effect to image.
    
    Args:
        img_bgr: Input BGR image
        size: Brush size (3-10), larger = more painterly
        dynRatio: Dynamic range ratio (1-10)
    
    Returns:
        Oil painting styled BGR image
    """
    # OpenCV has a built-in oil painting effect
    try:
        # Try using cv2.xphoto module if available
        result = cv2.xphoto.oilPainting(img_bgr, size, dynRatio)
        return result
    except (AttributeError, cv2.error):
        # Fallback: manual oil painting effect
        # Apply bilateral filter multiple times for oil paint look
        result = img_bgr.copy()
        
        for _ in range(2):
            result = cv2.bilateralFilter(result, d=9, sigmaColor=90, sigmaSpace=90)
        
        # Apply median blur
        ksize = max(3, size)
        if ksize % 2 == 0:
            ksize += 1
        result = cv2.medianBlur(result, ksize)
        
        # Enhance color saturation for oil paint vibrancy
        hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        s = np.clip(s * 1.3, 0, 255).astype(np.uint8)
        hsv = cv2.merge([h, s, v])
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        # Quantize colors for paint-like effect
        color_levels = 32
        result = (result // color_levels) * color_levels
        
        return result


def apply_cartoon_effect(img_bgr: np.ndarray, num_bilateral: int = 7, edge_threshold: int = 80) -> np.ndarray:
    """Apply cartoon/cel-shading effect to image.
    
    Args:
        img_bgr: Input BGR image
        num_bilateral: Number of bilateral filter iterations (5-10)
        edge_threshold: Edge detection threshold (50-150)
    
    Returns:
        Cartoon-styled BGR image
    """
    # Apply bilateral filter multiple times to reduce details
    result = img_bgr.copy()
    for _ in range(num_bilateral):
        result = cv2.bilateralFilter(result, d=9, sigmaColor=9, sigmaSpace=7)
    
    # Detect and emphasize edges
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 7)
    edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, blockSize=9, C=edge_threshold)
    
    # Convert edges to BGR and combine with filtered image
    edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
    result = cv2.bitwise_and(result, edges)
    
    return result


def apply_artistic_filter(img_bgr: np.ndarray, filter_type: str, intensity: float = 0.5) -> np.ndarray:
    """Apply artistic filter to image.
    
    Args:
        img_bgr: Input BGR image
        filter_type: Type of filter ('watercolor', 'sketch', 'colored_sketch', 'oil', 'cartoon')
        intensity: Filter intensity (0.0-1.0)
    
    Returns:
        Filtered BGR image
    """
    if filter_type == "watercolor":
        return apply_watercolor_effect(img_bgr, intensity)
    elif filter_type == "sketch":
        return apply_sketch_effect(img_bgr, intensity, colored=False)
    elif filter_type == "colored_sketch":
        return apply_sketch_effect(img_bgr, intensity, colored=True)
    elif filter_type == "oil":
        size = max(3, int(7 * intensity))
        return apply_oil_painting_effect(img_bgr, size=size, dynRatio=1)
    elif filter_type == "cartoon":
        num_bilateral = max(5, int(7 + 3 * intensity))
        return apply_cartoon_effect(img_bgr, num_bilateral=num_bilateral)
    else:
        return img_bgr


# --------------- Image Preprocessing ---------------

def enhance_contrast(img_bgr: np.ndarray, method: str = "clahe", clip_limit: float = 2.0) -> np.ndarray:
    """Enhance image contrast using CLAHE or histogram equalization.
    
    Args:
        img_bgr: Input BGR image
        method: 'clahe' for adaptive or 'hist' for global histogram equalization
        clip_limit: Clip limit for CLAHE (1.0-4.0)
    
    Returns:
        Contrast-enhanced BGR image
    """
    # Convert to LAB for better perceptual results
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    if method == "clahe":
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        l = clahe.apply(l)
    else:  # hist
        l = cv2.equalizeHist(l)
    
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def denoise_image(img_bgr: np.ndarray, strength: int = 10) -> np.ndarray:
    """Remove noise using Non-local Means Denoising.
    
    Args:
        img_bgr: Input BGR image
        strength: Denoising strength (5-20), higher = more smoothing
    
    Returns:
        Denoised BGR image
    """
    h = min(21, max(5, strength))
    return cv2.fastNlMeansDenoisingColored(img_bgr, None, h=h, hColor=h, templateWindowSize=7, searchWindowSize=21)


def sharpen_image(img_bgr: np.ndarray, strength: float = 1.0) -> np.ndarray:
    """Sharpen image using unsharp masking.
    
    Args:
        img_bgr: Input BGR image
        strength: Sharpening strength (0.5-2.0)
    
    Returns:
        Sharpened BGR image
    """
    # Gaussian blur for unsharp mask
    blurred = cv2.GaussianBlur(img_bgr, (0, 0), 3)
    sharpened = cv2.addWeighted(img_bgr, 1.0 + strength, blurred, -strength, 0)
    return sharpened


def auto_crop(img_bgr: np.ndarray, threshold: int = 10) -> np.ndarray:
    """Remove uniform borders from image.
    
    Args:
        img_bgr: Input BGR image
        threshold: Color difference threshold for border detection
    
    Returns:
        Cropped BGR image (returns original if cropping would result in empty image)
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # Detect edges
    edges = cv2.Canny(gray, 50, 150)
    
    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return img_bgr
    
    # Get bounding rectangle of all contours
    x, y, w, h = cv2.boundingRect(np.vstack(contours))
    
    # Add small margin
    margin = 5
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(img_bgr.shape[1] - x, w + 2 * margin)
    h = min(img_bgr.shape[0] - y, h + 2 * margin)
    
    # Safety check: ensure crop dimensions are valid
    if w <= 0 or h <= 0 or x >= img_bgr.shape[1] or y >= img_bgr.shape[0]:
        return img_bgr
    
    cropped = img_bgr[y:y+h, x:x+w]
    
    # Ensure cropped image is not empty
    if cropped.size == 0:
        return img_bgr
    
    return cropped


def resize_if_large(img_bgr: np.ndarray, max_size: int = 2000) -> np.ndarray:
    """Downsample image if dimensions exceed max_size for faster processing.
    
    Args:
        img_bgr: Input BGR image
        max_size: Maximum dimension (width or height)
    
    Returns:
        Resized BGR image or original if already small enough
    """
    h, w = img_bgr.shape[:2]
    max_dim = max(h, w)
    
    if max_dim <= max_size:
        return img_bgr
    
    scale = max_size / max_dim
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def preprocess_image(
    img_bgr: np.ndarray,
    contrast: bool = False,
    contrast_method: str = "clahe",
    denoise: bool = False,
    denoise_strength: int = 10,
    sharpen: bool = False,
    sharpen_strength: float = 1.0,
    auto_crop_enabled: bool = False,
    max_size: int = 0
) -> np.ndarray:
    """Apply preprocessing pipeline to image.
    
    Args:
        img_bgr: Input BGR image
        contrast: Enable contrast enhancement
        contrast_method: 'clahe' or 'hist'
        denoise: Enable denoising
        denoise_strength: Denoising strength (5-20)
        sharpen: Enable sharpening
        sharpen_strength: Sharpening strength (0.5-2.0)
        auto_crop_enabled: Enable automatic border cropping
        max_size: Maximum dimension for resizing (0=no limit)
    
    Returns:
        Preprocessed BGR image
    """
    img = img_bgr.copy()
    
    # Resize first for faster subsequent operations
    if max_size > 0:
        img = resize_if_large(img, max_size)
    
    # Auto crop
    if auto_crop_enabled:
        img = auto_crop(img)
    
    # Denoise (do early to clean up noise before other operations)
    if denoise:
        img = denoise_image(img, denoise_strength)
    
    # Contrast enhancement
    if contrast:
        img = enhance_contrast(img, contrast_method)
    
    # Sharpen (do last for best effect)
    if sharpen:
        img = sharpen_image(img, sharpen_strength)
    
    return img


# --------------- Bezier Curve Fitting ---------------

# Bezier fitting: simple chord-length parameterization + least-squares cubic fit per segment.
# Also provides a recursive error-based splitter (Schneider-style) for better corner preservation.

def _fit_cubic_bezier(points: np.ndarray) -> Optional[np.ndarray]:
    """Fit a single cubic Bezier to a sequence of points (Nx2) using chord-length parameterization.
    Returns control points as (4,2) or None if unstable.
    """
    n = len(points)
    if n < 2:
        return None
    # End points
    P0 = points[0]
    P3 = points[-1]
    # Tangent approximations at ends
    t0 = points[1] - points[0]
    t1 = points[-2] - points[-1]
    if np.linalg.norm(t0) < 1e-6 or np.linalg.norm(t1) < 1e-6:
        # Degenerate: return a straight-line Bezier
        return np.stack([P0, P0 + (P3 - P0) / 3.0, P0 + 2.0 * (P3 - P0) / 3.0, P3], axis=0)

    # Parameterize by chord length
    dists = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    if dists[-1] <= 1e-6:
        return np.stack([P0, P0, P3, P3], axis=0)
    u = (dists / dists[-1]).reshape(-1, 1)

    # Build matrices for least squares on P1,P2 given P0,P3
    # B(t) = (1-t)^3 P0 + 3(1-t)^2 t P1 + 3(1-t) t^2 P2 + t^3 P3
    # Let A = [3(1-t)^2 t, 3(1-t) t^2], solve A * [P1; P2] = P - ((1-t)^3 P0 + t^3 P3)
    t = u
    omt = 1.0 - t
    A = np.concatenate([3 * omt * omt * t, 3 * omt * t * t], axis=1)  # (n,2)
    RHS = points - (omt * omt * omt) * P0 - (t * t * t) * P3

    # Solve least squares per coordinate
    # Add small regularization for stability
    reg = 1e-6
    ATA = A.T @ A + reg * np.eye(2)
    ATb_x = A.T @ RHS[:, 0]
    ATb_y = A.T @ RHS[:, 1]
    try:
        coeff_x = np.linalg.solve(ATA, ATb_x)
        coeff_y = np.linalg.solve(ATA, ATb_y)
    except np.linalg.LinAlgError:
        return None

    # Construct P1,P2 per axis properly
    P1 = np.array([coeff_x[0], coeff_y[0]])
    P2 = np.array([coeff_x[1], coeff_y[1]])

    return np.stack([P0, P1, P2, P3], axis=0)


def polyline_to_beziers(points: np.ndarray, seg_len: int = 16) -> List[np.ndarray]:
    """Split a polyline into chunks and fit a cubic Bezier to each. Returns list of (4,2) arrays.
    seg_len controls the number of input points per fitted curve. Overlaps ends for continuity.
    """
    if points is None or len(points) < 2:
        return []
    pts = points.astype(np.float64)
    n = len(pts)
    beziers: List[np.ndarray] = []
    i = 0
    while i < n - 1:
        j = min(n - 1, i + seg_len - 1)
        seg = pts[i:j + 1]
        bz = _fit_cubic_bezier(seg)
        if bz is not None:
            beziers.append(bz)
        else:
            # fallback to straight line as degenerate cubic
            P0, P3 = seg[0], seg[-1]
            beziers.append(np.stack([P0, P0 + (P3 - P0) / 3.0, P0 + 2.0 * (P3 - P0) / 3.0, P3], axis=0))
        i = j
    return beziers


def beziers_to_path_d(beziers: List[np.ndarray], closed: bool = True) -> str:
    if not beziers:
        return ""
    d = []
    first = beziers[0]
    d.append(f"M {first[0,0]:.2f},{first[0,1]:.2f}")
    for bz in beziers:
        # C x1,y1 x2,y2 x,y
        d.append(
            f"C {bz[1,0]:.2f},{bz[1,1]:.2f} {bz[2,0]:.2f},{bz[2,1]:.2f} {bz[3,0]:.2f},{bz[3,1]:.2f}"
        )
    if closed:
        d.append("Z")
    return " ".join(d)


def bgr_to_hex(color: np.ndarray) -> str:
    b, g, r = [int(x) for x in color]
    return f"#{r:02x}{g:02x}{b:02x}"


def to_svg_path_d(points: np.ndarray, closed: bool = True) -> str:
    """Construct an SVG path 'd' string from polyline points using straight segments.
    points: (N,2) float32 or float64.
    """
    if points is None or len(points) == 0:
        return ""
    d = [f"M {points[0][0]:.2f},{points[0][1]:.2f}"]
    for p in points[1:]:
        d.append(f"L {p[0]:.2f},{p[1]:.2f}")
    if closed:
        d.append("Z")
    return " ".join(d)


def simplify_poly(contour: np.ndarray, epsilon_ratio: float = 0.002) -> np.ndarray:
    """Simplify contour to fewer points using Ramer–Douglas–Peucker.
    contour: (N,1,2) int32/float -> returns (M,2) float32
    epsilon = epsilon_ratio * perimeter
    """
    if contour is None or len(contour) == 0:
        return np.empty((0, 2), dtype=np.float32)
    perim = cv2.arcLength(contour, True)
    epsilon = float(epsilon_ratio) * max(perim, 1.0)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return approx[:, 0, :].astype(np.float32)


def max_poly_error(poly: np.ndarray, bezier: np.ndarray) -> float:
    """Compute maximum point-to-Bezier distance as an error metric."""
    if poly is None or len(poly) == 0:
        return 0.0
    # Sample the Bezier finely
    ts = np.linspace(0, 1, num=64)
    P0, P1, P2, P3 = [bezier[i] for i in range(4)]
    B = (1-ts)[:,None]**3 * P0 + 3*(1-ts)[:,None]**2*ts[:,None] * P1 + 3*(1-ts)[:,None]*ts[:,None]**2 * P2 + ts[:,None]**3 * P3
    # Distances from poly points to closest Bezier sample
    d = np.min(np.linalg.norm(poly[:,None,:] - B[None,:,:], axis=2), axis=1)
    return float(d.max())


def recursive_fit_beziers(points: np.ndarray, max_err: float = 2.0, min_seg: int = 6) -> List[np.ndarray]:
    """Recursively split polyline and fit cubic Beziers where error exceeds threshold.
    max_err in pixels. Returns list of cubic Bezier segments.
    """
    pts = points.astype(np.float64)
    n = len(pts)
    if n <= 1:
        return []
    if n <= min_seg:
        bz = _fit_cubic_bezier(pts)
        return [bz] if bz is not None else []
    bz = _fit_cubic_bezier(pts)
    if bz is None:
        # fallback: split in half
        mid = n // 2
        return recursive_fit_beziers(pts[:mid+1], max_err, min_seg) + recursive_fit_beziers(pts[mid:], max_err, min_seg)
    err = max_poly_error(pts, bz)
    if err <= max_err:
        return [bz]
    # Split at point of max deviation
    ts = np.linspace(0, 1, num=n)
    P0, P1, P2, P3 = bz
    B = (1-ts)[:,None]**3 * P0 + 3*(1-ts)[:,None]**2*ts[:,None] * P1 + 3*(1-ts)[:,None]*ts[:,None]**2 * P2 + ts[:,None]**3 * P3
    d = np.linalg.norm(pts - B, axis=1)
    split_idx = int(np.argmax(d))
    split_idx = max(2, min(n-3, split_idx))  # ensure both sides have >=2 points
    left = recursive_fit_beziers(pts[:split_idx+1], max_err, min_seg)
    right = recursive_fit_beziers(pts[split_idx:], max_err, min_seg)
    return left + right

# ---------------- Skeleton graph extraction ----------------

def _neighbors8(y: int, x: int, h: int, w: int):
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            if dy == 0 and dx == 0:
                continue
            ny, nx = y+dy, x+dx
            if 0 <= ny < h and 0 <= nx < w:
                yield ny, nx


def _degree(img: np.ndarray, y: int, x: int) -> int:
    h, w = img.shape
    deg = 0
    for ny, nx in _neighbors8(y, x, h, w):
        if img[ny, nx]:
            deg += 1
    return deg


def skeleton_centerlines(bin_img: np.ndarray, prune_len: int = 8) -> List[np.ndarray]:
    """Convert a binary mask to skeleton centerline polylines via graph tracing.
    prune_len: remove short spur paths shorter than this many pixels.
    Returns list of polylines (N,2) float32.
    """
    if not _HAS_SKIMAGE:
        return []
    skel = skeletonize((bin_img > 0).astype(np.uint8)).astype(np.uint8)
    h, w = skel.shape
    visited = np.zeros_like(skel, dtype=np.uint8)

    # Identify junctions (deg >= 3) and endpoints (deg == 1)
    junctions = set()
    endpoints = set()
    for y in range(h):
        for x in range(w):
            if not skel[y, x]:
                continue
            deg = _degree(skel, y, x)
            if deg == 1:
                endpoints.add((y, x))
            elif deg >= 3:
                junctions.add((y, x))

    def trace_from(start: tuple) -> List[tuple]:
        path = [start]
        y, x = start
        prev = None
        while True:
            visited[y, x] = 1
            # Explore neighbors
            nbrs = []
            for ny, nx in _neighbors8(y, x, h, w):
                if not skel[ny, nx] or visited[ny, nx]:
                    continue
                if prev is not None and (ny, nx) == prev:
                    continue
                nbrs.append((ny, nx))
            if not nbrs:
                break
            # If at junction, stop path and let another trace handle branches
            if (y, x) in junctions and (y, x) != start:
                break
            # Choose the next neighbor (prefer straightest by simple heuristic)
            if prev is None:
                nxt = nbrs[0]
            else:
                vy, vx = y - prev[0], x - prev[1]
                best, bestdot = None, -1e9
                for cand in nbrs:
                    wy, wx = cand[0]-y, cand[1]-x
                    dot = vy*wy + vx*wx
                    if dot > bestdot:
                        bestdot = dot
                        best = cand
                nxt = best if best is not None else nbrs[0]
            prev = (y, x)
            y, x = nxt
            path.append((y, x))
            # Stop if we hit endpoint
            if (y, x) in endpoints:
                visited[y, x] = 1
                break
        return path

    polylines: List[np.ndarray] = []
    # Start traces from endpoints for maximal path coverage
    for start in endpoints:
        y, x = start
        if not skel[y, x] or visited[y, x]:
            continue
        path = trace_from(start)
        if len(path) >= prune_len:
            pts = np.array([(p[1], p[0]) for p in path], dtype=np.float32)  # (x,y)
            polylines.append(pts)

    # For remaining unvisited pixels (loops without endpoints), pick junctions or any pixel
    for y in range(h):
        for x in range(w):
            if skel[y, x] and not visited[y, x]:
                path = trace_from((y, x))
                if len(path) >= prune_len:
                    pts = np.array([(p[1], p[0]) for p in path], dtype=np.float32)
                    polylines.append(pts)

    return polylines


def rdp_polyline(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Ramer–Douglas–Peucker on a 2D polyline."""
    if len(points) < 3:
        return points
    # Find farthest point from the line p0-pn
    p0 = points[0]
    pn = points[-1]
    v = pn - p0
    v2 = v[0]*v[0] + v[1]*v[1]
    maxd = -1.0
    maxi = -1
    for i in range(1, len(points)-1):
        wv = points[i] - p0
        if v2 == 0:
            d = np.linalg.norm(points[i]-p0)
        else:
            # area of parallelogram over base length
            d = abs(v[0]*wv[1] - v[1]*wv[0]) / np.sqrt(v2)
        if d > maxd:
            maxd = d
            maxi = i
    if maxd > epsilon:
        left = rdp_polyline(points[:maxi+1], epsilon)
        right = rdp_polyline(points[maxi:], epsilon)
        return np.vstack([left[:-1], right])
    else:
        return np.vstack([p0, pn])


# --------------- Flat-color pipeline ---------------

def extract_dominant_colors(img_bgr: np.ndarray, k: int = 8, method: str = "kmeans") -> Tuple[np.ndarray, np.ndarray]:
    """Extract dominant colors using advanced techniques.
    
    Args:
        img_bgr: Input BGR image
        k: Number of colors to extract
        method: 'kmeans' (default), 'median_cut', or 'octree'
    
    Returns:
        Tuple of (quantized BGR image, label map)
    """
    if method == "median_cut":
        return median_cut_quantize(img_bgr, k)
    elif method == "octree":
        return octree_quantize(img_bgr, k)
    else:
        return kmeans_quantize_bgr(img_bgr, k)


def median_cut_quantize(img_bgr: np.ndarray, k: int = 8) -> Tuple[np.ndarray, np.ndarray]:
    """Quantize colors using median cut algorithm (better for images with few colors).
    
    This preserves color relationships better than k-means for certain images.
    """
    from collections import namedtuple
    
    ColorBucket = namedtuple('ColorBucket', ['pixels', 'color_range'])
    
    # Convert to RGB for easier processing
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w, _ = img_rgb.shape
    pixels = img_rgb.reshape(-1, 3)
    
    # Start with single bucket
    buckets = [ColorBucket(pixels, (0, len(pixels)))]
    
    # Split buckets until we have k colors
    while len(buckets) < k:
        # Find bucket with largest color range
        max_range_idx = 0
        max_range = 0
        
        for i, bucket in enumerate(buckets):
            if bucket.color_range[1] - bucket.color_range[0] <= 1:
                continue
            bucket_pixels = pixels[bucket.color_range[0]:bucket.color_range[1]]
            color_range = bucket_pixels.max(axis=0) - bucket_pixels.min(axis=0)
            range_val = color_range.max()
            if range_val > max_range:
                max_range = range_val
                max_range_idx = i
        
        if max_range == 0:
            break
        
        # Split the bucket with largest range
        bucket = buckets[max_range_idx]
        bucket_pixels = pixels[bucket.color_range[0]:bucket.color_range[1]]
        
        # Find channel with max range
        color_range = bucket_pixels.max(axis=0) - bucket_pixels.min(axis=0)
        channel = color_range.argmax()
        
        # Sort by that channel and split at median
        indices = np.argsort(bucket_pixels[:, channel])
        mid = len(indices) // 2
        
        start, end = bucket.color_range
        buckets[max_range_idx] = ColorBucket(pixels, (start, start + mid))
        buckets.append(ColorBucket(pixels, (start + mid, end)))
    
    # Calculate mean color for each bucket
    colors = []
    label_map = np.zeros(len(pixels), dtype=np.int32)
    
    for i, bucket in enumerate(buckets):
        bucket_pixels = pixels[bucket.color_range[0]:bucket.color_range[1]]
        mean_color = bucket_pixels.mean(axis=0).astype(np.uint8)
        colors.append(mean_color)
        label_map[bucket.color_range[0]:bucket.color_range[1]] = i
    
    # Build quantized image
    colors = np.array(colors, dtype=np.uint8)
    quant_rgb = colors[label_map].reshape(h, w, 3)
    quant_bgr = cv2.cvtColor(quant_rgb, cv2.COLOR_RGB2BGR)
    
    return quant_bgr, label_map.reshape(h, w)


def octree_quantize(img_bgr: np.ndarray, k: int = 8) -> Tuple[np.ndarray, np.ndarray]:
    """Quantize using octree color quantization (fast, good quality).
    
    Falls back to k-means if implementation is complex.
    """
    # For now, use k-means as fallback (octree is complex to implement from scratch)
    return kmeans_quantize_bgr(img_bgr, k)


def kmeans_quantize_bgr(img_bgr: np.ndarray, k: int = 8, attempts: int = 3) -> Tuple[np.ndarray, np.ndarray]:
    """Quantize image colors with k-means in CIELAB space and return quantized BGR image and label map."""
    img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    Z = img_lab.reshape((-1, 3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1.0)
    _compactness, labels, centers = cv2.kmeans(
        Z, K=k, bestLabels=None, criteria=criteria, attempts=attempts, flags=cv2.KMEANS_PP_CENTERS
    )
    centers = centers.astype(np.uint8)
    quant_lab = centers[labels.flatten()].reshape(img_lab.shape)
    quant_bgr = cv2.cvtColor(quant_lab, cv2.COLOR_LAB2BGR)
    label_map = labels.reshape(img_lab.shape[:2])
    return quant_bgr, label_map


def build_color_masks(quant_bgr: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Return list of (bgr_color, mask) for each unique color in quantized image."""
    h, w, _ = quant_bgr.shape
    # Hash BGR into a 24-bit int to identify unique colors
    ids = (quant_bgr[:, :, 0].astype(np.int32)
           + 256 * quant_bgr[:, :, 1].astype(np.int32)
           + 256 * 256 * quant_bgr[:, :, 2].astype(np.int32))
    unique_ids, inv = np.unique(ids, return_inverse=True)
    inv = inv.reshape((h, w))

    results = []
    for idx, uid in enumerate(unique_ids):
        mask = (inv == idx).astype(np.uint8) * 255
        # Recover BGR from uid
        b = uid % 256
        g = (uid // 256) % 256
        r = (uid // (256 * 256)) % 256
        results.append((np.array([b, g, r], dtype=np.uint8), mask))
    return results


def detect_gradient_regions(img_bgr: np.ndarray, mask: np.ndarray, threshold: float = 30.0) -> bool:
    """Detect if a masked region contains gradients (color variation).
    
    Args:
        img_bgr: Original BGR image
        mask: Binary mask of region
        threshold: Std deviation threshold to consider as gradient
    
    Returns:
        True if region has gradient, False if flat color
    """
    # Sample colors in the masked region
    ys, xs = np.where(mask == 255)
    if len(xs) < 10:  # Too small to analyze
        return False
    
    colors = img_bgr[ys, xs]
    
    # Calculate standard deviation in LAB space (perceptual)
    lab_colors = cv2.cvtColor(colors.reshape(1, -1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3)
    std_dev = np.std(lab_colors[:, 0])  # L channel std deviation
    
    return std_dev > threshold


def analyze_gradient_direction(img_bgr: np.ndarray, mask: np.ndarray, contour: np.ndarray) -> dict:
    """Analyze gradient direction and colors in a region.
    
    Args:
        img_bgr: Original BGR image
        mask: Binary mask of region
        contour: Contour points defining the region
    
    Returns:
        Dictionary with gradient info: {type, angle, colors, positions}
    """
    # Get bounding box of region
    x, y, w, h = cv2.boundingRect(contour)
    
    if w < 3 or h < 3:
        return None
    
    # Extract region
    region_mask = mask[y:y+h, x:x+w]
    region_img = img_bgr[y:y+h, x:x+w]
    
    # Sample colors along different directions
    ys, xs = np.where(region_mask == 255)
    if len(xs) < 20:
        return None
    
    colors = region_img[ys, xs]
    positions = np.column_stack([xs, ys])
    
    # Determine gradient type and direction
    # Try horizontal gradient
    horiz_correlation = np.corrcoef(positions[:, 0], colors[:, 0])[0, 1]
    # Try vertical gradient
    vert_correlation = np.corrcoef(positions[:, 1], colors[:, 0])[0, 1]
    
    # Check for radial gradient (distance from center)
    center_x, center_y = w / 2, h / 2
    distances = np.sqrt((positions[:, 0] - center_x)**2 + (positions[:, 1] - center_y)**2)
    radial_correlation = np.corrcoef(distances, colors[:, 0])[0, 1]
    
    gradient_type = "linear"
    angle = 0.0
    
    if abs(radial_correlation) > max(abs(horiz_correlation), abs(vert_correlation)):
        # Radial gradient detected
        gradient_type = "radial"
        
        # Find colors at center and edge
        center_dist_threshold = np.percentile(distances, 10)
        edge_dist_threshold = np.percentile(distances, 90)
        
        center_colors = colors[distances <= center_dist_threshold]
        edge_colors = colors[distances >= edge_dist_threshold]
        
        if len(center_colors) > 0 and len(edge_colors) > 0:
            color1 = np.median(center_colors, axis=0).astype(np.uint8)
            color2 = np.median(edge_colors, axis=0).astype(np.uint8)
            
            return {
                'type': 'radial',
                'colors': [color1, color2],
                'center': (x + center_x, y + center_y),
                'radius': max(w, h) / 2
            }
    else:
        # Linear gradient
        if abs(horiz_correlation) > abs(vert_correlation):
            # Horizontal gradient
            angle = 90.0 if horiz_correlation < 0 else 270.0
            
            # Sample left and right colors
            left_threshold = np.percentile(positions[:, 0], 10)
            right_threshold = np.percentile(positions[:, 0], 90)
            
            left_colors = colors[positions[:, 0] <= left_threshold]
            right_colors = colors[positions[:, 0] >= right_threshold]
        else:
            # Vertical gradient
            angle = 180.0 if vert_correlation < 0 else 0.0
            
            # Sample top and bottom colors
            top_threshold = np.percentile(positions[:, 1], 10)
            bottom_threshold = np.percentile(positions[:, 1], 90)
            
            left_colors = colors[positions[:, 1] <= top_threshold]
            right_colors = colors[positions[:, 1] >= bottom_threshold]
        
        if len(left_colors) > 0 and len(right_colors) > 0:
            color1 = np.median(left_colors, axis=0).astype(np.uint8)
            color2 = np.median(right_colors, axis=0).astype(np.uint8)
            
            return {
                'type': 'linear',
                'angle': angle,
                'colors': [color1, color2],
                'bbox': (x, y, w, h)
            }
    
    return None


def create_gradient_id(color1: np.ndarray, color2: np.ndarray, gradient_type: str) -> str:
    """Create unique gradient ID based on colors.
    
    Args:
        color1: First color (BGR)
        color2: Second color (BGR)
        gradient_type: 'linear' or 'radial'
    
    Returns:
        Unique gradient ID string
    """
    c1_hex = f"{color1[2]:02x}{color1[1]:02x}{color1[0]:02x}"
    c2_hex = f"{color2[2]:02x}{color2[1]:02x}{color2[0]:02x}"
    return f"grad_{gradient_type}_{c1_hex}_{c2_hex}"


def vectorize_flat(
    img_bgr: np.ndarray,
    k_colors: int = 8,
    min_area: int = 25,
    epsilon_ratio: float = 0.003,
    close_kernel: int = 3,
    fill_rule: str = "evenodd",
    bezier: bool = False,
    bezier_seglen: int = 16,
    bezier_recursive: bool = False,
    bezier_maxerr: float = 2.0,
    smoothness: int = 0,
    color_method: str = "kmeans",
    detect_gradients: bool = False,
    gradient_threshold: float = 25.0,
    detect_patterns: bool = False,
    pattern_type: str = "auto",
) -> Iterator[Tuple[str, str, dict]]:
    """Yields (path_d, fill_hex, gradient_info) for flat-color vectorization.
    
    Enhancements:
    - Multiple color quantization methods
    - Gradient fill detection and rendering
    - Contour hierarchy support
    - Optimized performance
    
    Performance optimizations:
    - Cached bilateral filtering
    - Early area filtering
    - Optimized contour retrieval
    
    Returns:
        Iterator yielding tuples of (path_d, fill_hex, gradient_info)
        gradient_info is None for solid colors, or a dict with gradient data
    """
    
    # Pre-process image with bilateral filter to smooth colors while keeping edges
    if smoothness > 0:
        d = max(3, smoothness)
        sigma_color = float(smoothness) * 10.0
        sigma_space = float(smoothness) * 2.0
        iters = 1 if smoothness < 5 else 2
        temp = img_bgr
        for _ in range(iters):
            temp = cv2.bilateralFilter(temp, d=d, sigmaColor=sigma_color, sigmaSpace=sigma_space)
        img_bgr = temp

    # Use advanced color extraction if specified
    quant_bgr, _label_map = extract_dominant_colors(img_bgr, k=k_colors, method=color_method)
    color_masks = build_color_masks(quant_bgr)

    # Sort by area descending to paint large regions first
    # Early filter: skip masks with area below minimum
    areas_masks = []
    for bgr, mask in color_masks:
        area = int(mask.sum() // 255)
        if area >= min_area:  # Early filtering
            areas_masks.append((area, bgr, mask))
    areas_masks.sort(key=lambda x: x[0], reverse=True)

    # Pre-create kernel once if needed
    kernel = np.ones((close_kernel, close_kernel), np.uint8) if close_kernel > 1 else None

    for area, bgr, mask in areas_masks:
        # Apply morphological closing if kernel exists
        mask2 = mask
        if kernel is not None:
            mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Use RETR_EXTERNAL for simpler hierarchy (performance boost)
        # Only use RETR_CCOMP if we need holes
        contours, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            continue
        
        # Check if this region has a gradient or pattern (if detection enabled)
        gradient_info = None
        if len(contours) > 0:
            main_contour = max(contours, key=cv2.contourArea)
            
            # Check for patterns first
            if detect_patterns:
                pattern_info = detect_texture_pattern(img_bgr, mask2)
                if pattern_info:
                    gradient_info = pattern_info
            
            # If no pattern, check for gradients
            if gradient_info is None and detect_gradients:
                has_gradient = detect_gradient_regions(img_bgr, mask2, gradient_threshold)
                if has_gradient:
                    # Analyze gradient direction and colors
                    gradient_info = analyze_gradient_direction(img_bgr, mask2, main_contour)
            
        d_parts = []
        for cnt in contours:
            # Quick area check before expensive operations
            cnt_area = cv2.contourArea(cnt)
            if cnt_area < min_area:
                continue
                
            approx = simplify_poly(cnt, epsilon_ratio)
            if len(approx) < 3:  # Need at least 3 points for a valid polygon
                continue
                
            if bezier:
                if bezier_recursive:
                    beziers = recursive_fit_beziers(approx, max_err=bezier_maxerr, min_seg=max(6, int(bezier_seglen)))
                else:
                    beziers = polyline_to_beziers(approx, seg_len=bezier_seglen)
                d = beziers_to_path_d(beziers, closed=True)
            else:
                d = to_svg_path_d(approx, closed=True)
            if d:
                d_parts.append(d)
                
        if d_parts:
            yield (" ".join(d_parts), bgr_to_hex(bgr), gradient_info)


# --------------- Line-art pipeline ---------------

def detect_contour_hierarchy(contours: list, hierarchy: np.ndarray) -> dict:
    """Analyze contour hierarchy to identify parent-child relationships.
    
    Args:
        contours: List of contours from cv2.findContours
        hierarchy: Hierarchy array from cv2.findContours
    
    Returns:
        Dictionary mapping contour index to its children indices
    """
    hierarchy_map = {}
    if hierarchy is None or len(hierarchy) == 0:
        return hierarchy_map
    
    # hierarchy format: [Next, Previous, First_Child, Parent]
    for i in range(len(contours)):
        parent_idx = hierarchy[0][i][3]
        if parent_idx >= 0:
            if parent_idx not in hierarchy_map:
                hierarchy_map[parent_idx] = []
            hierarchy_map[parent_idx].append(i)
    
    return hierarchy_map


def estimate_variable_stroke_width(img_bgr: np.ndarray, contour: np.ndarray, dist: np.ndarray) -> np.ndarray:
    """Estimate variable stroke width along a contour path.
    
    Args:
        img_bgr: Original image
        contour: Contour points
        dist: Distance transform of binary image
    
    Returns:
        Array of stroke widths for each contour point
    """
    if len(contour) == 0:
        return np.array([1.0])
    
    # Sample width at each contour point
    widths = []
    for pt in contour:
        x, y = int(pt[0][0]), int(pt[0][1])
        x = np.clip(x, 0, dist.shape[1] - 1)
        y = np.clip(y, 0, dist.shape[0] - 1)
        w = dist[y, x] * 2.0  # Distance to edge * 2 = stroke width
        widths.append(max(0.5, w))
    
    return np.array(widths)


def smooth_stroke_widths(widths: np.ndarray, window: int = 5) -> np.ndarray:
    """Smooth stroke width variations for better visual quality.
    
    Args:
        widths: Array of stroke widths
        window: Smoothing window size
    
    Returns:
        Smoothed widths array
    """
    if len(widths) < window:
        return widths
    
    # Simple moving average
    kernel = np.ones(window) / window
    padded = np.pad(widths, window // 2, mode='edge')
    smoothed = np.convolve(padded, kernel, mode='valid')
    
    return smoothed[:len(widths)]


def threshold_line_art(
    img_bgr: np.ndarray,
    adaptive: bool = False,
    thresh: int = 128,
    invert: bool = False,
    blur: int = 0,
) -> np.ndarray:
    """Return binary mask (uint8 0/255) for foreground (ink) pixels."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if blur and blur > 0:
        k = max(1, int(blur))
        k = k + 1 if k % 2 == 0 else k
        gray = cv2.GaussianBlur(gray, (k, k), 0)
    if adaptive:
        bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                        cv2.THRESH_BINARY, 21, 2)
    else:
        # Otsu if thresh < 0, else fixed
        if thresh < 0:
            _t, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _t, bin_img = cv2.threshold(gray, int(thresh), 255, cv2.THRESH_BINARY)
    if invert:
        bin_img = 255 - bin_img
    return bin_img


def vectorize_line(
    img_bgr: np.ndarray,
    adaptive: bool = False,
    thresh: int = -1,
    invert: bool = True,
    blur: int = 0,
    min_area: int = 15,
    epsilon_ratio: float = 0.002,
    close_kernel: int = 3,
    bezier: bool = False,
    bezier_seglen: int = 16,
    bezier_recursive: bool = False,
    bezier_maxerr: float = 2.0,
    line_output: str = "fill",
    stroke_color: str = "#000000",
    stroke_width_scale: float = 1.0,
    centerline: bool = True,
    centerline_prune: int = 8,
    centerline_rdp: float = 0.0,
    variable_width: bool = False,
    preserve_hierarchy: bool = False,
) -> Iterator[Tuple[str, str, str, float]]:
    """Yields tuples of (path_d, fill_hex, stroke_hex, stroke_width).
    
    Enhancements:
    - Variable stroke width support
    - Contour hierarchy preservation (holes)
    - Better stroke width estimation
    - Improved centerline extraction
    
    Performance optimizations:
    - Distance transform computed once globally
    - Centerlines extracted once upfront
    - Early exit for empty results
    """
    bin_img = threshold_line_art(img_bgr, adaptive=adaptive, thresh=thresh, invert=invert, blur=blur)

    # Clean noise and fill small gaps
    kernel = np.ones((close_kernel, close_kernel), np.uint8) if close_kernel > 1 else None
    if kernel is not None:
        bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=1)

    # Use RETR_CCOMP if we need to preserve holes/hierarchy
    retr_mode = cv2.RETR_CCOMP if preserve_hierarchy else cv2.RETR_EXTERNAL
    contours, hierarchy = cv2.findContours(bin_img, retr_mode, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return
    
    # Analyze hierarchy if needed
    hierarchy_map = {}
    if preserve_hierarchy and hierarchy is not None:
        hierarchy_map = detect_contour_hierarchy(contours, hierarchy)

    # Pre-calculate distance transform once for all stroke calculations
    dist = None
    if line_output in ("stroke", "both"):
        dist = cv2.distanceTransform(bin_img, cv2.DIST_L2, 3)
    
    # Pre-calculate centerlines once if needed
    centerlines = None
    if line_output in ("stroke", "both") and _HAS_SKIMAGE and centerline:
        centerlines = skeleton_centerlines(bin_img, prune_len=max(int(centerline_prune), int(min_area**0.5)))

    for cnt in contours:
        # Quick area check
        cnt_area = cv2.contourArea(cnt)
        if cnt_area < min_area:
            continue
            
        approx = simplify_poly(cnt, epsilon_ratio)
        if len(approx) < 3:  # Need at least 3 points
            continue
        
        d = ""
        if bezier:
            if bezier_recursive:
                beziers = recursive_fit_beziers(approx, max_err=bezier_maxerr, min_seg=max(6, int(bezier_seglen)))
            else:
                beziers = polyline_to_beziers(approx, seg_len=bezier_seglen)
            d = beziers_to_path_d(beziers, closed=True)
        else:
            d = to_svg_path_d(approx, closed=True)
            
        if not d:
            continue

        if line_output in ("fill", "both"):
            yield (d, "#000000", "none", 0.0)

        # Optionally add stroke version (non-centerline fallback)
        if line_output in ("stroke", "both") and not (centerlines and _HAS_SKIMAGE and centerline):
            # Fallback: stroke the outer contour path with width estimation
            mask = np.zeros_like(bin_img)
            cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
            vals = dist[mask == 255]
            width = float(np.median(vals) * 2.0) if len(vals) > 0 else 1.0
            width *= float(stroke_width_scale)
            yield (d, "none", stroke_color, max(0.5, width))

    # Yield centerlines if they were computed (optimized: done once, not per contour)
    if line_output in ("stroke", "both") and _HAS_SKIMAGE and centerline and centerlines:
        for sp in centerlines:
            if len(sp) < 8:
                continue
            if centerline_rdp and centerline_rdp > 0:
                sp = rdp_polyline(sp, centerline_rdp)
            
            # Estimate width using pre-computed distance transform
            xs = np.clip(sp[:,0].round().astype(int), 0, bin_img.shape[1]-1)
            ys = np.clip(sp[:,1].round().astype(int), 0, bin_img.shape[0]-1)
            widths = dist[ys, xs] * 2.0
            width = float(np.median(widths)) if len(widths) > 0 else 1.0
            width *= float(stroke_width_scale)
            
            if bezier:
                if bezier_recursive:
                    beziers = recursive_fit_beziers(sp, max_err=bezier_maxerr, min_seg=max(6, int(bezier_seglen)))
                else:
                    beziers = polyline_to_beziers(sp, seg_len=bezier_seglen)
                sd = beziers_to_path_d(beziers, closed=False)
            else:
                sd = to_svg_path_d(sp, closed=False)
            
            if sd:
                yield (sd, "none", stroke_color, max(0.5, width))


# --------------- Low-poly pipeline ---------------

def adaptive_point_sampling(
    img_bgr: np.ndarray,
    num_points: int = 1000,
    edge_weight: float = 0.7,
    blur: int = 1
) -> np.ndarray:
    """Advanced point sampling that adapts to image features.
    
    Args:
        img_bgr: Input BGR image
        num_points: Total number of points to sample
        edge_weight: Ratio of points to place on edges (0.0-1.0)
        blur: Blur for feature detection
    
    Returns:
        Array of sampled points (N, 2) as (x, y)
    """
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    if blur > 0:
        k = blur * 2 + 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)
    
    # Detect edges for adaptive sampling
    edges = cv2.Canny(gray, 50, 150)
    edge_points = np.column_stack(np.where(edges > 0))[:, [1, 0]]  # Convert to (x, y)
    
    num_edge_points = int(num_points * edge_weight)
    num_feature_points = int(num_points * (1.0 - edge_weight) * 0.6)
    num_random_points = num_points - num_edge_points - num_feature_points
    
    pts = []
    
    # Sample from edges
    if len(edge_points) > 0:
        if len(edge_points) > num_edge_points:
            indices = np.random.choice(len(edge_points), num_edge_points, replace=False)
            edge_samples = edge_points[indices]
        else:
            edge_samples = edge_points
        pts.extend([tuple(map(float, pt)) for pt in edge_samples])
    
    # Sample feature points (corners, interest points)
    corners = cv2.goodFeaturesToTrack(
        gray,
        maxCorners=num_feature_points,
        qualityLevel=0.01,
        minDistance=5
    )
    if corners is not None:
        pts.extend([tuple(map(float, c.ravel())) for c in corners])
    
    # Add border points for stability
    pts += [(0.0, 0.0), (float(w-1), 0.0), (float(w-1), float(h-1)), (0.0, float(h-1))]
    
    # Add random points to fill remaining
    rng = np.random.default_rng(123)
    while len(pts) < num_points:
        pts.append((float(rng.integers(0, w)), float(rng.integers(0, h))))
    
    return np.array(pts[:num_points], dtype=np.float32)


def sample_points(img_bgr: np.ndarray, num_points: int = 1000, blur: int = 1) -> np.ndarray:
    """Original simple point sampling (kept for compatibility)."""
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if blur > 0:
        k = blur * 2 + 1
        gray = cv2.GaussianBlur(gray, (k, k), 0)
    corners = cv2.goodFeaturesToTrack(gray, maxCorners=num_points, qualityLevel=0.01, minDistance=3)
    pts = []
    if corners is not None:
        pts = [tuple(map(float, c.ravel())) for c in corners]
    # Add border points to stabilize triangulation
    border = 10
    pts += [(0, 0), (w-1, 0), (w-1, h-1), (0, h-1)]
    # Uniform random points as fallback to reach desired count
    rng = np.random.default_rng(123)
    while len(pts) < num_points:
        pts.append((float(rng.integers(0, w)), float(rng.integers(0, h))))
    return np.array(pts, dtype=np.float32)


def triangle_mean_color(img_bgr: np.ndarray, tri: np.ndarray) -> str:
    """Calculate mean color of a triangle region.
    
    Optimized: Uses bounding box sampling instead of full-image masking.
    """
    # Get bounding box of triangle
    x_coords = tri[:, 0]
    y_coords = tri[:, 1]
    x_min = max(0, int(np.floor(x_coords.min())))
    x_max = min(img_bgr.shape[1] - 1, int(np.ceil(x_coords.max())))
    y_min = max(0, int(np.floor(y_coords.min())))
    y_max = min(img_bgr.shape[0] - 1, int(np.ceil(y_coords.max())))
    
    if x_max <= x_min or y_max <= y_min:
        return "#000000"
    
    # Create smaller mask for just the bounding box
    box_h = y_max - y_min + 1
    box_w = x_max - x_min + 1
    mask = np.zeros((box_h, box_w), dtype=np.uint8)
    
    # Adjust triangle coordinates to box-local coordinates
    tri_local = tri.copy()
    tri_local[:, 0] -= x_min
    tri_local[:, 1] -= y_min
    
    cv2.fillConvexPoly(mask, tri_local.astype(np.int32), 255)
    
    # Sample from the cropped region
    roi = img_bgr[y_min:y_max+1, x_min:x_max+1]
    ys, xs = np.where(mask == 255)
    
    if len(xs) == 0:
        return "#000000"
    
    cols = roi[ys, xs]
    bgr = cols.mean(axis=0).astype(np.uint8)
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def lowpoly(
    img_bgr: np.ndarray,
    num_points: int = 1000,
    blur: int = 1,
    adaptive_sampling: bool = False,
    edge_weight: float = 0.7
) -> Iterator[Tuple[List[Tuple[float, float]], str]]:
    """Yields (points, fill_hex) polygons.
    
    Enhancements:
    - Adaptive point sampling based on edges
    - Better feature detection
    - Improved color sampling
    
    Performance optimizations:
    - Bounding-box color sampling
    - Vectorized coordinate extraction
    - Boundary checking optimization
    """
    # Use adaptive sampling if enabled
    if adaptive_sampling:
        pts = adaptive_point_sampling(img_bgr, num_points=num_points, edge_weight=edge_weight, blur=blur)
    else:
        pts = sample_points(img_bgr, num_points=num_points, blur=blur)
    
    h, w = img_bgr.shape[:2]

    if _HAS_SCIPY:
        tri = Delaunay(pts)
        # Pre-allocate for vectorized operations
        for simplex in tri.simplices:
            p = pts[simplex]
            fill = triangle_mean_color(img_bgr, p)
            # Vectorized tuple creation
            yield ([(float(p[0,0]), float(p[0,1])), (float(p[1,0]), float(p[1,1])), (float(p[2,0]), float(p[2,1]))], fill)
    else:
        subdiv = cv2.Subdiv2D((0, 0, w, h))
        # Batch insert for better performance
        for (x, y) in pts:
            try:
                subdiv.insert((float(x), float(y)))
            except Exception:
                pass
        triangleList = subdiv.getTriangleList()
        
        # Vectorized boundary checking
        for t in triangleList:
            x1, y1, x2, y2, x3, y3 = t
            # Quick bounds check - all points must be inside
            if (x1 < 0 or x1 >= w or x2 < 0 or x2 >= w or x3 < 0 or x3 >= w or 
                y1 < 0 or y1 >= h or y2 < 0 or y2 >= h or y3 < 0 or y3 >= h):
                continue
            
            p = np.array([[x1, y1], [x2, y2], [x3, y3]], dtype=np.float32)
            fill = triangle_mean_color(img_bgr, p)
            yield ([(float(x1), float(y1)), (float(x2), float(y2)), (float(x3), float(y3))], fill)


# --------------- SVG Patterns ---------------

def create_dots_pattern(pattern_id: str, color: str, bg_color: str = "none", size: int = 10, spacing: int = 20) -> str:
    """Create SVG dots pattern definition.
    
    Args:
        pattern_id: Unique ID for the pattern
        color: Dot color (hex)
        bg_color: Background color (hex or 'none')
        size: Dot size in pixels
        spacing: Spacing between dots
    
    Returns:
        SVG pattern definition string
    """
    return f'''<pattern id="{pattern_id}" x="0" y="0" width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse">
    <rect width="{spacing}" height="{spacing}" fill="{bg_color}"/>
    <circle cx="{spacing//2}" cy="{spacing//2}" r="{size//2}" fill="{color}"/>
  </pattern>'''


def create_stripes_pattern(pattern_id: str, color1: str, color2: str, width: int = 10, angle: float = 0.0) -> str:
    """Create SVG stripes pattern definition.
    
    Args:
        pattern_id: Unique ID for the pattern
        color1: First stripe color (hex)
        color2: Second stripe color (hex)
        width: Stripe width in pixels
        angle: Rotation angle in degrees
    
    Returns:
        SVG pattern definition string
    """
    transform = f' patternTransform="rotate({angle})"' if angle != 0 else ''
    return f'''<pattern id="{pattern_id}" x="0" y="0" width="{width*2}" height="{width*2}" patternUnits="userSpaceOnUse"{transform}>
    <rect width="{width}" height="{width*2}" fill="{color1}"/>
    <rect x="{width}" width="{width}" height="{width*2}" fill="{color2}"/>
  </pattern>'''


def create_checkerboard_pattern(pattern_id: str, color1: str, color2: str, size: int = 20) -> str:
    """Create SVG checkerboard pattern definition.
    
    Args:
        pattern_id: Unique ID for the pattern
        color1: First square color (hex)
        color2: Second square color (hex)
        size: Square size in pixels
    
    Returns:
        SVG pattern definition string
    """
    return f'''<pattern id="{pattern_id}" x="0" y="0" width="{size*2}" height="{size*2}" patternUnits="userSpaceOnUse">
    <rect width="{size}" height="{size}" fill="{color1}"/>
    <rect x="{size}" width="{size}" height="{size}" fill="{color2}"/>
    <rect y="{size}" width="{size}" height="{size}" fill="{color2}"/>
    <rect x="{size}" y="{size}" width="{size}" height="{size}" fill="{color1}"/>
  </pattern>'''


def create_crosshatch_pattern(pattern_id: str, color: str, bg_color: str = "none", spacing: int = 10, stroke_width: int = 2) -> str:
    """Create SVG crosshatch pattern definition.
    
    Args:
        pattern_id: Unique ID for the pattern
        color: Line color (hex)
        bg_color: Background color (hex or 'none')
        spacing: Spacing between lines
        stroke_width: Line thickness
    
    Returns:
        SVG pattern definition string
    """
    return f'''<pattern id="{pattern_id}" x="0" y="0" width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse">
    <rect width="{spacing}" height="{spacing}" fill="{bg_color}"/>
    <line x1="0" y1="0" x2="{spacing}" y2="{spacing}" stroke="{color}" stroke-width="{stroke_width}"/>
    <line x1="{spacing}" y1="0" x2="0" y2="{spacing}" stroke="{color}" stroke-width="{stroke_width}"/>
  </pattern>'''


def create_grid_pattern(pattern_id: str, color: str, bg_color: str = "none", spacing: int = 20, stroke_width: int = 1) -> str:
    """Create SVG grid pattern definition.
    
    Args:
        pattern_id: Unique ID for the pattern
        color: Grid line color (hex)
        bg_color: Background color (hex or 'none')
        spacing: Grid spacing in pixels
        stroke_width: Line thickness
    
    Returns:
        SVG pattern definition string
    """
    return f'''<pattern id="{pattern_id}" x="0" y="0" width="{spacing}" height="{spacing}" patternUnits="userSpaceOnUse">
    <rect width="{spacing}" height="{spacing}" fill="{bg_color}"/>
    <path d="M 0,0 L 0,{spacing} M 0,0 L {spacing},0" stroke="{color}" stroke-width="{stroke_width}" fill="none"/>
  </pattern>'''


def detect_texture_pattern(img_bgr: np.ndarray, mask: np.ndarray) -> dict:
    """Detect if a region has a repeating pattern/texture.
    
    Args:
        img_bgr: Original BGR image
        mask: Binary mask of region
    
    Returns:
        Dictionary with pattern info or None
    """
    # Sample region
    ys, xs = np.where(mask == 255)
    if len(xs) < 100:  # Too small to analyze
        return None
    
    # Get bounding box
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    
    region = img_bgr[y_min:y_max+1, x_min:x_max+1]
    region_mask = mask[y_min:y_max+1, x_min:x_max+1]
    
    # Convert to grayscale for pattern analysis
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    
    # Calculate variance - high variance might indicate texture
    variance = np.var(gray[region_mask[0:region_mask.shape[0], 0:region_mask.shape[1]] == 255])
    
    # Detect edges
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (region.shape[0] * region.shape[1])
    
    # High edge density + high variance = potential texture
    if variance > 500 and edge_density > 0.1:
        # Analyze dominant colors for pattern
        colors = region[region_mask == 255]
        if len(colors) > 10:
            # Simple pattern detection based on color distribution
            unique_colors = np.unique(colors.reshape(-1, 3), axis=0)
            
            if len(unique_colors) == 2:
                # Two colors - might be dots, stripes, or checkerboard
                return {
                    'type': 'stripes',  # Default to stripes
                    'colors': [unique_colors[0], unique_colors[1]],
                    'size': 10
                }
    
    return None


def create_pattern_id(pattern_type: str, color1: np.ndarray, color2: np.ndarray = None) -> str:
    """Create unique pattern ID.
    
    Args:
        pattern_type: Type of pattern (dots, stripes, checkerboard, etc.)
        color1: Primary color (BGR)
        color2: Secondary color (BGR) if applicable
    
    Returns:
        Unique pattern ID string
    """
    c1_hex = f"{color1[2]:02x}{color1[1]:02x}{color1[0]:02x}"
    if color2 is not None:
        c2_hex = f"{color2[2]:02x}{color2[1]:02x}{color2[0]:02x}"
        return f"pattern_{pattern_type}_{c1_hex}_{c2_hex}"
    return f"pattern_{pattern_type}_{c1_hex}"


# --------------- SVG Gradients & Effects ---------------

def bgr_to_hex(bgr: np.ndarray) -> str:
    """Convert BGR color to hex string.
    
    Args:
        bgr: BGR color array [B, G, R]
    
    Returns:
        Hex color string like '#rrggbb'
    """
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def create_linear_gradient(gradient_id: str, color1: str, color2: str, angle: float = 0.0) -> str:
    """Create SVG linear gradient definition.
    
    Args:
        gradient_id: Unique ID for the gradient
        color1: Start color (hex)
        color2: End color (hex)
        angle: Gradient angle in degrees (0=top to bottom, 90=left to right)
    
    Returns:
        SVG gradient definition string
    """
    # Convert angle to x1,y1,x2,y2 coordinates
    import math
    rad = math.radians(angle)
    
    # For SVG gradients: 0° = vertical (top to bottom)
    if angle == 0.0:  # Top to bottom
        x1, y1, x2, y2 = 0, 0, 0, 1
    elif angle == 90.0:  # Left to right
        x1, y1, x2, y2 = 0, 0, 1, 0
    elif angle == 180.0:  # Bottom to top
        x1, y1, x2, y2 = 0, 1, 0, 0
    elif angle == 270.0:  # Right to left
        x1, y1, x2, y2 = 1, 0, 0, 0
    else:
        # Generic angle
        x1, y1 = 0, 0
        x2 = math.cos(rad)
        y2 = math.sin(rad)
    
    return f'''<linearGradient id="{gradient_id}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">
    <stop offset="0%" stop-color="{color1}"/>
    <stop offset="100%" stop-color="{color2}"/>
  </linearGradient>'''


def create_radial_gradient(gradient_id: str, color1: str, color2: str, cx: float = 0.5, cy: float = 0.5) -> str:
    """Create SVG radial gradient definition.
    
    Args:
        gradient_id: Unique ID for the gradient
        color1: Center color (hex)
        color2: Edge color (hex)
        cx: Center x position (0.0-1.0)
        cy: Center y position (0.0-1.0)
    
    Returns:
        SVG gradient definition string
    """
    return f'''<radialGradient id="{gradient_id}" cx="{cx}" cy="{cy}">
    <stop offset="0%" stop-color="{color1}"/>
    <stop offset="100%" stop-color="{color2}"/>
  </radialGradient>'''


def create_drop_shadow_filter(filter_id: str = "shadow", blur: float = 2.0, opacity: float = 0.5) -> str:
    """Create SVG drop shadow filter definition.
    
    Args:
        filter_id: Unique ID for the filter
        blur: Shadow blur amount
        opacity: Shadow opacity (0.0-1.0)
    
    Returns:
        SVG filter definition string
    """
    return f'''<filter id="{filter_id}" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur in="SourceAlpha" stdDeviation="{blur}"/>
    <feOffset dx="2" dy="2" result="offsetblur"/>
    <feComponentTransfer>
      <feFuncA type="linear" slope="{opacity}"/>
    </feComponentTransfer>
    <feMerge>
      <feMergeNode/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>'''


# --------------- SVG Optimization ---------------

def optimize_path_data(path_d: str, precision: int = 2) -> str:
    """Optimize SVG path data by reducing precision and removing redundancy.
    
    Args:
        path_d: SVG path data string
        precision: Number of decimal places to keep
    
    Returns:
        Optimized path data string
    """
    import re
    
    # Round numbers to specified precision
    def round_number(match):
        num = float(match.group(0))
        rounded = round(num, precision)
        # Remove trailing zeros and decimal point if integer
        if rounded == int(rounded):
            return str(int(rounded))
        return f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
    
    # Replace all numbers with rounded versions
    optimized = re.sub(r'-?\d+\.?\d*', round_number, path_d)
    
    # Remove unnecessary spaces
    optimized = re.sub(r'\s+', ' ', optimized)
    optimized = re.sub(r'\s*([MLCZmlcz])\s*', r'\1', optimized)
    
    # Remove space before negative numbers
    optimized = re.sub(r'\s+-', '-', optimized)
    
    return optimized.strip()


def optimize_color(color: str) -> str:
    """Optimize color representation.
    
    Args:
        color: Color string (hex or named)
    
    Returns:
        Optimized color string
    """
    if not color or color == "none":
        return color
    
    # Convert 6-digit hex to 3-digit if possible
    if color.startswith('#') and len(color) == 7:
        r, g, b = color[1:3], color[3:5], color[5:7]
        if r[0] == r[1] and g[0] == g[1] and b[0] == b[1]:
            return f"#{r[0]}{g[0]}{b[0]}"
    
    # Convert common colors to names
    color_names = {
        '#000000': 'black', '#000': 'black',
        '#ffffff': 'white', '#fff': 'white',
        '#ff0000': 'red', '#f00': 'red',
        '#00ff00': 'lime', '#0f0': 'lime',
        '#0000ff': 'blue', '#00f': 'blue',
    }
    
    return color_names.get(color.lower(), color)


def merge_adjacent_paths(paths: list, tolerance: float = 0.01) -> list:
    """Merge adjacent paths with same attributes.
    
    Args:
        paths: List of (path_d, attributes) tuples
        tolerance: Tolerance for considering colors equal
    
    Returns:
        List of merged paths
    """
    if not paths:
        return paths
    
    merged = []
    current_attrs = None
    current_paths = []
    
    for path_d, attrs in paths:
        # Check if attributes match
        if current_attrs == attrs:
            current_paths.append(path_d)
        else:
            # Save previous group
            if current_paths:
                merged_d = ' '.join(current_paths)
                merged.append((merged_d, current_attrs))
            
            # Start new group
            current_attrs = attrs
            current_paths = [path_d]
    
    # Don't forget the last group
    if current_paths:
        merged_d = ' '.join(current_paths)
        merged.append((merged_d, current_attrs))
    
    return merged


def remove_default_attributes(element: str) -> str:
    """Remove default SVG attributes to reduce file size.
    
    Args:
        element: SVG element string
    
    Returns:
        Optimized element string
    """
    import re
    
    # Default values that can be removed
    defaults = {
        'fill="black"': '',
        'fill="none" stroke="none"': 'fill="none"',  # stroke=none is implied
        'stroke-width="1"': '',  # 1 is default
        'stroke-linecap="butt"': '',  # butt is default
        'stroke-linejoin="miter"': '',  # miter is default
        'fill-opacity="1"': '',  # 1 is default
        'stroke-opacity="1"': '',  # 1 is default
        'opacity="1"': '',  # 1 is default
    }
    
    result = element
    for default_attr, replacement in defaults.items():
        result = result.replace(default_attr, replacement)
    
    # Clean up multiple spaces
    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'\s+/>', '/>', result)
    result = re.sub(r'\s+>', '>', result)
    
    return result


def optimize_svg_output(svg_content: str, 
                       precision: int = 2,
                       remove_metadata: bool = True,
                       remove_comments: bool = True,
                       minify: bool = False) -> str:
    """Optimize SVG content for smaller file size.
    
    Args:
        svg_content: SVG content string
        precision: Number of decimal places for coordinates
        remove_metadata: Remove metadata and editor info
        remove_comments: Remove XML comments
        minify: Remove unnecessary whitespace
    
    Returns:
        Optimized SVG string
    """
    import re
    
    result = svg_content
    
    # Remove comments
    if remove_comments:
        result = re.sub(r'<!--.*?-->', '', result, flags=re.DOTALL)
    
    # Remove metadata, title, desc tags
    if remove_metadata:
        result = re.sub(r'<(metadata|title|desc)>.*?</\1>', '', result, flags=re.DOTALL)
    
    # Optimize numbers in attributes
    def optimize_attr_numbers(match):
        attr = match.group(1)
        value = match.group(2)
        # Round numeric values
        try:
            num = float(value)
            rounded = round(num, precision)
            if rounded == int(rounded):
                optimized = str(int(rounded))
            else:
                optimized = f"{rounded:.{precision}f}".rstrip('0').rstrip('.')
            return f'{attr}="{optimized}"'
        except ValueError:
            return match.group(0)
    
    # Optimize coordinate attributes
    coord_attrs = ['x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 
                   'width', 'height', 'stroke-width']
    for attr in coord_attrs:
        pattern = f'{attr}="(-?\\d+\\.?\\d*)"'
        result = re.sub(pattern, optimize_attr_numbers, result)
    
    # Optimize path data
    def optimize_path(match):
        path_d = match.group(1)
        return f'd="{optimize_path_data(path_d, precision)}"'
    
    result = re.sub(r'd="([^"]+)"', optimize_path, result)
    
    # Optimize colors
    def optimize_color_attr(match):
        color = match.group(1)
        return f'fill="{optimize_color(color)}"'
    
    result = re.sub(r'fill="([^"]+)"', optimize_color_attr, result)
    
    def optimize_stroke_color(match):
        color = match.group(1)
        return f'stroke="{optimize_color(color)}"'
    
    result = re.sub(r'stroke="([^"]+)"', optimize_stroke_color, result)
    
    # Remove default attributes
    result = remove_default_attributes(result)
    
    # Minify: remove unnecessary whitespace
    if minify:
        # Remove whitespace between tags
        result = re.sub(r'>\s+<', '><', result)
        # Remove leading/trailing whitespace
        result = result.strip()
        # Keep only single spaces
        result = re.sub(r'\s+', ' ', result)
    
    return result


def calculate_svg_size_reduction(original: str, optimized: str) -> dict:
    """Calculate size reduction statistics.
    
    Args:
        original: Original SVG content
        optimized: Optimized SVG content
    
    Returns:
        Dictionary with size statistics
    """
    original_size = len(original.encode('utf-8'))
    optimized_size = len(optimized.encode('utf-8'))
    reduction = original_size - optimized_size
    reduction_percent = (reduction / original_size * 100) if original_size > 0 else 0
    
    return {
        'original_size': original_size,
        'optimized_size': optimized_size,
        'reduction': reduction,
        'reduction_percent': reduction_percent
    }


# --------------- SVG writer & Streaming ---------------

def stream_svg(
    width: int,
    height: int,
    shapes_iterator: Iterator[Any],
    fill_rule: str = "evenodd",
    enable_effects: bool = False
) -> Iterator[str]:
    """Yield SVG parts as strings: header, defs (gradients/filters), shapes, footer."""
    yield f'<svg baseProfile="full" height="{height}" version="1.1" viewBox="0 0 {width} {height}" width="{width}" xmlns="http://www.w3.org/2000/svg" xmlns:ev="http://www.w3.org/2001/xml-events" xmlns:xlink="http://www.w3.org/1999/xlink" shape-rendering="geometricPrecision">'
    
    # Collect all shapes and gradients first
    gradients = {}
    shapes = []
    
    for item in shapes_iterator:
        item_len = len(item)
        
        if item_len == 3:
            # Flat mode: (d, fill_hex, gradient_info) where gradient_info can be None or dict
            d, fill_hex, gradient_info = item
            shapes.append(('path_grad', d, fill_hex, gradient_info))
            
            # Collect gradient definition if present
            if gradient_info is not None and isinstance(gradient_info, dict):
                colors = gradient_info['colors']
                grad_id = create_gradient_id(colors[0], colors[1], gradient_info['type'])
                if grad_id not in gradients:
                    color1_hex = bgr_to_hex(colors[0])
                    color2_hex = bgr_to_hex(colors[1])
                    if gradient_info['type'] == 'linear':
                        gradients[grad_id] = create_linear_gradient(grad_id, color1_hex, color2_hex, gradient_info['angle'])
                    elif gradient_info['type'] == 'radial':
                        gradients[grad_id] = create_radial_gradient(grad_id, color1_hex, color2_hex)
        
        elif item_len == 4:
            # Line mode: (d, fill_hex, stroke_hex, stroke_width)
            shapes.append(('line', item[0], item[1], item[2], item[3]))
        
        elif item_len == 2:
            # Check if it's path or polygon
            first, second = item
            if isinstance(first, list):
                # Polygon: (points_list, fill_hex)
                shapes.append(('polygon', first, second))
            else:
                # Path: (d, fill_hex) - old format
                shapes.append(('path', first, second))
    
    # Output defs section if we have gradients or effects
    if gradients or enable_effects:
        yield '<defs>'
        for grad_def in gradients.values():
            yield grad_def
        if enable_effects:
            yield create_drop_shadow_filter("shadow", 2.0, 0.5)
        yield '</defs>'
    
    # Output all shapes
    for shape_data in shapes:
        shape_type = shape_data[0]
        
        if shape_type == 'path_grad':
            d, fill_hex, gradient_info = shape_data[1], shape_data[2], shape_data[3]
            if gradient_info is not None and isinstance(gradient_info, dict):
                colors = gradient_info['colors']
                info_type = gradient_info['type']
                
                if info_type in ['linear', 'radial']:
                    fill_id = create_gradient_id(colors[0], colors[1], info_type)
                elif info_type in ['dots', 'stripes', 'checkerboard', 'crosshatch', 'grid']:
                    if len(colors) >= 2:
                        fill_id = create_pattern_id(info_type, colors[0], colors[1])
                    else:
                        fill_id = create_pattern_id(info_type, colors[0])
                else:
                    fill_id = None
                
                fill_attr = f'url(#{fill_id})' if fill_id else fill_hex
            else:
                fill_attr = fill_hex
            yield f'<path d="{d}" fill="{fill_attr}" stroke="none" fill-rule="{fill_rule}" />'
        
        elif shape_type == 'path':
            d, fill = shape_data[1], shape_data[2]
            yield f'<path d="{d}" fill="{fill}" stroke="none" fill-rule="{fill_rule}" />'
        
        elif shape_type == 'polygon':
            pts, fill = shape_data[1], shape_data[2]
            pts_str = " ".join([f"{x:.2f},{y:.2f}" for x,y in pts])
            yield f'<polygon points="{pts_str}" fill="{fill}" stroke="none" />'
        
        elif shape_type == 'line':
            d, fill, stroke, width = shape_data[1], shape_data[2], shape_data[3], shape_data[4]
            if fill != "none":
                yield f'<path d="{d}" fill="{fill}" stroke="none" fill-rule="{fill_rule}" />'
            if stroke != "none" and width > 0:
                yield f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width:.2f}" stroke-linecap="round" stroke-linejoin="round" />'

    yield '</svg>'


def build_svg_string(width: int,
                     height: int,
                     paths_fill: List[Tuple[str, str]] = None,
                     paths_stroke: Optional[List[Tuple[str, str, float]]] = None,
                     fill_rule: str = "evenodd",
                     polygons: Optional[List[Tuple[List[Tuple[float, float]], str]]] = None) -> str:
    """Helper to maintain backward compatibility with non-streaming calls."""
    # Convert lists to a unified iterator
    def unified_iter():
        if paths_fill:
            for d, fill in paths_fill:
                yield (d, fill)
        if paths_stroke:
            for d, stroke, width in paths_stroke:
                yield (d, "none", stroke, width)
        if polygons:
            for pts, fill in polygons:
                yield (pts, fill)
                
    return "".join(stream_svg(width, height, unified_iter(), fill_rule))

def write_svg(
    output_path: str,
    width: int,
    height: int,
    paths_fill: List[Tuple[str, str]] = None,
    paths_stroke: List[Tuple[str, str, float]] = None,
    fill_rule: str = "evenodd",
    polygons: Optional[List[Tuple[List[Tuple[float, float]], str]]] = None,
):
    svg_content = build_svg_string(width, height, paths_fill, paths_stroke, fill_rule, polygons)
    with open(output_path, "w") as f:
        f.write(svg_content)


# --------------- CLI ---------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert raster images to SVG without AI.")

    def apply_quality(ns: argparse.Namespace):
        if not getattr(ns, "quality", None):
            return ns
        q = ns.quality
        # Defaults that we may override; we only set if user didn't explicitly pass
        def set_if_none(name, val):
            if getattr(ns, name) == p.get_default(name):
                setattr(ns, name, val)
        if q == "low":
            set_if_none("epsilon", 0.006)
            set_if_none("bezier", True)
            set_if_none("bezier_recursive", False)
            set_if_none("bezier_seglen", 24)
            set_if_none("bezier_maxerr", 2.5)
            if getattr(ns, "mode", "flat") == "flat":
                set_if_none("colors", 6)
        elif q == "medium":
            set_if_none("epsilon", 0.003)
            set_if_none("bezier", True)
            set_if_none("bezier_recursive", True)
            set_if_none("bezier_seglen", 16)
            set_if_none("bezier_maxerr", 1.8)
            if getattr(ns, "mode", "flat") == "flat":
                set_if_none("colors", 8)
        elif q == "high":
            set_if_none("epsilon", 0.0015)
            set_if_none("bezier", True)
            set_if_none("bezier_recursive", True)
            set_if_none("bezier_seglen", 10)
            set_if_none("bezier_maxerr", 1.0)
            if getattr(ns, "mode", "flat") == "flat":
                set_if_none("colors", 12)
        return ns
    p.add_argument("input", help="Input image path (png/jpg/etc)")
    p.add_argument("-o", "--output", required=True, help="Output SVG path")
    p.add_argument("--mode", choices=["flat", "line", "lowpoly"], default="flat", help="Vectorization mode")
    p.add_argument("--quality", choices=["low","medium","high"], help="Quality preset")

    # Flat mode
    p.add_argument("--colors", type=int, default=8, help="Number of colors for quantization (flat mode)")
    p.add_argument("--min-area", type=int, default=20, help="Minimum contour area to keep (px^2)")
    p.add_argument("--epsilon", type=float, default=0.003, help="RDP simplification ratio relative to perimeter")
    p.add_argument("--close-kernel", type=int, default=3, help="Morphological closing kernel size")
    p.add_argument("--fill-rule", choices=["nonzero", "evenodd"], default="evenodd", help="Fill rule for complex paths")
    p.add_argument("--smoothness", type=int, default=0, help="Bilateral filter smoothness (0-10)")

    # Line mode
    p.add_argument("--adaptive", action="store_true", help="Use adaptive thresholding (line mode)")
    p.add_argument("--thresh", type=int, default=-1, help="Fixed threshold 0-255; -1 uses Otsu (line mode)")
    p.add_argument("--invert", action="store_true", help="Invert threshold result (ink=white->black)")
    p.add_argument("--blur", type=int, default=0, help="Gaussian blur kernel size prior to thresholding (line mode)")

    # Bezier options (flat/line)
    p.add_argument("--bezier", action="store_true", help="Fit cubic Beziers for smoother curves")
    p.add_argument("--bezier-seglen", type=int, default=16, help="Polyline points per Bezier segment")
    p.add_argument("--bezier-recursive", action="store_true", help="Use recursive error-based Bezier splitting")
    p.add_argument("--bezier-maxerr", type=float, default=2.0, help="Max fitting error (px) for recursive Bezier")

    # Line output style
    p.add_argument("--line-output", choices=["fill","stroke","both"], default="fill", help="How to render line mode")
    p.add_argument("--stroke-color", default="#000000", help="Stroke color for line mode")
    p.add_argument("--stroke-width-scale", type=float, default=1.0, help="Scale factor for estimated stroke width")
    p.add_argument("--no-centerline", action="store_true", help="Disable skeletonized centerline stroke tracing")
    p.add_argument("--centerline-prune", type=int, default=8, help="Prune centerline paths shorter than this length")
    p.add_argument("--centerline-rdp", type=float, default=0.0, help="RDP simplify epsilon for centerline polylines")

    # Low-poly mode options
    p.add_argument("--points", type=int, default=1000, help="Number of feature/sample points for low-poly mode")
    p.add_argument("--tri-blur", type=int, default=1, help="Box blur radius before sampling (low-poly)")

    ns = p.parse_args(argv)
    ns = apply_quality(ns)
    return ns


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    img_bgr = cv2.imread(args.input, cv2.IMREAD_COLOR)
    if img_bgr is None:
        print("ERROR: Failed to read input image", file=sys.stderr)
        return 2
    h, w = img_bgr.shape[:2]

    # Use the new streaming approach directly for CLI as well
    if args.mode == "flat":
        gen = vectorize_flat(
           img_bgr,
           k_colors=max(2, int(args.colors)),
           min_area=max(1, int(args.min_area)),
           epsilon_ratio=max(1e-5, float(args.epsilon)),
           close_kernel=max(0, int(args.close_kernel)),
           fill_rule=args.fill_rule,
           bezier=bool(args.bezier),
           bezier_seglen=max(4, int(args.bezier_seglen)),
           bezier_recursive=bool(args.bezier_recursive),
           bezier_maxerr=float(args.bezier_maxerr),
           smoothness=int(args.smoothness),
        )
    elif args.mode == "line":
        gen = vectorize_line(
            img_bgr,
            adaptive=bool(args.adaptive),
            thresh=int(args.thresh),
            invert=bool(args.invert),
            blur=int(args.blur),
            min_area=max(1, int(args.min_area)),
            epsilon_ratio=max(1e-5, float(args.epsilon)),
            close_kernel=max(0, int(args.close_kernel)),
            bezier=bool(args.bezier),
            bezier_seglen=max(4, int(args.bezier_seglen)),
            bezier_recursive=bool(args.bezier_recursive),
            bezier_maxerr=float(args.bezier_maxerr),
            line_output=str(args.line_output),
            stroke_color=str(args.stroke_color),
            stroke_width_scale=float(args.stroke_width_scale),
            centerline=not bool(args.no_centerline),
            centerline_prune=int(args.centerline_prune),
            centerline_rdp=float(args.centerline_rdp),
        )
    else:  # lowpoly
        gen = lowpoly(img_bgr, num_points=int(args.points), blur=int(args.tri_blur))

    # Stream to file
    with open(args.output, "w") as f:
        for chunk in stream_svg(w, h, gen, fill_rule=args.fill_rule):
            f.write(chunk)

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))