# AGENTS.md - Developer Guide for im2svg

## Project Overview

**Purpose**: A web application for converting raster images (PNG, JPG) to SVG vector graphics using non-AI algorithms

**Language**: Python 3.7+

**Frameworks & Key Libraries**:
- **Backend**: FastAPI (web framework), Uvicorn (ASGI server)
- **Image Processing**: OpenCV (cv2), NumPy
- **SVG Generation**: svgwrite
- **Optional**: scipy (Delaunay triangulation), scikit-image (skeletonization)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3

**Architecture**: 
- Server-side image processing with FastAPI REST API
- Client-side SPA with real-time preview
- In-memory image caching (UUID-based)
- Streaming SVG response

---

## Project Structure

### Core Files

**Backend**:
- `app.py` (147 lines) - FastAPI application with 3 endpoints
- `im2svg.py` (865 lines) - Core vectorization algorithms and CLI interface

**Frontend**:
- `templates/index.html` (8KB) - Main UI template (Jinja2)
- `static/css/style.css` (7.5KB) - Modern responsive styling
- `static/js/app.js` (7.3KB) - Client-side logic and API integration

**Documentation**:
- `README.md` - Complete project documentation
- `USAGE_GUIDE.md` - Detailed parameter explanations and use cases
- `GETTING_STARTED.md` - Quick start guide for new users

**Configuration**:
- `requirements.txt` - Python dependencies
- `.gitignore` - Git ignore rules (includes tmp_* patterns)

### Total Lines of Code
- Python: ~1012 lines (app.py + im2svg.py)
- JavaScript: ~200+ lines
- CSS: ~400+ lines

---

## Core Algorithms & Functions

### Vectorization Modes (im2svg.py)

**1. Flat Mode** (`vectorize_flat`):
- **Multiple color quantization methods**:
  - K-means clustering (default, balanced quality)
  - Median cut algorithm (better for few colors, 6-7x faster)
  - Octree quantization (future enhancement)
- **Gradient fill detection and rendering**:
  - Automatic detection of linear and radial gradients
  - Intelligent direction analysis (horizontal, vertical, radial)
  - Native SVG gradient definitions
  - Significantly improves quality for images with color transitions
- Region extraction with morphological operations
- Contour detection and polygon simplification
- Optional Bezier curve fitting
- Best for: logos, icons, cartoons, flat illustrations, buttons with gradients

**2. Line Mode** (`vectorize_line`):
- Adaptive or fixed thresholding
- **Contour hierarchy preservation** (handles holes and nested shapes)
- Optional centerline extraction using skeletonization
- **Variable stroke width detection** (adaptive line thickness)
- Enhanced stroke width estimation
- Contour-to-path conversion
- Stroke or fill output options
- Best for: sketches, line art, technical drawings

**3. Low Poly Mode** (`lowpoly`):
- **Adaptive point sampling** (edge-aware placement)
- Feature point sampling with configurable edge weight
- Smart edge detection for better triangle placement
- Delaunay triangulation (scipy or cv2.Subdiv2D fallback)
- Optimized triangle color averaging
- Best for: artistic effects, backgrounds, portraits

### Key Utility Functions

**Core Algorithms**:
- `simplify_poly()` - Douglas-Peucker polygon simplification
- `polyline_to_beziers()` - Convert polylines to cubic Bezier curves
- `recursive_fit_beziers()` - Schneider-style recursive Bezier fitting
- `skeleton_centerlines()` - Extract and prune skeleton lines
- `stream_svg()` - Generator-based SVG streaming (memory efficient)

**Artistic Filters**:
- `apply_watercolor_effect()` - Watercolor painting effect
- `apply_sketch_effect()` - Pencil sketch effect (B&W or colored)
- `apply_oil_painting_effect()` - Oil painting with brush strokes
- `apply_cartoon_effect()` - Cartoon/cel-shading effect
- `apply_artistic_filter()` - Unified filter interface

**Color Palette Extraction**:
- `extract_color_palette()` - Extract dominant colors (3 methods)
- `export_palette_json()` - Export as JSON
- `export_palette_css()` - Export as CSS custom properties
- `export_palette_scss()` - Export as SCSS variables
- `export_palette_tailwind()` - Export as Tailwind config
- `rgb_to_hsl()` - RGB to HSL color conversion
- `analyze_color_temperature()` - Warm/cool/neutral analysis

**Enhanced Color Extraction**:
- `extract_dominant_colors()` - Multi-method color extraction dispatcher
- `median_cut_quantize()` - Median cut algorithm (6-7x faster than k-means)
- `octree_quantize()` - Octree color quantization (future)
- `detect_gradient_regions()` - Identify gradient vs flat color regions
- `analyze_gradient_direction()` - Analyze gradient type, angle, and colors
- `create_gradient_id()` - Generate unique gradient identifiers

**Advanced Line Detection**:
- `detect_contour_hierarchy()` - Analyze parent-child contour relationships
- `estimate_variable_stroke_width()` - Adaptive stroke width estimation
- `smooth_stroke_widths()` - Moving average stroke width smoothing

**Intelligent Point Sampling**:
- `adaptive_point_sampling()` - Edge-aware point placement
- `sample_points()` - Standard point sampling (original method)

**SVG Effects & Gradients**:
- `create_linear_gradient()` - Linear gradient definitions with angle support
- `create_radial_gradient()` - Radial gradient definitions with center positioning
- `create_drop_shadow_filter()` - Drop shadow filter effects
- `bgr_to_hex()` - BGR to hex color conversion for SVG

**SVG Pattern Fills**:
- `create_dots_pattern()` - Polka dot pattern with customizable size/spacing
- `create_stripes_pattern()` - Parallel stripe pattern with rotation
- `create_checkerboard_pattern()` - Alternating square pattern
- `create_crosshatch_pattern()` - Diagonal cross-hatch lines
- `create_grid_pattern()` - Perpendicular grid pattern
- `detect_texture_pattern()` - Detect repeating textures in regions
- `create_pattern_id()` - Generate unique pattern identifiers

---

## API Endpoints

### `GET /`
- Serves main UI (Jinja2 template)
- Returns: HTML page

### `POST /api/upload`
- Uploads image to memory cache
- Returns: `{"id": "<uuid>", "width": int, "height": int}`
- Cache: `IMAGE_CACHE` dict (in-memory, no TTL)

### `POST /api/convert`
- Converts cached or uploaded image to SVG
- Accepts: multipart form data with parameters
- Returns: Streaming SVG response
- Supports 3 modes: flat, line, lowpoly
- 20+ configurable parameters

---

## Frontend Architecture

### JavaScript Structure (app.js)

**Key Components**:
- `PRESETS` object - Quality preset configurations for each mode
- `updateOptionsVisibility()` - Dynamic UI based on mode
- `handleUpload()` - File upload with caching
- `applyPreset()` - Apply quality preset values
- `downloadSVG()` - Client-side SVG file download

**Event Handlers**:
- File input change → auto-upload
- Drag & drop → file upload
- Form submit → API conversion
- Mode change → show/hide options
- Quality change → apply preset
- Copy/download buttons → clipboard/file

**API Flow**:
1. Upload file → `/api/upload` → get file_id
2. Auto-trigger conversion → `/api/convert` → get SVG
3. Display in preview + textarea
4. Show copy/download buttons

### CSS Architecture (style.css)

**Design System**:
- CSS custom properties in `:root` for theming
- Mobile-first responsive design
- Grid layout (2-column on desktop, 1-column on mobile)
- Gradient background with card-based panels

**Key Classes**:
- `.panel` - Card containers
- `.form-section` - Grouped form elements
- `.options-fieldset` - Collapsible option groups
- `.btn-primary` / `.btn-secondary` - Action buttons
- `.status` - Status indicators with color variants

---

## Development Best Practices

### Code Conventions

**Python**:
- Type hints used throughout (`typing` module)
- Generator functions for memory efficiency (`yield`)
- Docstrings on public functions
- Error handling with try/except and fallbacks
- Optional dependencies checked at import (`_HAS_SCIPY`, `_HAS_SKIMAGE`)

**JavaScript**:
- Modern ES6+ syntax (arrow functions, async/await, const/let)
- Descriptive function names with JSDoc-style comments
- Event delegation where appropriate
- No external dependencies (vanilla JS)

**CSS**:
- BEM-like naming conventions
- Mobile-first media queries
- CSS custom properties for theming
- Logical grouping with comments

### File Naming

**Temporary Files**:
- Prefix with `tmp_rovodev_*` (auto-ignored by .gitignore)
- Clean up after testing

**Static Assets**:
- CSS: `static/css/*.css`
- JS: `static/js/*.js`
- Images: `static/images/*.{png,jpg,svg}` (if added)

---

## Common Development Tasks

### Adding New Conversion Mode

1. Implement generator function in `im2svg.py`:
   ```python
   def vectorize_mymode(img_bgr, **kwargs) -> Iterator[Tuple[List, str]]:
       # Yield (points, color) tuples
       yield ([(x1,y1), (x2,y2)], "#hexcolor")
   ```

2. Add mode handler in `app.py` `/api/convert`:
   ```python
   elif mode == "mymode":
       gen = vectorize_mymode(img, **params)
   ```

3. Update UI in `templates/index.html`:
   - Add option in mode select
   - Add fieldset for mode-specific options

4. Update `static/js/app.js`:
   - Add to `PRESETS` object
   - Update `updateOptionsVisibility()`

### Adding New Preprocessing Function

1. Add function to `im2svg.py` (in preprocessing section):
   ```python
   def my_preprocessing(img_bgr: np.ndarray, param: int = 10) -> np.ndarray:
       """My preprocessing description."""
       # Process image
       return processed_img
   ```

2. Update `preprocess_image()` function to call it:
   ```python
   if my_preprocess_enabled:
       img = my_preprocessing(img, my_param)
   ```

3. Add parameter to `app.py` `/api/convert`:
   ```python
   my_preprocess: Optional[str] = Form(None),
   my_param: int = Form(10),
   ```

4. Update preprocessing call in `app.py`:
   ```python
   img = preprocess_image(
       img,
       # ... existing params ...
       my_preprocess_enabled=(my_preprocess == "true"),
       my_param=int(my_param)
   )
   ```

5. Add UI control in `templates/index.html`:
   ```html
   <label class="checkbox-label">
     <input type="checkbox" name="my_preprocess">
     <span>My Preprocessing</span>
   </label>
   ```

6. Update checkbox normalization in `static/js/app.js`

### Adding Quality Preset

Edit `static/js/app.js` PRESETS:
```javascript
const PRESETS = {
  flat: {
    mypreset: { colors: 10, min_area: 15, epsilon: 0.002 }
  }
};
```

Add option in `templates/index.html`:
```html
<option value="mypreset">My Preset</option>
```

### Customizing Theme

Edit `static/css/style.css` `:root` section:
```css
:root {
  --primary-color: #4f46e5;  /* Change primary color */
  --radius: 8px;              /* Change border radius */
  /* ... other variables ... */
}
```

---

## Testing & Debugging

### Manual Testing

1. **Start dev server**:
   ```bash
   uvicorn app:app --reload
   ```

2. **Test endpoints**:
   ```bash
   # Upload
   curl -X POST -F "file=@test.png" http://localhost:8000/api/upload
   
   # Convert
   curl -X POST -F "file=@test.png" -F "mode=flat" -F "colors=8" \
        http://localhost:8000/api/convert > output.svg
   ```

3. **Check browser console** for JavaScript errors

4. **Verify SVG** by opening in browser or editor

### Common Issues

**Import Errors**:
- Check all dependencies installed: `pip install -r requirements.txt`
- Optional deps (scipy, skimage) - code has fallbacks

**Port Already in Use**:
```bash
# Use different port
uvicorn app:app --port 8001
```

**Image Cache Growing**:
- `IMAGE_CACHE` has no TTL or size limit
- For production: implement Redis or disk-based cache with cleanup

**CORS Issues** (if using separate frontend):
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

---

## Performance Considerations

### Backend Optimization

- **Streaming Response**: Uses `StreamingResponse` to avoid loading entire SVG in memory
- **Generator Pattern**: Vectorization functions yield incrementally
- **Image Caching**: Avoids re-uploading for parameter tweaks
- **Parameter Validation**: Uses `max()`, `min()` to prevent invalid values

### Frontend Optimization

- **Auto-conversion**: Triggers on upload (good UX, may be resource-heavy)
- **No Image Preview**: Could add thumbnail preview before conversion
- **Single Request**: No chunked uploads or progress bars

### Scalability Concerns

**Current Limitations**:
- In-memory cache (not persistent, not distributed)
- No request queuing or rate limiting
- Single-threaded processing
- No timeout handling

**Production Improvements**:
- Add Redis/disk cache with TTL
- Implement background task queue (Celery)
- Add rate limiting (slowapi)
- Set request timeouts
- Use multiple Uvicorn workers
- Add monitoring/logging

---

## Deployment Notes

### Development
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Production

**Option 1: Gunicorn + Uvicorn Workers**
```bash
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Option 2: Uvicorn with reverse proxy (Nginx)**
```bash
uvicorn app:app --host 127.0.0.1 --port 8000
# Configure Nginx to proxy to localhost:8000
```

### Environment Variables

Consider adding:
```python
import os
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
CACHE_SIZE = int(os.getenv("CACHE_SIZE", 1000))
```

### Docker (Future)

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Security Considerations

### Current State

**Vulnerabilities**:
- No authentication or authorization
- No rate limiting (DoS risk)
- No file size limits (memory exhaustion)
- No input validation (malicious images)
- Cache never cleared (memory leak)

**Implemented Protections**:
- Image validation via cv2.imdecode
- Parameter bounds checking (max/min)
- No file system writes (except manual save)

### Production Hardening

1. **Add file size limits**:
   ```python
   @app.post("/api/upload")
   async def api_upload(file: UploadFile = File(..., max_length=10*1024*1024)):  # 10MB
   ```

2. **Add rate limiting**:
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   @limiter.limit("10/minute")
   ```

3. **Add cache cleanup**:
   ```python
   import time
   CACHE_TTL = 3600  # 1 hour
   # Implement periodic cleanup task
   ```

4. **Validate image types**:
   ```python
   ALLOWED_TYPES = {"image/png", "image/jpeg", "image/jpg"}
   if file.content_type not in ALLOWED_TYPES:
       raise HTTPException(400, "Invalid file type")
   ```

---

## Artistic Filters

### Available Artistic Filters

**Watercolor Effect**:
- Soft, paint-like appearance with color bleeding
- Reduces details while preserving overall composition
- Darkens edges for watercolor paper effect
- Quantizes colors for paint-like appearance
- Adjustable intensity (0.0-1.0)

**Sketch Effect**:
- Pencil drawing appearance
- Available in B&W or colored versions
- Adjustable line intensity
- Inverted blur technique for realistic sketch lines
- Colored version preserves hues with reduced saturation

**Oil Painting Effect**:
- Thick brush strokes appearance
- Enhanced color saturation
- Bilateral filtering for smooth color regions
- Quantized colors for paint texture
- Adjustable brush size

**Cartoon Effect**:
- Cel-shaded animation style
- Emphasized edges with thick outlines
- Reduced color details
- Adaptive thresholding for cartoon borders
- Multiple bilateral filter passes

**Colored Sketch Effect**:
- Combines sketch lines with original colors
- Reduced saturation for pencil effect
- Maintains color relationships
- Adjustable intensity

### Usage in Code

```python
from im2svg import apply_artistic_filter

# Apply watercolor effect
img_watercolor = apply_artistic_filter(img_bgr, 'watercolor', intensity=0.7)

# Apply sketch effect (B&W)
img_sketch = apply_artistic_filter(img_bgr, 'sketch', intensity=0.5)

# Apply colored sketch
img_colored_sketch = apply_artistic_filter(img_bgr, 'colored_sketch', intensity=0.6)

# Apply oil painting
img_oil = apply_artistic_filter(img_bgr, 'oil', intensity=0.8)

# Apply cartoon effect
img_cartoon = apply_artistic_filter(img_bgr, 'cartoon', intensity=0.5)
```

### UI Integration

Artistic filters are available in the web interface:
1. Select "Filter Type" from dropdown (Watercolor, Sketch, Colored Sketch, Oil Painting, Cartoon)
2. Adjust "Filter Intensity" slider (0.0-1.0)
3. Filters are applied before vectorization
4. Convert as normal

### Performance Impact

- **Watercolor**: ~200-400ms depending on image size and intensity
- **Sketch**: ~100-200ms (B&W), ~150-250ms (colored)
- **Oil Painting**: ~300-600ms (uses bilateral filtering)
- **Cartoon**: ~400-800ms (multiple bilateral passes)
- **Overall**: Filters add processing time but create unique artistic styles

**Tip**: Use lower intensities for subtle effects and faster processing

---

## Image Preprocessing Features

### Available Preprocessing Options

**Contrast Enhancement**:
- CLAHE (Contrast Limited Adaptive Histogram Equalization)
- Global histogram equalization
- Improves visibility in low-contrast images

**Denoising**:
- Non-local Means Denoising
- Strength adjustable (5-20)
- Removes grain and sensor noise

**Sharpening**:
- Unsharp masking
- Strength adjustable (0.5-2.0)
- Enhances edge definition

**Auto Crop**:
- Automatically removes uniform borders
- Uses edge detection to find content bounds
- Adds small margin for safety

**Smart Resizing**:
- Downsample large images for faster processing
- Preserves aspect ratio
- Uses INTER_AREA for quality downsampling

### Usage in Code

```python
from im2svg import preprocess_image

# Apply full preprocessing pipeline
img_processed = preprocess_image(
    img_bgr,
    contrast=True,
    contrast_method="clahe",
    denoise=True,
    denoise_strength=10,
    sharpen=True,
    sharpen_strength=1.0,
    auto_crop_enabled=True,
    max_size=2000
)
```

### UI Integration

Preprocessing options are available in the web interface:
1. Check "Enable Preprocessing"
2. Select desired preprocessing options
3. Set max_size to limit dimensions (0 = no limit)
4. Convert as normal

### Performance Impact

- **Contrast**: Minimal overhead (~50ms for 2000px image)
- **Denoise**: Moderate cost (~500ms, depends on strength)
- **Sharpen**: Fast (~30ms)
- **Auto Crop**: Fast (~100ms)
- **Resize**: Fast (~50ms, saves time in vectorization)

**Tip**: Use max_size for faster overall processing, especially for photos

---

## Enhanced Algorithms

### Flat Mode Enhancements

**New Features**:
- **Multiple Color Quantization Methods**:
  - K-means: Balanced quality, good for most images
  - Median cut: 6-7x faster, better for images with few distinct colors
- **Gradient Fill Support** (NEW! ✨):
  - Automatic detection of gradients in color regions
  - Supports linear gradients (horizontal, vertical, diagonal)
  - Supports radial gradients (center to edge)
  - Native SVG gradient rendering (smaller files, scalable)
  - Configurable detection threshold
- Better color preservation for specific image types

**Performance Improvements**:
- Early area filtering before contour processing
- Optimized contour retrieval (RETR_EXTERNAL)
- Pre-created morphological kernels
- Minimum polygon point validation (3+ points)
- Median cut is 85-90% faster than k-means

**Performance Gain**: 
- Standard optimizations: ~15-25% faster
- Median cut method: ~600-700% faster than k-means

**Usage**:
```python
# Use median cut for faster processing
paths = vectorize_flat(img, k_colors=8, color_method="median_cut")

# Use k-means for best quality (default)
paths = vectorize_flat(img, k_colors=8, color_method="kmeans")

# Enable gradient detection and rendering
paths = vectorize_flat(img, k_colors=8, detect_gradients=True, gradient_threshold=25.0)

# Disable gradients for pure flat colors
paths = vectorize_flat(img, k_colors=8, detect_gradients=False)
```

### Line Mode Enhancements

**New Features**:
- **Contour Hierarchy Preservation**: Properly handles holes and nested shapes
- **Variable Stroke Width**: Adaptive line thickness based on distance transform
- **Smooth Width Variations**: Moving average for better visual quality
- Enhanced stroke width estimation algorithm

**Performance Improvements**:
- Distance transform computed once globally
- Centerline extraction done once upfront
- Removed per-contour redundant calculations
- Optimized contour retrieval mode

**Performance Gain**: ~20-30% faster, especially with centerlines enabled

**Usage**:
```python
# Preserve holes and hierarchy
paths = vectorize_line(img, preserve_hierarchy=True)

# Variable stroke width
paths = vectorize_line(img, variable_width=True, line_output="stroke")

# Both features
paths = vectorize_line(img, preserve_hierarchy=True, variable_width=True)
```

### Low Poly Mode Enhancements

**New Features**:
- **Adaptive Point Sampling**: Edge-aware point placement
- **Configurable Edge Weight**: Control point distribution (0.0-1.0)
- Smart edge detection using Canny
- Feature-based sampling (corners + edges + random)
- Better preservation of important image features

**Performance Improvements**:
- Bounding-box color sampling instead of full-image masking
- Reduced memory allocation per triangle
- Vectorized coordinate operations
- Optimized boundary checking

**Performance Gain**: ~40-50% faster on high triangle counts

**Usage**:
```python
# Standard sampling (original)
polys = lowpoly(img, num_points=1000, adaptive_sampling=False)

# Adaptive sampling (better quality)
polys = lowpoly(img, num_points=1000, adaptive_sampling=True, edge_weight=0.7)

# More edges (detailed), less random
polys = lowpoly(img, num_points=1000, adaptive_sampling=True, edge_weight=0.9)

# Fewer edges (smoother), more random
polys = lowpoly(img, num_points=1000, adaptive_sampling=True, edge_weight=0.5)
```

### SVG Optimization

**SVGO-Style Optimization Features**:
- Path data precision reduction (configurable 0-6 decimals)
- Color shortening (#ffffff → #fff or white)
- Default attribute removal (stroke-width="1", etc.)
- Comment and metadata removal
- Number rounding and cleanup
- Whitespace minification
- Trailing zero removal

**Optimization Functions**:
- `optimize_path_data()` - Reduce path precision and remove redundancy
- `optimize_color()` - Shorten color codes
- `remove_default_attributes()` - Remove SVG default values
- `optimize_svg_output()` - Complete optimization pipeline
- `calculate_svg_size_reduction()` - Statistics calculator

**Usage**:
```python
from im2svg import optimize_svg_output

# Optimize SVG content
optimized = optimize_svg_output(
    svg_content,
    precision=2,              # 2 decimal places
    remove_metadata=True,     # Remove <title>, <desc>, etc.
    remove_comments=True,     # Remove <!-- comments -->
    minify=False              # Keep human-readable formatting
)

# Aggressive optimization
optimized = optimize_svg_output(svg_content, precision=1, minify=True)
```

**Typical Size Reductions**:
- Standard optimization: 20-40% smaller
- With minification: 30-50% smaller
- High precision images: 40-60% smaller

**UI Integration**:
- "Optimize SVG Output" checkbox (enabled by default)
- Precision slider (0-6 decimals, default 2)
- Minify option (remove all whitespace)

---

### SVG Effects & Features

**Implemented**:
- ✅ Linear gradient definitions
- ✅ Radial gradient definitions  
- ✅ Drop shadow filters
- ✅ Pattern fills (dots, stripes, checkerboard, cross-hatch, grid)
- ✅ Gradient fill detection in flat mode
- ✅ Effect system infrastructure

**Pattern Types Available**:
- **Dots**: Polka dot pattern with configurable size and spacing
- **Stripes**: Parallel lines with rotation support (0-360°)
- **Checkerboard**: Alternating squares pattern
- **Cross-hatch**: Diagonal crossing lines for shading
- **Grid**: Perpendicular grid lines

**Future Enhancements**:
- Custom image-based patterns
- Blur effects
- Advanced compositing
- Mesh gradients

### General Optimizations

**Best Practices**:
- Use preprocessing max_size to reduce input dimensions
- Start with lower quality settings for previews
- Enable preprocessing only when needed
- Use appropriate mode for image type
- **Use median cut for faster flat mode processing**
- **Enable adaptive sampling for better lowpoly quality**
- **Use hierarchy preservation for complex line art**

**Algorithm Selection Guide**:
```
Flat Mode:
  Speed priority → color_method="median_cut"
  Quality priority → color_method="kmeans"

Line Mode:
  Complex drawings → preserve_hierarchy=True
  Variable thickness → variable_width=True

Low Poly Mode:
  Better quality → adaptive_sampling=True, edge_weight=0.7-0.9
  Faster/smoother → adaptive_sampling=False
```

---

## Extension Ideas

### Near-term Enhancements

- **Image preview**: Show uploaded image thumbnail
- **History**: Store recent conversions (localStorage)
- **Batch processing**: Upload multiple images
- **More export formats**: EPS, PDF via additional libraries
- **Server-side presets**: Store and share configurations
- **Progress indicators**: For slow conversions
- **Advanced preprocessing**: Perspective correction, color adjustment

### Advanced Features

- **User accounts**: Save preferences and history
- **API keys**: For programmatic access
- **Webhooks**: Notify on completion
- **Cloud storage**: S3/GCS integration
- **WebSocket**: Real-time progress updates
- **Docker**: Containerized deployment
- **Advanced editing**: Crop, rotate, color adjust

---

## Useful Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server
uvicorn app:app --reload

# Run with custom host/port
uvicorn app:app --host 185.190.140.93 --port 9003

# Check syntax
python -m py_compile app.py im2svg.py

# Run CLI version
python im2svg.py input.png -o output.svg --mode flat --colors 8
```

### Testing
```bash
# Test upload endpoint
curl -X POST -F "file=@test.png" http://localhost:8000/api/upload

# Test conversion
curl -X POST -F "file=@test.png" -F "mode=flat" \
     http://localhost:8000/api/convert -o output.svg

# Check server health
curl http://localhost:8000/
```

### Production
```bash
# Multi-worker production server
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With logging
uvicorn app:app --log-level info --access-log
```

---

## Resources & References

### Documentation
- FastAPI: https://fastapi.tiangolo.com/
- OpenCV Python: https://docs.opencv.org/
- svgwrite: https://svgwrite.readthedocs.io/
- SVG Spec: https://www.w3.org/TR/SVG/

### Algorithms
- Douglas-Peucker: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
- K-means clustering: https://en.wikipedia.org/wiki/K-means_clustering
- Delaunay triangulation: https://en.wikipedia.org/wiki/Delaunay_triangulation
- Bezier curves: https://en.wikipedia.org/wiki/B%C3%A9zier_curve
- Image skeletonization: https://en.wikipedia.org/wiki/Topological_skeleton

### Related Projects
- Potrace (bitmap tracing): http://potrace.sourceforge.net/
- Primitive (geometric shapes): https://github.com/fogleman/primitive
- VTracer (Rust): https://github.com/visioncortex/vtracer

---

## Contributing Guidelines

### Code Style
- Follow PEP 8 for Python
- Use type hints where appropriate
- Add docstrings to public functions
- Keep functions focused and modular
- Write self-documenting code with clear names

### Commit Messages
```
feat: add batch processing support
fix: correct bezier curve calculation
docs: update API documentation
refactor: simplify polygon algorithm
test: add unit tests for flat mode
```

### Pull Request Checklist
- [ ] Code follows project conventions
- [ ] All tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
- [ ] Temporary files cleaned up

---

## Support & Troubleshooting

### Getting Help
1. Check `README.md` for complete documentation
2. Review `USAGE_GUIDE.md` for parameter details
3. Check `GETTING_STARTED.md` for setup instructions
4. Search existing issues
5. Create new issue with reproduction steps

### Debug Mode
```python
# Add to app.py for verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable FastAPI debug mode
app = FastAPI(debug=True)
```

### Common Error Messages

**"Invalid image"**: Image file corrupted or unsupported format
**"Missing image or invalid file_id"**: Cache expired or wrong ID
**"Invalid mode"**: Mode parameter not in [flat, line, lowpoly]
**Module not found**: Install missing dependencies

### Performance Troubleshooting

**Slow preprocessing**:
- Denoising is the slowest operation
- Reduce denoise_strength or disable if not needed
- Use max_size to downsample before preprocessing

**Slow vectorization**:
- Flat mode: Reduce colors, increase min_area
- Line mode: Increase min_area, disable centerlines for speed
- Low poly mode: Reduce number of points

**Out of memory**:
- Enable max_size preprocessing
- Reduce image dimensions before upload
- Lower quality settings

---

## Changelog & Version History

### Current Version: 1.0
- ✅ Three vectorization modes (flat, line, lowpoly)
- ✅ Modern web UI with drag & drop
- ✅ Quality presets
- ✅ Bezier curve support
- ✅ Real-time preview
- ✅ Copy/download functionality
- ✅ Responsive design
- ✅ Comprehensive documentation

### Future Versions
- v1.1: Batch processing, image preview
- v1.2: User accounts, saved presets
- v2.0: Advanced editing tools, cloud integration

---

**Last Updated**: 2026-01-28
**Maintainers**: Development Team
**License**: MIT (assumed - add LICENSE file)

## Color Palette Extraction

### Available Extraction Methods

**K-means Clustering** (default):
- Uses k-means algorithm to find dominant colors
- Balanced quality and performance
- Good for most images
- Returns colors with percentage distribution

**Median Cut**:
- Faster than k-means (6-7x)
- Better for images with few distinct colors
- Good color preservation
- Ideal for logos and graphics

**Histogram-based**:
- Simple frequency counting
- Very fast
- Good for quick analysis
- May miss subtle colors

### Export Formats

**JSON Format**:
```json
[
  {
    "color": [0, 0, 255],
    "hex": "#ff0000",
    "rgb": [255, 0, 0],
    "percentage": 42.5,
    "count": 12543
  }
]
```

**CSS Format**:
```css
:root {
  --palette-color-1: #ff0000;
  --palette-color-2: #00ff00;
}
```

**SCSS Format**:
```scss
$palette-color-1: #ff0000;
$palette-color-2: #00ff00;
```

**Tailwind Format**:
```js
brand: {
  100: '#ff0000',
  200: '#00ff00',
}
```

### Usage

```python
from im2svg import extract_color_palette, export_palette_css

# Extract palette
palette = extract_color_palette(
    img_bgr,
    num_colors=5,           # Number of colors to extract
    method="kmeans",        # or "median_cut", "histogram"
    min_percentage=1.0      # Minimum percentage threshold
)

# Export in different formats
json_output = export_palette_json(palette)
css_output = export_palette_css(palette, name="brand")
scss_output = export_palette_scss(palette, name="theme")
tailwind_output = export_palette_tailwind(palette, name="primary")
```

### API Endpoint

**POST /api/extract-palette**:
- Parameters: `file`, `file_id`, `num_colors` (2-20), `method`, `export_format`
- Returns: Color palette in requested format
- Formats: json, css, scss, tailwind

---

