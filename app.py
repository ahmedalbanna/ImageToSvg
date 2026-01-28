import uuid
from typing import Optional, Dict
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import numpy as np
import cv2

from im2svg import (
    vectorize_flat,
    vectorize_line,
    lowpoly,
    stream_svg,
    preprocess_image,
    apply_artistic_filter,
    optimize_svg_output,
)

app = FastAPI(title="im2svg API", version="1.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Simple in-memory cache for demo purposes
# In production, use a proper backend (Redis/Disk) and TTL
IMAGE_CACHE: Dict[str, np.ndarray] = {}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI page."""
    return templates.TemplateResponse("index.html", {"request": request})


def _imdecode(file_bytes: bytes):
    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """Cache the uploaded file and return an ID."""
    data = await file.read()
    img = _imdecode(data)
    if img is None:
        return Response("Invalid image", status_code=400)
    
    fid = str(uuid.uuid4())
    IMAGE_CACHE[fid] = img
    return {"id": fid, "width": img.shape[1], "height": img.shape[0]}


@app.post("/api/convert")
async def api_convert(
    # Preprocessing parameters
    preprocess: Optional[str] = Form(None),
    contrast: Optional[str] = Form(None),
    denoise: Optional[str] = Form(None),
    sharpen: Optional[str] = Form(None),
    auto_crop: Optional[str] = Form(None),
    max_size: Optional[int] = Form(0),
    # Artistic filter parameters
    artistic_filter: Optional[str] = Form(None),
    filter_intensity: Optional[float] = Form(0.5),
    # SVG optimization parameters
    optimize_svg: Optional[str] = Form(None),
    svg_precision: Optional[int] = Form(2),
    minify_svg: Optional[str] = Form(None),
    # Advanced algorithm parameters
    color_method: Optional[str] = Form("kmeans"),
    detect_gradients: Optional[str] = Form(None),
    detect_patterns: Optional[str] = Form(None),
    pattern_type: Optional[str] = Form("auto"),
    adaptive_sampling: Optional[str] = Form(None),
    edge_weight: Optional[float] = Form(0.7),
    variable_width: Optional[str] = Form(None),
    preserve_hierarchy: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    file_id: Optional[str] = Form(None),
    mode: str = Form("flat"),
    quality: Optional[str] = Form(None),
    # flat
    colors: int = Form(8),
    min_area: int = Form(20),
    epsilon: float = Form(0.003),
    close_kernel: int = Form(3),
    fill_rule: str = Form("evenodd"),
    smoothness: int = Form(0),
    # line
    adaptive: str = Form("false"),
    thresh: int = Form(-1),
    invert: str = Form("true"),
    blur: int = Form(0),
    line_output: str = Form("fill"),
    stroke_color: str = Form("#000000"),
    stroke_width_scale: float = Form(1.0),
    centerline: str = Form("true"),
    centerline_prune: int = Form(8),
    centerline_rdp: float = Form(0.0),
    # bezier
    bezier: str = Form("false"),
    bezier_seglen: int = Form(16),
    bezier_recursive: str = Form("false"),
    bezier_maxerr: float = Form(2.0),
    # lowpoly
    points: int = Form(1000),
    tri_blur: int = Form(1),
):
    # Resolve input image
    img = None
    if file_id and file_id in IMAGE_CACHE:
        img = IMAGE_CACHE[file_id]
    elif file is not None:
        data = await file.read()
        if len(data) > 0:
            img = _imdecode(data)
    
    if img is None:
        return Response("Missing image or invalid file_id", status_code=400)
    
    # Apply artistic filter first if requested
    if artistic_filter and artistic_filter != "none":
        try:
            intensity = float(filter_intensity) if filter_intensity else 0.5
            intensity = max(0.0, min(1.0, intensity))  # Clamp to 0-1
            img = apply_artistic_filter(img, artistic_filter, intensity)
        except Exception as e:
            print(f"Warning: Artistic filter failed: {e}")
            # Continue with original image
    
    # Apply preprocessing if requested
    if preprocess and preprocess == "true":
        try:
            # Safe conversion of max_size parameter
            max_size_val = 0
            if max_size is not None:
                try:
                    max_size_val = int(max_size)
                except (ValueError, TypeError):
                    max_size_val = 0
            
            img = preprocess_image(
                img,
                contrast=(contrast == "true"),
                contrast_method="clahe",
                denoise=(denoise == "true"),
                denoise_strength=10,
                sharpen=(sharpen == "true"),
                sharpen_strength=1.0,
                auto_crop_enabled=(auto_crop == "true"),
                max_size=max_size_val
            )
        except Exception as e:
            # If preprocessing fails, log and continue with original image
            print(f"Warning: Preprocessing failed: {e}")
            # Continue with original img
    
    h, w = img.shape[:2]

    # Select generator
    if mode == "flat":
        gen = vectorize_flat(
            img,
            k_colors=max(2, int(colors)),
            min_area=max(1, int(min_area)),
            epsilon_ratio=max(1e-5, float(epsilon)),
            close_kernel=max(0, int(close_kernel)),
            fill_rule=fill_rule,
            bezier=(bezier == "true"),
            bezier_seglen=max(4, int(bezier_seglen)),
            bezier_recursive=(bezier_recursive == "true"),
            bezier_maxerr=float(bezier_maxerr),
            smoothness=max(0, int(smoothness)),
            color_method=str(color_method) if color_method else "kmeans",
            detect_gradients=(detect_gradients == "true"),
            gradient_threshold=25.0,
            detect_patterns=(detect_patterns == "true"),
            pattern_type=str(pattern_type) if pattern_type else "auto",
        )
    elif mode == "line":
        gen = vectorize_line(
            img,
            adaptive=(adaptive == "true"),
            thresh=int(thresh),
            invert=(invert == "true"),
            blur=int(blur),
            min_area=max(1, int(min_area)),
            epsilon_ratio=max(1e-5, float(epsilon)),
            close_kernel=max(0, int(close_kernel)),
            bezier=(bezier == "true"),
            bezier_seglen=max(4, int(bezier_seglen)),
            bezier_recursive=(bezier_recursive == "true"),
            bezier_maxerr=float(bezier_maxerr),
            line_output=line_output,
            stroke_color=stroke_color,
            stroke_width_scale=float(stroke_width_scale),
            centerline=(centerline == "true"),
            centerline_prune=int(centerline_prune),
            centerline_rdp=float(centerline_rdp),
            variable_width=(variable_width == "true"),
            preserve_hierarchy=(preserve_hierarchy == "true"),
        )
    elif mode == "lowpoly":
        gen = lowpoly(
            img,
            num_points=int(points),
            blur=int(tri_blur),
            adaptive_sampling=(adaptive_sampling == "true"),
            edge_weight=float(edge_weight) if edge_weight else 0.7,
        )
    else:
        return Response("Invalid mode", status_code=400)

    # Use streaming response
    return StreamingResponse(
        stream_svg(w, h, gen, fill_rule),
        media_type="image/svg+xml; charset=utf-8"
    )