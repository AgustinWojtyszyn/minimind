"""Build a dependency-free static BoitIA page from the canonical frontend."""
import argparse
import json
import shutil
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from boitia.config import SYSTEM_PROMPT


def render_index():
    text = (ROOT / "frontend/index.html").read_text()
    text = text.replace("</head>", '<link rel="manifest" href="./manifest.webmanifest?v=2"><link rel="apple-touch-icon" href="./icon-192.png?v=2"><meta name="apple-mobile-web-app-capable" content="yes"></head>', 1)
    marker = "<script>"
    assert text.count(marker) == 1
    config = json.dumps(SYSTEM_PROMPT, ensure_ascii=False).replace("<", "\\u003c")
    text = text.replace(marker, '<script src="pwa.js"></script>\n<script src="client.js"></script>\n<script src="tools.js?v=6"></script>\n<script>window.BOITIA_LOCAL_SYSTEM='+config+';</script>\n'+marker, 1)
    return text


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(render_index())
    for name in ('client.js','local-worker.js','tools.js','pwa.js','manifest.webmanifest','sw.js','icon-192.png','icon-512.png'):
        shutil.copyfile(ROOT/'frontend/portable'/name, output/name)
    (output/'.nojekyll').touch()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'docs')
    parser.add_argument('--check', action='store_true', help='Fail if the published index diverges from the canonical frontend')
    args = parser.parse_args()
    if args.check:
        if (args.output / 'index.html').read_text() != render_index():
            parser.exit(1, 'Published index is stale; run scripts/build_portable.py.\n')
        print('Published index matches canonical frontend.')
    else:
        build(args.output)
