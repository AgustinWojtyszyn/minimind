"""Build a dependency-free static BoitIA page from the canonical frontend."""
import argparse
import json
import shutil
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from boitia.config import SYSTEM_PROMPT


def build(output):
    output.mkdir(parents=True, exist_ok=True)
    text = (ROOT / "frontend/index.html").read_text()
    marker = "<script>"
    assert text.count(marker) == 1
    config = json.dumps(SYSTEM_PROMPT, ensure_ascii=False).replace("<", "\\u003c")
    text = text.replace(marker, '<script src="client.js"></script>\n<script src="tools.js?v=5"></script>\n<script>window.BOITIA_LOCAL_SYSTEM='+config+';</script>\n'+marker, 1)
    (output / 'index.html').write_text(text)
    for name in ('client.js','local-worker.js','tools.js'):
        shutil.copyfile(ROOT/'frontend/portable'/name, output/name)
    (output/'.nojekyll').touch()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'docs')
    build(parser.parse_args().output)
