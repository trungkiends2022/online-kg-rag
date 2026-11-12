import base64
import xml.etree.ElementTree as ET
from PIL import Image

# Read PNG image
png_path = '/workspace/kiennt/online-kg-rag/paper_v2/figures/fig3_two_tier_reasoning.png'
with open(png_path, 'rb') as f:
    png_bytes = f.read()

b64_str = base64.b64encode(png_bytes).decode('utf-8')

# Get image dimensions
im = Image.open(png_path)
orig_w, orig_h = im.size
aspect = orig_w / orig_h
print(f"Original image size: {orig_w} x {orig_h}, aspect ratio: {aspect:.3f}")

target_w = 1280
target_h = int(target_w / aspect)
print(f"Target Draw.io geometry: {target_w} x {target_h}")

# Vector diagram XML content
from create_fig3_flowchart_drawio import generate_fig3_drawio
vector_xml = generate_fig3_drawio()

# Extract inner root from vector_xml
vector_tree = ET.fromstring(vector_xml)

# Create multi-page mxfile XML
multi_page_xml = f"""<mxfile host="Electron" modified="2026-10-31T18:11:00.000Z" agent="Antigravity" version="21.0.0" type="device">
  <diagram id="page_png" name="Figure 3 (Rendered PNG)">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{target_w + 80}" pageHeight="{target_h + 80}" background="#ffffff">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="img_fig3" value="" style="shape=image;verticalLabelPosition=bottom;labelBackgroundColor=default;verticalAlign=top;aspect=fixed;imageAspect=0;image=data:image/png;base64,{b64_str};" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="{target_w}" height="{target_h}" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
  <diagram id="page_vector" name="Editable Flowchart Vectors">
    {vector_xml}
  </diagram>
</mxfile>"""

# Validate XML
try:
    ET.fromstring(multi_page_xml)
    print("Multi-page XML is 100% valid XML!")
except Exception as e:
    print("XML Error:", e)

with open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig3_two_tier_reasoning.drawio', 'w', encoding='utf-8') as f:
    f.write(multi_page_xml)

print("Saved multi-page figures/fig3_two_tier_reasoning.drawio successfully!")
