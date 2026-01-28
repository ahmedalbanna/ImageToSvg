# 🎨 im2svg Usage Guide

## Quick Start

### 1. Start the Server

```bash
# Development mode (auto-reload on changes)
uvicorn app:app --reload

# Production mode
uvicorn app:app --host 0.0.0.0 --port 8000

# With multiple workers (production)
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 2. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:8000
```

---

## 🖼️ Converting Images

### Method 1: Drag & Drop
1. Simply drag an image file onto the drop zone
2. The image uploads automatically
3. Conversion starts immediately with default settings

### Method 2: File Browser
1. Click "Choose Image" or the drop zone
2. Select an image from your computer
3. Wait for upload and auto-conversion

---

## 🎛️ Understanding Parameters

### Mode Selection

#### **Flat Mode** 🎨
Best for: Logos, illustrations, cartoons, icons

**Key Parameters:**
- **Colors (2-64)**: How many colors to reduce the image to
  - Low values (2-4): Simple, bold graphics
  - Medium values (8-12): Balanced detail
  - High values (16+): More detailed, gradients
  
- **Min Area (1-100)**: Minimum size of regions to keep
  - Higher values: Removes small details, cleaner output
  - Lower values: Preserves tiny features
  
- **Epsilon (0.001-0.01)**: Path simplification
  - Lower values: More accurate paths, larger file
  - Higher values: Simpler paths, smaller file
  
- **Smoothness (0-10)**: Smoothing level
  - 0: No smoothing, preserves edges
  - 5+: Significant smoothing, rounder shapes

**Example Settings:**
```
Logo/Icon: colors=4, min_area=50, epsilon=0.005
Illustration: colors=12, min_area=20, epsilon=0.003
Detailed art: colors=24, min_area=10, epsilon=0.001
```

---

#### **Line Mode** ✏️
Best for: Sketches, line art, coloring pages, technical drawings

**Key Parameters:**
- **Threshold (-1 to 255)**: Binarization level
  - -1: Auto-detect (Otsu's method)
  - 0-255: Manual threshold value
  
- **Adaptive**: Better for images with varying lighting
  
- **Invert**: Swap black and white
  - Check: Black lines on white background
  - Uncheck: White lines on black background
  
- **Centerline**: Extract skeleton of lines
  - Enabled: Thin lines converted to strokes
  - Disabled: Filled regions
  
- **Blur (0-10)**: Pre-processing blur
  - 0: No blur, preserves fine details
  - 3+: Smooths noise, cleaner lines

**Example Settings:**
```
Clean sketch: adaptive=off, thresh=-1, blur=0, centerline=on
Noisy drawing: adaptive=on, blur=2, centerline=on
Coloring page: invert=on, centerline=off, line_output=fill
```

---

#### **Low Poly Mode** 🔷
Best for: Artistic effects, backgrounds, geometric art

**Key Parameters:**
- **Points (100-5000+)**: Number of triangulation vertices
  - 500-1000: Abstract, geometric look
  - 1000-2000: Balanced detail
  - 2000+: High detail, almost realistic
  
- **Triangle Blur (0-5)**: Color sampling blur
  - 0: Sharp color transitions
  - 2+: Smoother color gradients

**Example Settings:**
```
Abstract art: points=500, tri_blur=2
Portrait: points=2000, tri_blur=1
Background: points=1000, tri_blur=1
```

---

### Bezier Curve Options 〰️

Available for Flat and Line modes. Converts straight paths to smooth curves.

- **Enable Bezier**: Turn on curve fitting
- **Segment Length (4-32)**: Target length for curve segments
  - Lower: More control points, more accurate
  - Higher: Fewer points, smoother but less accurate
  
- **Max Error (0.5-5.0)**: Maximum deviation allowed
  - Lower: Stays closer to original path
  - Higher: Allows more simplification
  
- **Recursive**: Advanced curve fitting algorithm
  - Better for complex organic shapes
  - Slower but more accurate

**When to use:**
- Logos with curves
- Organic shapes
- Typography
- Smooth illustrations

---

## 🎯 Quality Presets

Quick settings for common use cases:

### Low Quality
- Fastest processing
- Smallest file size
- Good for previews and testing

### Medium Quality
- Balanced speed and quality
- Recommended for most use cases
- Good detail with reasonable file size

### High Quality
- Best output quality
- Larger file sizes
- Longer processing time
- Use for final production work

**Tip:** Start with Medium, then adjust individual parameters as needed.

---

## 💡 Tips & Tricks

### Getting the Best Results

1. **Image Preparation**
   - Use high-contrast images for Line mode
   - Reduce noise before uploading
   - Crop to remove unwanted areas
   - Use PNG for images with transparency

2. **File Size Optimization**
   - Increase epsilon for smaller files
   - Use fewer colors in Flat mode
   - Enable Bezier for smoother paths with fewer points
   - Increase min_area to remove small details

3. **Quality Improvement**
   - Lower epsilon for more accurate paths
   - Use more colors for gradients
   - Disable Bezier for geometric shapes
   - Adjust smoothness for organic shapes

4. **Performance**
   - Start with smaller images for testing
   - Use Low quality preset for quick iterations
   - Reduce points in Low Poly mode if slow
   - Clear browser cache if preview seems stuck

---

## 🚀 Advanced Usage

### API Access

You can use the API programmatically:

```python
import requests

# Upload image
with open('image.png', 'rb') as f:
    response = requests.post('http://localhost:8000/api/upload', 
                            files={'file': f})
    file_id = response.json()['id']

# Convert to SVG
params = {
    'file_id': file_id,
    'mode': 'flat',
    'colors': 8,
    'min_area': 20
}
response = requests.post('http://localhost:8000/api/convert', data=params)
svg_content = response.text

# Save SVG
with open('output.svg', 'w') as f:
    f.write(svg_content)
```

### Batch Processing

```bash
# Convert multiple images
for img in *.png; do
    curl -X POST -F "file=@$img" \
         -F "mode=flat" \
         -F "colors=8" \
         http://localhost:8000/api/convert > "${img%.png}.svg"
done
```

---

## 🎨 Use Cases

### Logos & Icons
```
Mode: Flat
Colors: 4-8
Min Area: 30
Epsilon: 0.005
Bezier: Enabled
```

### Coloring Pages
```
Mode: Line
Adaptive: Off
Threshold: -1
Invert: On
Centerline: Off
Line Output: Fill
```

### Portrait Art
```
Mode: Low Poly
Points: 2000
Triangle Blur: 1
```

### Technical Drawings
```
Mode: Line
Centerline: On
Threshold: 200
Blur: 0
Epsilon: 0.001
```

### Abstract Art
```
Mode: Low Poly
Points: 500-800
Triangle Blur: 2
```

---

## ❓ FAQ

**Q: Why is my SVG file so large?**
A: Increase epsilon, reduce colors, or increase min_area to simplify.

**Q: The conversion is slow. What can I do?**
A: Use smaller images, lower quality settings, or fewer points in Low Poly mode.

**Q: Lines are jagged. How to smooth them?**
A: Enable Bezier curves or increase smoothness parameter.

**Q: Colors don't match the original.**
A: Try increasing the number of colors or adjusting the image before upload.

**Q: Can I process transparent images?**
A: Yes, upload PNG files with transparency. The alpha channel is preserved.

**Q: What's the maximum image size?**
A: There's no hard limit, but larger images take longer to process. Recommended: under 2000x2000 pixels.

---

## 🔗 Additional Resources

- [SVG Specification](https://www.w3.org/TR/SVG/)
- [OpenCV Documentation](https://docs.opencv.org/)
- [Bezier Curves Explained](https://en.wikipedia.org/wiki/B%C3%A9zier_curve)
- [Image Vectorization Techniques](https://en.wikipedia.org/wiki/Image_tracing)

---

**Happy Vectorizing! 🎉**
