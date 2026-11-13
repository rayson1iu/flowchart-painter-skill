#!/usr/bin/env python3
"""Render an editable SVG to PNG using an available local renderer."""
import argparse
import importlib.util
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def run(args):
    subprocess.run([str(a) for a in args], check=True, capture_output=True, text=True)


def png_size(path):
    with open(path, 'rb') as f:
        header = f.read(24)
    if header[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('Renderer did not produce a valid PNG')
    return struct.unpack('>II', header[16:24])


def dimension(root, key, fallback):
    raw = root.get(key, '').removesuffix('px')
    try:
        value = float(raw)
    except ValueError:
        value = fallback
    if value is None or not math.isfinite(value) or value <= 0:
        raise ValueError('SVG needs positive width/height in pixels or a valid viewBox')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('svg', type=Path)
    parser.add_argument('png', type=Path)
    parser.add_argument('--scale', type=float, default=2)
    args = parser.parse_args()
    if not math.isfinite(args.scale) or args.scale <= 0:
        parser.error('--scale must be positive and finite')
    source, target = args.svg.resolve(), args.png.resolve()
    if source == target:
        parser.error('Input and output paths must differ')
    root = ET.parse(source).getroot()
    if root.tag != '{http://www.w3.org/2000/svg}svg':
        parser.error('Input must be an SVG with the SVG namespace')
    view = [float(x) for x in root.get('viewBox', '').replace(',', ' ').split()]
    w = dimension(root, 'width', view[2] if len(view) == 4 else None)
    h = dimension(root, 'height', view[3] if len(view) == 4 else None)
    width, height = max(1, round(w * args.scale)), max(1, round(h * args.scale))
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='flowchart-') as tmp:
        tmp = Path(tmp)
        rendered = tmp / 'rendered.png'
        if shutil.which('rsvg-convert'):
            renderer = 'rsvg-convert'
            run([renderer, '--width', width, '--height', height, '--background-color', 'white', '--output', rendered, source])
        elif importlib.util.find_spec('cairosvg'):
            renderer = 'CairoSVG'
            import cairosvg
            cairosvg.svg2png(url=str(source), write_to=str(rendered), output_width=width, output_height=height, background_color='white')
        elif shutil.which('qlmanage') and shutil.which('swift'):
            renderer = 'Quick Look'
            # Quick Look can return a square preview; explicitly pad at top-left
            # and crop the same origin to retain the source aspect ratio.
            edge = max(width, height)
            ns = 'http://www.w3.org/2000/svg'
            ET.register_namespace('', ns)
            square = ET.Element(f'{{{ns}}}svg', {'width': str(edge), 'height': str(edge), 'viewBox': f'0 0 {edge} {edge}'})
            ET.SubElement(square, f'{{{ns}}}rect', {'width': '100%', 'height': '100%', 'fill': 'white'})
            root.set('x', '0'); root.set('y', '0')
            root.set('width', str(width)); root.set('height', str(height))
            if not root.get('viewBox'):
                root.set('viewBox', f'0 0 {w} {h}')
            square.append(root)
            padded = tmp / 'padded.svg'
            ET.ElementTree(square).write(padded, encoding='utf-8', xml_declaration=True)
            run(['qlmanage', '-t', '-s', edge, '-o', tmp, padded])
            preview = tmp / 'padded.svg.png'
            if png_size(preview) != (edge, edge):
                raise RuntimeError('Unexpected Quick Look dimensions; use another renderer')
            run(['swift', '-module-cache-path', tmp / 'swift-cache', Path(__file__).with_name('crop_png.swift'), preview, rendered, width, height])
        else:
            raise RuntimeError('No SVG renderer available. Use rsvg-convert, CairoSVG, or macOS Quick Look + Swift.')
        actual = png_size(rendered)
        if actual != (width, height):
            raise RuntimeError(f'Expected {(width, height)}, got {actual}')
        shutil.copyfile(rendered, target)
    print(f'{renderer}: {target} ({width} × {height})')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, ET.ParseError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f'Export failed: {exc}')
