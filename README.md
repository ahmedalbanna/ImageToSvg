# im2svg - Image to SVG Converter

A modern web application for converting raster images (PNG, JPG, etc.) to scalable vector graphics (SVG) with multiple conversion modes and customizable parameters.

![im2svg Preview](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)

## ✨ Features

### Conversion Modes

- **🎨 Flat Mode**: Convert images to flat color regions with customizable color palettes
- **✏️ Line Mode**: Extract line art and sketches from images with advanced edge detection
- **🔷 Low Poly Mode**: Create artistic low-poly triangulated versions of images

### Advanced Options

- **Bezier Curves**: Smooth vector paths with cubic Bezier curve fitting
- **Quality Presets**: Quick settings for low, medium, or high-quality output
- **Real-time Preview**: Instant SVG preview in the browser
- **Customizable Parameters**: Fine-tune every aspect of the conversion
- **Drag & Drop**: Easy file upload with drag-and-drop support

### Modern UI

- 🎯 Clean, responsive design that works on all devices
- 🌈 Beautiful gradient theme with smooth animations
- 📋 One-click copy to clipboard
- 💾 Direct SVG file download
- 🔄 Auto-conversion after upload
- 📊 Real-time status updates

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. **Clone or download this repository**

```bash
git clone <your-repo-url>
cd im2svg
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Run the application**

```bash
uvicorn app:app --reload
```

4. **Open your browser**

Navigate to: `http://localhost:8000`

## 📦 Dependencies

The application requires the following Python packages:

```
opencv-python-headless  # Image processing
numpy                   # Numerical operations
svgwrite               # SVG generation
scipy                  # Scientific computing (optional, for Delaunay triangulation)
scikit-image          # Image processing algorithms
fastapi               # Web framework
uvicorn               # ASGI server
python-multipart      # File upload support
```

## 🎯 Usage Guide

### Basic Usage

1. **Upload an Image**
   - Click the upload area or drag & drop an image file
   - Supported formats: PNG, JPG, JPEG, BMP, GIF

2. **Choose Conversion Mode**
   - **Flat**: Best for logos, illustrations, and graphics with solid colors
   - **Line**: Ideal for sketches, drawings, and extracting outlines
   - **Low Poly**: Creates artistic geometric representations

3. **Adjust Parameters** (Optional)
   - Use quality presets for quick setup
   - Or manually fine-tune parameters for specific needs

4. **Convert & Download**
   - Conversion happens automatically after upload
   - Preview the result in real-time
   - Copy SVG code or download as file

### Mode-Specific Tips

#### Flat Mode
- **Colors**: Number of colors to quantize (2-64)
- **Min Area**: Minimum region size to keep (pixels)
- **Epsilon**: Path simplification threshold (lower = more detail)
- **Smoothness**: Morphological smoothing level (0-10)

**Best for**: Logos, icons, cartoons, flat illustrations

#### Line Mode
- **Threshold**: Binarization threshold (-1 for auto)
- **Adaptive**: Use adaptive thresholding for varied lighting
- **Invert**: Invert black/white colors
- **Centerline**: Extract skeleton centerlines for cleaner lines

**Best for**: Sketches, line drawings, coloring pages, technical drawings

#### Low Poly Mode
- **Points**: Number of triangulation points (100-5000+)
- **Triangle Blur**: Blur radius for color sampling

**Best for**: Artistic effects, backgrounds, geometric art

### Bezier Curve Options

Available for Flat and Line modes:
- **Enable Bezier**: Convert paths to smooth cubic Bezier curves
- **Segment Length**: Target segment length for curve fitting
- **Max Error**: Maximum allowed deviation from original path
- **Recursive**: Use recursive subdivision for better curve approximation

## 🏗️ Project Structure

```
im2svg/
├── app.py                  # FastAPI application & API endpoints
├── im2svg.py              # Core vectorization algorithms
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/               # Static assets
│   ├── css/
│   │   └── style.css    # Application styling
│   └── js/
│       └── app.js       # Frontend JavaScript
└── templates/
    └── index.html       # Main UI template
```

## 🔌 API Endpoints

The application exposes REST API endpoints for programmatic access:

### `GET /`
Serves the web UI

### `POST /api/upload`
Upload and cache an image

**Request:**
- `file`: Image file (multipart/form-data)

**Response:**
```json
{
  "id": "uuid-string",
  "width": 1920,
  "height": 1080
}
```

### `POST /api/convert`
Convert image to SVG

**Request Parameters:**
- `file_id` or `file`: Image source
- `mode`: Conversion mode (flat/line/lowpoly)
- `quality`: Preset quality level (optional)
- Mode-specific parameters (see UI for details)

**Response:**
- SVG file (image/svg+xml)

## 🛠️ Development

### Running in Development Mode

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Production Deployment

For production, consider:

1. **Use Gunicorn with Uvicorn workers:**
```bash
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

2. **Set up a reverse proxy (Nginx/Apache)**

3. **Enable HTTPS with SSL certificates**

4. **Implement proper caching:**
   - Replace in-memory cache with Redis or disk storage
   - Add cache TTL and cleanup

5. **Add rate limiting and authentication** if needed

## ⚙️ Configuration

### Host and Port

Edit the startup command or create a configuration file:

```bash
# Custom host and port
uvicorn app:app --host 185.190.140.93 --port 9003
```

### Environment Variables

You can use environment variables for configuration:

```bash
export HOST=0.0.0.0
export PORT=8000
export CACHE_SIZE=1000
```

## 🤝 Contributing

Contributions are welcome! Feel free to:

- Report bugs
- Suggest new features
- Submit pull requests
- Improve documentation

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Image processing powered by [OpenCV](https://opencv.org/)
- SVG generation using [svgwrite](https://pypi.org/project/svgwrite/)
- UI icons from inline SVG

## 📧 Support

If you encounter any issues or have questions:

1. Check the troubleshooting section below
2. Review existing issues
3. Create a new issue with details about your problem

## 🔧 Troubleshooting

### Common Issues

**Problem**: "Module not found" errors
```bash
# Solution: Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Problem**: Port already in use
```bash
# Solution: Use a different port
uvicorn app:app --port 8001
```

**Problem**: Image upload fails
- Check file size (consider adding size limits)
- Verify image format is supported
- Check browser console for errors

**Problem**: Slow conversion
- Try lower quality settings
- Reduce image resolution before upload
- Use fewer colors in Flat mode
- Reduce points in Low Poly mode

## 🎨 Customization

### Changing the Theme

Edit `static/css/style.css` and modify the CSS variables in `:root`:

```css
:root {
  --primary-color: #4f46e5;
  --primary-hover: #4338ca;
  /* ... more variables ... */
}
```

### Adding New Presets

Edit `static/js/app.js` and add to the `PRESETS` object:

```javascript
const PRESETS = {
  flat: {
    mypreset: { colors: 12, min_area: 15, ... }
  }
};
```

## 📊 Performance Tips

- **Use quality presets** for faster experimentation
- **Reduce image size** before uploading large images
- **Enable caching** for repeated conversions
- **Use appropriate modes**: Flat is fastest, Line is moderate, Low Poly varies with point count

## 🌟 Future Enhancements

Potential features for future versions:

- [ ] Batch processing multiple images
- [ ] Server-side preset management
- [ ] User accounts and saved configurations
- [ ] Export to additional formats (EPS, PDF)
- [ ] Advanced color palette extraction
- [ ] Image editing tools (crop, rotate, adjust)
- [ ] API authentication and rate limiting
- [ ] WebSocket support for real-time progress
- [ ] Docker containerization
- [ ] Cloud storage integration

---

**Made with ❤️ using FastAPI and OpenCV**
