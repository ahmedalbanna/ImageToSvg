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
- Color quantization using k-means
- Region extraction with morphological operations
- Contour detection and polygon simplification
- Optional Bezier curve fitting
- Best for: logos, icons, cartoons, flat illustrations

**2. Line Mode** (`vectorize_line`):
- Adaptive or fixed thresholding
- Optional centerline extraction using skeletonization
- Contour-to-path conversion
- Stroke or fill output options
- Best for: sketches, line art, technical drawings

**3. Low Poly Mode** (`lowpoly`):
- Feature point sampling (edges, random)
- Delaunay triangulation (scipy or cv2.Subdiv2D fallback)
- Triangle color averaging
- Best for: artistic effects, backgrounds

### Key Utility Functions

- `simplify_poly()` - Douglas-Peucker polygon simplification
- `polyline_to_beziers()` - Convert polylines to cubic Bezier curves
- `recursive_fit_beziers()` - Schneider-style recursive Bezier fitting
- `skeleton_centerlines()` - Extract and prune skeleton lines
- `stream_svg()` - Generator-based SVG streaming (memory efficient)

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

## Extension Ideas

### Near-term Enhancements

- **Image preview**: Show uploaded image thumbnail
- **History**: Store recent conversions (localStorage)
- **Batch processing**: Upload multiple images
- **More export formats**: EPS, PDF via additional libraries
- **Server-side presets**: Store and share configurations
- **Progress indicators**: For slow conversions

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
