#!/usr/bin/env python3
"""Embed the offline explorer's styles and scripts in one portable HTML file."""

import argparse
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent


def build_html():
    html = (HERE / 'index.html').read_bytes().decode('utf-8')
    css = (HERE / 'styles.css').read_bytes().decode('utf-8')
    style_pattern = r'<link\b[^>]*href=[\"\'](?:\./)?styles\.css[\"\'][^>]*>'
    html, count = re.subn(style_pattern, lambda match: '<style>\n' + css + '\n</style>', html)
    if count != 1:
        raise ValueError('Expected exactly one styles.css reference')
    for name in ('data.js', 'app.js'):
        javascript = (HERE / name).read_bytes().decode('utf-8')
        javascript = re.sub(r'</script', r'<\\/script', javascript, flags=re.IGNORECASE)
        pattern = r'<script\b[^>]*src=[\"\'](?:\./)?' + re.escape(name) + r'[\"\'][^>]*>\s*</script>'
        html, count = re.subn(pattern, lambda match: '<script>\n' + javascript + '\n</script>', html)
        if count != 1:
            raise ValueError('Expected exactly one {} reference'.format(name))
    if re.search(r'<script\b[^>]*\bsrc\s*=', html, re.IGNORECASE):
        raise ValueError('Standalone file still contains an external script')
    return html


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true', help='Verify the packaged HTML against its source files without writing')
    args = parser.parse_args()
    html = build_html()
    if args.check:
        if args.output is not None:
            parser.error('--check and --output cannot be combined')
        packaged = HERE / 'Temporal_Profile_Explorer.html'
        if not packaged.is_file() or packaged.read_bytes() != html.encode('utf-8'):
            parser.exit(1, 'Portable HTML differs from its sources. Rebuild and review it before committing.\n')
        print('Portable HTML source comparison: PASS')
        return
    output = (args.output or Path('Temporal_Profile_Explorer.html')).expanduser().resolve()
    if output == (HERE / 'index.html').resolve():
        parser.error('Choose an output path other than the source index.html')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(html.encode('utf-8'))
    print('Created {} ({} bytes). Open this file in a browser.'.format(output, output.stat().st_size))


if __name__ == '__main__':
    main()
