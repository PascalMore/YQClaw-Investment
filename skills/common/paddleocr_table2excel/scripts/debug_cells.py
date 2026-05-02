#!/usr/bin/env python3
"""Debug: Visualize cell positions by Y to understand row structure"""
import sys
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/.venv/lib/python3.10/site-packages')
sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant/skills/common/paddleocr_table2excel/scripts')

from paddleocr import PPStructure
import cv2, warnings, numpy as np
warnings.filterwarnings('ignore')

table_sys = PPStructure(table=True, lang='ch', show_log=False, layout=False)
img = cv2.imread('/tmp/cropped_table.jpg')
result = table_sys(img)
cell_bbox = result[0]['res']['cell_bbox']

# Get cell positions
def get_cell_info(idx, bbox):
    x_min = min(bbox[0], bbox[2], bbox[4], bbox[6])
    x_max = max(bbox[0], bbox[2], bbox[4], bbox[6])
    y_min = min(bbox[1], bbox[3], bbox[5], bbox[7])
    y_max = max(bbox[1], bbox[3], bbox[5], bbox[7])
    return {'x': x_min, 'y': y_min, 'w': x_max-x_min, 'h': y_max-y_min}

cells = [get_cell_info(i, b) for i, b in enumerate(cell_bbox)]

# Bin cells by Y (using 250px bands)
bands = {}
for c in cells:
    band = int(c['y']) // 250
    if band not in bands:
        bands[band] = []
    bands[band].append(c)

for band in sorted(bands.keys()):
    row_cells = bands[band]
    y_avg = sum(c['y'] for c in row_cells) / len(row_cells)
    x_min, x_max = min(c['x'] for c in row_cells), max(c['x'] + c['w'] for c in row_cells)
    print(f'Y_band {band*250}-{(band+1)*250} ({len(row_cells)} cells, avg_y={y_avg:.0f}): x_range=[{x_min:.0f}, {x_max:.0f}]')
    # Show cell X positions
    sorted_by_x = sorted(row_cells, key=lambda c: c['x'])
    xs = [f'{c["x"]:.0f}' for c in sorted_by_x[:10]]
    print(f'  First 10 X: {xs}')