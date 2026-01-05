from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import HTMLResponse, Response
import numpy as np
import cv2

from im2svg import (
    vectorize_flat,
    vectorize_line,
    lowpoly,
    build_svg_string,
)

app = FastAPI(title="im2svg API", version="1.0")


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>im2svg – Image to SVG</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; }
    .row { display: flex; gap: 2rem; align-items: flex-start; }
    .panel { border: 1px solid #ddd; padding: 1rem; border-radius: 8px; }
    label { display:block; margin-top: .5rem; }
    input[type=number] { width: 6rem; }
    textarea { width: 100%; height: 400px; }
    #preview { border:1px dashed #aaa; min-width: 320px; min-height: 240px; padding: .5rem; }
    button { padding: .5rem 1rem; }
  </style>
</head>
<body>
  <h1>im2svg – Image to SVG</h1>
  <div class=\"row\">
    <div class=\"panel\">
      <form id=\"form\">
        <label>Image: <input type=\"file\" name=\"file\" accept=\"image/*\" required></label>
        <label>Mode:
          <select name=\"mode\">
            <option value=\"flat\">flat</option>
            <option value=\"line\">line</option>
            <option value=\"lowpoly\">lowpoly</option>
          </select>
        </label>
        <label>Quality preset:
          <select name=\"quality\">
            <option value=\"\">(default)</option>
            <option value=\"low\">low</option>
            <option value=\"medium\">medium</option>
            <option value=\"high\">high</option>
          </select>
        </label>
        <fieldset>
          <legend>Flat options</legend>
          <label>colors: <input type=\"number\" name=\"colors\" value=\"8\" min=\"2\" max=\"32\"></label>
          <label>min_area: <input type=\"number\" name=\"min_area\" value=\"20\" min=\"1\"></label>
          <label>epsilon: <input type=\"number\" step=\"0.0005\" name=\"epsilon\" value=\"0.003\"></label>
          <label>close_kernel: <input type=\"number\" name=\"close_kernel\" value=\"3\" min=\"0\"></label>
          <label>fill_rule:
            <select name=\"fill_rule\">
              <option value=\"evenodd\">evenodd</option>
              <option value=\"nonzero\">nonzero</option>
            </select>
          </label>
        </fieldset>
        <fieldset>
          <legend>Line options</legend>
          <label><input type=\"checkbox\" name=\"adaptive\"> adaptive</label>
          <label>thresh: <input type=\"number\" name=\"thresh\" value=\"-1\" min=\"-1\" max=\"255\"></label>
          <label><input type=\"checkbox\" name=\"invert\" checked> invert</label>
          <label>blur: <input type=\"number\" name=\"blur\" value=\"0\" min=\"0\"></label>
          <label>line_output:
            <select name=\"line_output\">
              <option value=\"fill\">fill</option>
              <option value=\"stroke\">stroke</option>
              <option value=\"both\">both</option>
            </select>
          </label>
          <label>stroke_color: <input type=\"text\" name=\"stroke_color\" value=\"#000000\"></label>
          <label>stroke_width_scale: <input type=\"number\" step=\"0.1\" name=\"stroke_width_scale\" value=\"1.0\"></label>
          <label><input type=\"checkbox\" name=\"centerline\" checked> centerline</label>
          <label>centerline_prune: <input type=\"number\" name=\"centerline_prune\" value=\"8\"></label>
          <label>centerline_rdp: <input type=\"number\" step=\"0.5\" name=\"centerline_rdp\" value=\"0\"></label>
        </fieldset>
        <fieldset>
          <legend>Bezier options</legend>
          <label><input type=\"checkbox\" name=\"bezier\"> bezier</label>
          <label><input type=\"checkbox\" name=\"bezier_recursive\"> bezier_recursive</label>
          <label>bezier_seglen: <input type=\"number\" name=\"bezier_seglen\" value=\"16\" min=\"4\"></label>
          <label>bezier_maxerr: <input type=\"number\" step=\"0.1\" name=\"bezier_maxerr\" value=\"2.0\"></label>
        </fieldset>
        <fieldset>
          <legend>Lowpoly</legend>
          <label>points: <input type=\"number\" name=\"points\" value=\"1000\" min=\"100\" step=\"50\"></label>
          <label>tri_blur: <input type=\"number\" name=\"tri_blur\" value=\"1\" min=\"0\"></label>
        </fieldset>
        <button type=\"submit\">Convert</button>
      </form>
    </div>
    <div class=\"panel\" style=\"flex:1\">
      <h3>Preview</h3>
      <div id=\"preview\"></div>
      <h3>SVG</h3>
      <textarea id=\"svgtext\" readonly></textarea>
    </div>
  </div>
<script>
const form = document.getElementById('form');
const preview = document.getElementById('preview');
const svgtext = document.getElementById('svgtext');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(form);
  // Checkbox normalization
  ['adaptive','invert','bezier','bezier_recursive','centerline'].forEach(name => {
    fd.set(name, form.elements[name].checked ? 'true' : 'false');
  });
  const resp = await fetch('/api/convert', { method: 'POST', body: fd });
  if (!resp.ok) {
    const t = await resp.text();
    alert('Error: ' + t);
    return;
  }
  const svg = await resp.text();
  preview.innerHTML = svg;
  svgtext.value = svg;
});
</script>
</body>
</html>
"""


def _imdecode(file_bytes: bytes):
    arr = np.frombuffer(file_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


@app.post("/api/convert")
async def api_convert(
    file: UploadFile = File(...),
    mode: str = Form("flat"),
    quality: Optional[str] = Form(None),
    # flat
    colors: int = Form(8),
    min_area: int = Form(20),
    epsilon: float = Form(0.003),
    close_kernel: int = Form(3),
    fill_rule: str = Form("evenodd"),
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
    data = await file.read()
    img = _imdecode(data)
    if img is None:
        return Response("Invalid image", status_code=400)
    h, w = img.shape[:2]

    # Note: quality preset is implemented client-side by choosing defaults; keep params simple here

    if mode == 'flat':
        paths_fill = vectorize_flat(
            img, k_colors=max(2, int(colors)), min_area=max(1, int(min_area)),
            epsilon_ratio=max(1e-5, float(epsilon)), close_kernel=max(0, int(close_kernel)),
            fill_rule=fill_rule, bezier=(bezier == 'true'), bezier_seglen=max(4, int(bezier_seglen)),
            bezier_recursive=(bezier_recursive == 'true'), bezier_maxerr=float(bezier_maxerr)
        )
        svg = build_svg_string(w, h, paths_fill=paths_fill, paths_stroke=None, fill_rule=fill_rule)
    elif mode == 'line':
        paths_fill, paths_stroke = vectorize_line(
            img,
            adaptive=(adaptive == 'true'), thresh=int(thresh), invert=(invert == 'true'), blur=int(blur),
            min_area=max(1, int(min_area)), epsilon_ratio=max(1e-5, float(epsilon)), close_kernel=max(0, int(close_kernel)),
            bezier=(bezier == 'true'), bezier_seglen=max(4, int(bezier_seglen)),
            bezier_recursive=(bezier_recursive == 'true'), bezier_maxerr=float(bezier_maxerr),
            line_output=line_output, stroke_color=stroke_color, stroke_width_scale=float(stroke_width_scale),
            centerline=(centerline == 'true'), centerline_prune=int(centerline_prune), centerline_rdp=float(centerline_rdp)
        )
        svg = build_svg_string(w, h, paths_fill=paths_fill, paths_stroke=paths_stroke, fill_rule=fill_rule)
    elif mode == 'lowpoly':
        polygons = lowpoly(img, num_points=int(points), blur=int(tri_blur))
        svg = build_svg_string(w, h, paths_fill=[], polygons=polygons, fill_rule=fill_rule)
    else:
        return Response("Invalid mode", status_code=400)

    return Response(content=svg, media_type="image/svg+xml; charset=utf-8")
