"""Mobile Chromium integration: mocked inference, actual file downloads and parsing."""
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.sync_api import sync_playwright
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
PROMPT = "Dame un PDF con tres recetas de pollo"
RESPONSE = ("Como soy un modelo de lenguaje, no puedo generar ni entregarte un archivo "
            "descargable directamente (como un PDF), pero puedo redactar todo.\n\n"
            "Acá tenés el contenido:\n\n---\n\n# Recetario\n"
            "1. Pollo al horno con papas.\n2. Pollo con arroz.\n3. Pollo salteado.")
ORIGIN = "https://agustinwojtyszyn.github.io"
BACKEND = "https://boitia-ai.agustinwojtyszyn.com"

with sync_playwright() as p, TemporaryDirectory() as tmp:
    browser = p.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"), args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 393, "height": 873}, is_mobile=True, has_touch=True, accept_downloads=True)
    posts = []
    def static(route):
        name = route.request.url.split("/minimind/", 1)[1].split("?")[0] or "index.html"
        if name == "engine.json":
            route.fulfill(json={"version": 1, "cloudflare_url": BACKEND})
        elif name in {"index.html", "client.js", "tools.js"}:
            route.fulfill(body=(ROOT/"docs"/name).read_text(), content_type="text/html" if name.endswith(".html") else "application/javascript")
        else:
            route.fulfill(status=404)

    def backend(route):
        if route.request.method == "OPTIONS":
            route.fulfill(status=204, headers={"Access-Control-Allow-Origin":ORIGIN,"Access-Control-Allow-Methods":"POST, OPTIONS","Access-Control-Allow-Headers":"content-type"})
            return
        posts.append(route.request.post_data_json)
        answer = RESPONSE if len(posts)==1 else "# Tabla\n| Nombre | Valor |\n|---|---|\n| Enero | 12 |"
        frames = [{"choices":[{"delta":{"content":answer},"finish_reason":None}]},
                  {"choices":[{"delta":{},"finish_reason":"stop"}]}]
        route.fulfill(status=200,headers={"Access-Control-Allow-Origin":ORIGIN,"Content-Type":"text/event-stream"},body="".join("data: "+json.dumps(f)+"\n\n" for f in frames)+"data: [DONE]\n\n")

    page.route(ORIGIN+"/minimind/**", static)
    page.route(BACKEND+"/**", backend)
    page.goto(ORIGIN+"/minimind/")
    page.wait_for_function("document.querySelector('#status').textContent === 'Motor bajo demanda'")
    assert page.locator("#attachButton").is_visible()
    page.locator("#prompt").fill(PROMPT)
    page.locator("#send").click()
    button=page.get_by_role("button",name="↓ PDF",exact=True)
    button.wait_for()
    assert len(posts)==1, posts
    assert "EXPORTACIÓN LOCAL ACTIVA" in posts[0]["messages"][-1]["content"]
    assert "no puedo generar" not in page.locator(".msg.assistant").inner_text()
    with page.expect_download() as dl:
        button.click()
    path=Path(tmp)/"recetas.pdf"; dl.value.save_as(path)
    text=" ".join(x.extract_text() for x in PdfReader(path).pages)
    assert "Recetario" in text and "Pollo al horno" in text and "no puedo" not in text
    assert len(posts)==1
    # Word / Excel are real, readable Office packages. No additional inference on download.
    page.locator("#prompt").fill("Armá un documento Word y una planilla Excel")
    page.locator("#send").click()
    for label,ext in [("Word","docx"),("Excel","xlsx")]:
        button=page.get_by_role("button",name="↓ "+label,exact=True)
        button.wait_for()
        with page.expect_download() as dl:
            button.click()
        path=Path(tmp)/("tabla."+ext); dl.value.save_as(path)
        if ext=="docx": assert "Tabla" in "\n".join(x.text for x in Document(path).paragraphs)
        else: assert load_workbook(path).active["B2"].value==12
    assert len(posts)==2
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    browser.close()
    print("PASS: mobile Chromium, PDF intent and disclaimer, actual PDF/DOCX/XLSX downloads, independent parsers, no extra inference")
