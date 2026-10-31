from PIL import Image
import numpy as np

# Load image
im = Image.open('/workspace/kiennt/online-kg-rag/paper_v2/figures/fig3_perfect_out-1.png').convert('RGB')
arr = np.array(im)
print("Shape:", arr.shape)
