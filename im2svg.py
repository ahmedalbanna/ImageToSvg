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
from typing import List, Tuple, Optional

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

    P1 = coeff_x[0] * np.array([1.0, 0.0]) + coeff_x[1] * np.array([0.0, 0.0])
    P2 = coeff_y[0] * np.array([0.0, 0.0]) + coeff_y[1] * np.array([1.0, 0.0])
    # The above shortcut is incorrect; construct P1,P2 per axis properly
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


# --------------- Flat-color pipeline ---------------

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


def vectorize_flat(
    img_bgr: np.ndarray,
    k_colors: int = 8,
    min_area: int = 25,
    epsilon_ratio: float = 0.003,
    close_kernel: int = 3,
    fill_rule: str = "evenodd",
    bezier: bool = False,
    bezier_seglen: int = 16,
) -> List[Tuple[str, str]]:
    """Return list of (path_d, fill_hex) for flat-color vectorization.
    If --bezier is used, output paths are cubic Beziers instead of polylines.
    """
    """Return list of (path_d, fill_hex) for flat-color vectorization."""
    quant_bgr, _label_map = kmeans_quantize_bgr(img_bgr, k=k_colors)
    color_masks = build_color_masks(quant_bgr)

    # Sort by area descending to paint large regions first
    areas_masks = []
    for bgr, mask in color_masks:
        area = int(mask.sum() // 255)
        areas_masks.append((area, bgr, mask))
    areas_masks.sort(key=lambda x: x[0], reverse=True)

    paths = []
    kernel = np.ones((close_kernel, close_kernel), np.uint8) if close_kernel > 1 else None

    for area, bgr, mask in areas_masks:
        if area < min_area:
            continue
        mask2 = mask
        if kernel is not None:
            mask2 = cv2.morphologyEx(mask2, cv2.MORPH_CLOSE, kernel, iterations=1)
        contours, hierarchy = cv2.findContours(mask2, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if not contours or hierarchy is None:
            continue
        d_parts = []
        for cnt in contours:
            if cv2.contourArea(cnt) < min_area:
                continue
            approx = simplify_poly(cnt, epsilon_ratio)
            if len(approx) < 2:
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
            paths.append((" ".join(d_parts), bgr_to_hex(bgr)))
    return paths


# --------------- Line-art pipeline ---------------

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
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, float]]]:
    """Return (paths_fill, paths_stroke).
    paths_fill: list of (path_d, fill_hex)
    paths_stroke: list of (path_d, stroke_hex, stroke_width)
    """
    """Return list of (path_d, fill_hex, stroke_hex). By default emit filled shapes (stroke none)."""
    bin_img = threshold_line_art(img_bgr, adaptive=adaptive, thresh=thresh, invert=invert, blur=blur)

    # Clean noise and fill small gaps
    kernel = np.ones((close_kernel, close_kernel), np.uint8) if close_kernel > 1 else None
    if kernel is not None:
        bin_img = cv2.morphologyEx(bin_img, cv2.MORPH_CLOSE, kernel, iterations=1)

    contours, hierarchy = cv2.findContours(bin_img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    paths_fill: List[Tuple[str, str]] = []
    paths_stroke: List[Tuple[str, str, float]] = []
    if not contours:
        return paths_fill, paths_stroke

    for cnt in contours:
        if cv2.contourArea(cnt) < min_area:
            continue
        approx = simplify_poly(cnt, epsilon_ratio)
        if len(approx) < 2:
            continue
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
            paths_fill.append((d, "#000000"))
        # Optionally add stroke version
        if line_output in ("stroke", "both"):
            if _HAS_SKIMAGE and centerline:
                # Skeletonize and trace centerlines to polylines
                skel = skeletonize((bin_img > 0).astype(np.uint8)).astype(np.uint8) * 255
                # Find skeleton contours as polylines
                sk_contours, _ = cv2.findContours(skel, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
                dist = cv2.distanceTransform(bin_img, cv2.DIST_L2, 3)
                for sc in sk_contours:
                    if len(sc) < 8:
                        continue
                    sp = sc[:,0,:].astype(np.float32)
                    # Estimate width along skeleton polyline
                    xs = np.clip(sp[:,0].round().astype(int), 0, bin_img.shape[1]-1)
                    ys = np.clip(sp[:,1].round().astype(int), 0, bin_img.shape[0]-1)
                    widths = dist[ys, xs] * 2.0
                    width = float(np.median(widths)) if len(widths) else 1.0
                    width *= float(stroke_width_scale)
                    # Optional curve smoothing of centerline
                    if bezier:
                        if bezier_recursive:
                            beziers = recursive_fit_beziers(sp, max_err=bezier_maxerr, min_seg=max(6, int(bezier_seglen)))
                        else:
                            beziers = polyline_to_beziers(sp, seg_len=bezier_seglen)
                        sd = beziers_to_path_d(beziers, closed=False)
                    else:
                        sd = to_svg_path_d(sp, closed=False)
                    if sd:
                        paths_stroke.append((sd, stroke_color, max(0.5, width)))
            else:
                # Fallback: stroke the outer contour path with width estimation
                dist = cv2.distanceTransform(bin_img, cv2.DIST_L2, 3)
                mask = np.zeros_like(bin_img)
                cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)
                vals = dist[mask == 255]
                width = float(np.median(vals) * 2.0) if len(vals) else 1.0
                width *= float(stroke_width_scale)
                paths_stroke.append((d, stroke_color, max(0.5, width)))

    return paths_fill, paths_stroke


# --------------- Low-poly pipeline ---------------

def sample_points(img_bgr: np.ndarray, num_points: int = 1000, blur: int = 1) -> np.ndarray:
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
    # Rasterize triangle to a mask and average color inside
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillConvexPoly(mask, tri.astype(np.int32), 255)
    ys, xs = np.where(mask == 255)
    if len(xs) == 0:
        return "#000000"
    cols = img_bgr[ys, xs]
    bgr = cols.mean(axis=0).astype(np.uint8)
    b, g, r = int(bgr[0]), int(bgr[1]), int(bgr[2])
    return f"#{r:02x}{g:02x}{b:02x}"


def lowpoly(img_bgr: np.ndarray, num_points: int = 1000, blur: int = 1):
    pts = sample_points(img_bgr, num_points=num_points, blur=blur)
    h, w = img_bgr.shape[:2]
    polygons = []  # List[(points, fill_hex)]

    if _HAS_SCIPY:
        tri = Delaunay(pts)
        for simplex in tri.simplices:
            p = pts[simplex]
            fill = triangle_mean_color(img_bgr, p)
            polygons.append(([(float(p[0,0]), float(p[0,1])), (float(p[1,0]), float(p[1,1])), (float(p[2,0]), float(p[2,1]))], fill))
    else:
        subdiv = cv2.Subdiv2D((0, 0, w, h))
        for (x, y) in pts:
            try:
                subdiv.insert((float(x), float(y)))
            except Exception:
                pass
        triangleList = subdiv.getTriangleList()
        for t in triangleList:
            x1, y1, x2, y2, x3, y3 = t
            if x1 < 0 or x1 >= w or x2 < 0 or x2 >= w or x3 < 0 or x3 >= w or y1 < 0 or y1 >= h or y2 < 0 or y2 >= h or y3 < 0 or y3 >= h:
                continue
            p = np.array([[x1, y1], [x2, y2], [x3, y3]], dtype=np.float32)
            fill = triangle_mean_color(img_bgr, p)
            polygons.append(([(float(x1), float(y1)), (float(x2), float(y2)), (float(x3), float(y3))], fill))

    return polygons

# --------------- SVG writer ---------------

def write_svg(
    output_path: str,
    width: int,
    height: int,
    paths_fill: List[Tuple[str, str]],
    paths_stroke: List[Tuple[str, str, float]] = None,
    fill_rule: str = "evenodd",
    polygons: Optional[List[Tuple[List[Tuple[float, float]], str]]] = None,
):
    dwg = svgwrite.Drawing(output_path, size=(width, height), viewBox=f"0 0 {width} {height}")
    dwg.attribs["shape-rendering"] = "geometricPrecision"

    # Filled paths
    for d, fill_hex in paths_fill:
        if not d:
            continue
        p = dwg.path(d=d, fill=fill_hex, stroke="none", fill_rule=fill_rule)
        dwg.add(p)

    # Stroked paths (optional)
    if paths_stroke:
        for d, stroke_hex, stroke_width in paths_stroke:
            p = dwg.path(d=d, fill="none", stroke=stroke_hex, stroke_width=stroke_width,
                         stroke_linejoin="round", stroke_linecap="round")
            dwg.add(p)

    # Polygon layer (e.g., low-poly)
    if polygons:
        for pts, fill_hex in polygons:
            dwg.add(dwg.polygon(points=pts, fill=fill_hex, stroke="none"))

    dwg.save()


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
    p.add_argument("--quality", choices=["low","medium","high"], help="Quality preset that sets smoothing and detail parameters (overrides related flags)")

    # Flat mode
    p.add_argument("--colors", type=int, default=8, help="Number of colors for quantization (flat mode)")
    p.add_argument("--min-area", type=int, default=20, help="Minimum contour area to keep (px^2)")
    p.add_argument("--epsilon", type=float, default=0.003, help="RDP simplification ratio relative to perimeter")
    p.add_argument("--close-kernel", type=int, default=3, help="Morphological closing kernel size (0/1 to disable)")
    p.add_argument("--fill-rule", choices=["nonzero", "evenodd"], default="evenodd", help="Fill rule for complex paths")

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

    if args.mode == "flat":
        paths_fill = vectorize_flat(
            img_bgr,
            k_colors=max(2, int(args.colors)),
            min_area=max(1, int(args.min_area)),
            epsilon_ratio=max(1e-5, float(args.epsilon)),
            close_kernel=max(0, int(args.close_kernel)),
            fill_rule=args.fill_rule,
            bezier=bool(args.bezier),
            bezier_seglen=max(4, int(args.bezier_seglen)),
        )
        write_svg(args.output, w, h, paths_fill=paths_fill, paths_stroke=None, fill_rule=args.fill_rule)
    elif args.mode == "line":  # line
        paths_fill, paths_stroke = vectorize_line(
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
        )
        write_svg(args.output, w, h, paths_fill=paths_fill, paths_stroke=paths_stroke, fill_rule=args.fill_rule)
    else:  # lowpoly
        polygons = lowpoly(img_bgr, num_points=int(args.points), blur=int(args.tri_blur))
        write_svg(args.output, w, h, paths_fill=[], polygons=polygons, fill_rule=args.fill_rule)

    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
