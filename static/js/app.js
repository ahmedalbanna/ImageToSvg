// DOM Elements
const form = document.getElementById('form');
const preview = document.getElementById('preview');
const svgtext = document.getElementById('svgtext');
const fileInput = document.getElementById('file-input');
const fileIdInput = document.getElementById('file-id');
const uploadStatus = document.getElementById('upload-status');
const convertBtn = document.getElementById('convert-btn');
const copyBtn = document.getElementById('copy-btn');
const dropZone = document.getElementById('drop-zone');
const modeSelect = document.getElementById('mode-select');

// Option fieldsets
const flatOptions = document.getElementById('flat-options');
const lineOptions = document.getElementById('line-options');
const bezierOptions = document.getElementById('bezier-options');
const lowpolyOptions = document.getElementById('lowpoly-options');

// Preprocessing
const preprocessEnable = document.getElementById('preprocess-enable');
const preprocessOptions = document.getElementById('preprocess-options');

// Preset configurations
const PRESETS = {
  flat: {
    low: { colors: 4, min_area: 50, epsilon: 0.005, smoothness: 0 },
    medium: { colors: 8, min_area: 20, epsilon: 0.003, smoothness: 1 },
    high: { colors: 16, min_area: 10, epsilon: 0.001, smoothness: 2 }
  },
  line: {
    low: { blur: 3, centerline_prune: 16, epsilon: 0.005 },
    medium: { blur: 1, centerline_prune: 8, epsilon: 0.003 },
    high: { blur: 0, centerline_prune: 4, epsilon: 0.001 }
  },
  lowpoly: {
    low: { points: 500, tri_blur: 2 },
    medium: { points: 1000, tri_blur: 1 },
    high: { points: 2000, tri_blur: 0 }
  }
};

/**
 * Show/hide option sections based on selected mode
 */
function updateOptionsVisibility() {
  const mode = modeSelect.value;
  
  // Hide all mode-specific options first
  flatOptions.style.display = mode === 'flat' ? 'block' : 'none';
  lineOptions.style.display = mode === 'line' ? 'block' : 'none';
  lowpolyOptions.style.display = mode === 'lowpoly' ? 'block' : 'none';
  
  // Bezier options are shown for flat and line modes
  bezierOptions.style.display = (mode === 'flat' || mode === 'line') ? 'block' : 'none';
}

/**
 * Update upload status display
 */
function setUploadStatus(message, type = '') {
  uploadStatus.textContent = message;
  uploadStatus.className = 'status';
  if (type) {
    uploadStatus.classList.add(type);
  }
}

/**
 * Handle file upload to cache
 */
async function handleUpload(file) {
  if (!file) return;
  
  const fd = new FormData();
  fd.append('file', file);
  
  setUploadStatus('Uploading...', 'uploading');
  convertBtn.disabled = true;
  
  try {
    const resp = await fetch('/api/upload', { method: 'POST', body: fd });
    if (!resp.ok) {
      throw new Error(await resp.text());
    }
    
    const data = await resp.json();
    fileIdInput.value = data.id;
    setUploadStatus(`✓ Ready (${data.width}×${data.height})`, 'ready');
    
    // Automatically trigger conversion after upload
    setTimeout(() => {
      form.dispatchEvent(new Event('submit'));
    }, 100);
  } catch (e) {
    setUploadStatus(`✗ Error: ${e.message}`, 'error');
    console.error('Upload failed:', e);
  } finally {
    convertBtn.disabled = false;
  }
}

/**
 * Handle form submission and conversion
 */
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  
  // Validate that we have an image
  if (!fileIdInput.value && !fileInput.files.length) {
    alert('Please select an image first.');
    return;
  }
  
  // Disable button and show loading state
  convertBtn.disabled = true;
  convertBtn.classList.add('loading');
  const originalText = convertBtn.querySelector('.btn-text').textContent;
  convertBtn.querySelector('.btn-text').textContent = 'Converting';
  
  const fd = new FormData(form);
  
  // Normalize checkbox values
  ['adaptive', 'invert', 'bezier', 'bezier_recursive', 'centerline', 'preprocess', 'contrast', 'denoise', 'sharpen', 'auto_crop', 'preserve_hierarchy', 'variable_width', 'adaptive_sampling', 'detect_gradients', 'detect_patterns', 'optimize_svg', 'minify_svg'].forEach(name => {
    const checkbox = form.elements[name];
    if (checkbox) {
      fd.set(name, checkbox.checked ? 'true' : 'false');
    }
  });
  
  try {
    // Add timeout for slow conversions
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout
    
    const resp = await fetch('/api/convert', { 
      method: 'POST', 
      body: fd,
      signal: controller.signal 
    });
    
    clearTimeout(timeoutId);
    
    if (!resp.ok) {
      const errorText = await resp.text();
      throw new Error(errorText);
    }
    
    // Get the SVG result
    const svg = await resp.text();
    
    // Update preview
    preview.innerHTML = svg;
    
    // Update textarea
    svgtext.value = svg;
    
    // Show action buttons
    copyBtn.style.display = 'inline-flex';
    if (downloadBtn) {
      downloadBtn.style.display = 'inline-flex';
    }
    
    // Success feedback
    setUploadStatus('✓ Conversion complete', 'ready');
  } catch (e) {
    let errorMsg = 'Conversion failed';
    if (e.name === 'AbortError') {
      errorMsg = 'Conversion timed out (60s limit)';
    } else if (e.message) {
      errorMsg = e.message;
    }
    alert(`Conversion error: ${errorMsg}`);
    setUploadStatus(`✗ ${errorMsg}`, 'error');
    console.error('Conversion error:', e);
  } finally {
    convertBtn.disabled = false;
    convertBtn.classList.remove('loading');
    convertBtn.querySelector('.btn-text').textContent = originalText;
  }
});

/**
 * Copy SVG to clipboard
 */
copyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(svgtext.value);
    const originalText = copyBtn.innerHTML;
    copyBtn.innerHTML = '✓ Copied!';
    setTimeout(() => {
      copyBtn.innerHTML = originalText;
    }, 2000);
  } catch (e) {
    alert('Failed to copy to clipboard');
    console.error('Copy failed:', e);
  }
});

/**
 * Download SVG button
 */
const downloadBtn = document.getElementById('download-btn');
if (downloadBtn) {
  downloadBtn.addEventListener('click', downloadSVG);
}

/**
 * Drag and drop handlers
 */
dropZone.addEventListener('click', () => {
  fileInput.click();
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  
  const files = e.dataTransfer.files;
  if (files.length) {
    // Set the file input
    fileInput.files = files;
    await handleUpload(files[0]);
  }
});

/**
 * File input change handler
 */
fileInput.addEventListener('change', (e) => {
  if (fileInput.files.length) {
    handleUpload(fileInput.files[0]);
  }
});

/**
 * Apply preset configuration
 */
function applyPreset(quality) {
  if (!quality) return;
  
  const mode = modeSelect.value;
  const preset = PRESETS[mode]?.[quality];
  
  if (!preset) return;
  
  Object.entries(preset).forEach(([key, value]) => {
    const input = form.elements[key];
    if (input) {
      input.value = value;
    }
  });
}

/**
 * Download SVG as file
 */
function downloadSVG() {
  const svgContent = svgtext.value;
  if (!svgContent) {
    alert('No SVG to download');
    return;
  }
  
  const blob = new Blob([svgContent], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `im2svg_${Date.now()}.svg`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Quality preset change handler
 */
const qualitySelect = form.elements['quality'];
if (qualitySelect) {
  qualitySelect.addEventListener('change', (e) => {
    applyPreset(e.target.value);
  });
}

/**
 * Mode select change handler
 */
modeSelect.addEventListener('change', updateOptionsVisibility);

/**
 * Preprocessing toggle handler
 */
if (preprocessEnable) {
  preprocessEnable.addEventListener('change', (e) => {
    preprocessOptions.style.display = e.target.checked ? 'block' : 'none';
  });
}

/**
 * Initialize
 */
updateOptionsVisibility();
