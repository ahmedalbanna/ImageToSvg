# 🚀 Getting Started with im2svg

## Installation & Setup

### Prerequisites
- Python 3.7+
- pip package manager

### Step-by-Step Installation

```bash
# 1. Navigate to project directory
cd im2svg

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn app:app --reload

# 4. Open in browser
# Navigate to: http://localhost:8000
```

That's it! You're ready to convert images to SVG! 🎉

---

## Your First Conversion

### Quick Test (30 seconds)

1. **Open your browser** to `http://localhost:8000`

2. **Upload an image** - drag & drop any PNG or JPG

3. **Watch the magic happen** - your image is automatically converted to SVG!

4. **Download** - click the 💾 Download button to save your SVG

### Try Different Modes

- **Flat Mode**: Great for logos and icons
- **Line Mode**: Perfect for sketches and drawings  
- **Low Poly Mode**: Create artistic geometric versions

---

## What's Included

### 📁 Project Structure

```
im2svg/
├── app.py                 # FastAPI backend server
├── im2svg.py             # Vectorization algorithms
├── requirements.txt      # Python dependencies
├── README.md            # Complete documentation
├── USAGE_GUIDE.md       # Detailed usage instructions
├── GETTING_STARTED.md   # This file
├── .gitignore           # Git ignore rules
├── static/              # Frontend assets
│   ├── css/
│   │   └── style.css   # Modern, responsive styling
│   └── js/
│       └── app.js      # Interactive features
└── templates/
    └── index.html      # Main UI page
```

### ✨ Features

- **🎨 Multiple Conversion Modes**: Flat, Line, and Low Poly
- **⚙️ Customizable Parameters**: Fine-tune every aspect
- **🎯 Quality Presets**: Quick setup for common use cases
- **📱 Responsive Design**: Works on desktop and mobile
- **🖱️ Drag & Drop**: Easy file upload
- **📋 Copy to Clipboard**: One-click SVG code copy
- **💾 Direct Download**: Save SVG files instantly
- **🔄 Auto-conversion**: Instant preview after upload
- **〰️ Bezier Curves**: Smooth vector paths
- **📊 Real-time Preview**: See results immediately

---

## Common Commands

### Development

```bash
# Start with auto-reload (development)
uvicorn app:app --reload

# Start on specific host/port
uvicorn app:app --host 0.0.0.0 --port 9003

# Check if dependencies are installed
pip list | grep -E "fastapi|uvicorn|opencv"
```

### Production

```bash
# Production mode with multiple workers
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# With logging
uvicorn app:app --host 0.0.0.0 --port 8000 --log-level info
```

---

## Quick Tips

### For Best Results

1. **Start with Medium quality preset** - good balance of speed and quality
2. **Use PNG files** for images with transparency
3. **Reduce large images** before uploading (recommended: under 2000px)
4. **Try different modes** - each excels at different image types

### Troubleshooting

**Server won't start?**
```bash
# Check if port is in use
lsof -i :8000

# Try different port
uvicorn app:app --port 8001
```

**Module not found errors?**
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

**Conversion fails?**
- Check image format (PNG, JPG, JPEG supported)
- Try reducing image size
- Check browser console for errors

---

## Next Steps

### Learn More

- 📖 Read [README.md](README.md) for complete documentation
- 📚 Check [USAGE_GUIDE.md](USAGE_GUIDE.md) for detailed parameter explanations
- 🔧 Explore the API endpoints for programmatic access

### Customize

- 🎨 Edit `static/css/style.css` to change the theme
- ⚙️ Modify `static/js/app.js` to add new features
- 🎯 Add custom presets in the PRESETS object

### Deploy

Ready for production? Consider:
- Using gunicorn with uvicorn workers
- Setting up Nginx as reverse proxy
- Implementing Redis for caching
- Adding authentication if needed

---

## Support

Having issues? 

1. Check the README.md troubleshooting section
2. Review USAGE_GUIDE.md for parameter help
3. Check server logs for error messages
4. Verify all dependencies are installed

---

## Resources

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **OpenCV Python**: https://docs.opencv.org/
- **SVG Specification**: https://www.w3.org/TR/SVG/

---

**Enjoy creating beautiful SVGs! 🎨✨**

For detailed usage instructions, see [USAGE_GUIDE.md](USAGE_GUIDE.md)
