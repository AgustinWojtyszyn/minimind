"""One real streaming request, measuring client-visible latency; no automatic retries."""
import argparse
import json
import subprocess
import time

URL = "https://boitia-ai.agustinwojtyszyn.com/api/boitia/v1/chat/completions"
ORIGIN = "https://agustinwojtyszyn.github.io"


def measure(lines, started, clock=time.perf_counter):
    pieces, first, finish, done = [], None, None, False
    for line in lines:
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            done = True
            break
        data = json.loads(payload)
        if data.get("error"):
            raise RuntimeError(data["error"].get("message", "Error del motor"))
        choice = (data.get("choices") or [{}])[0]
        content = choice.get("delta", {}).get("content")
        if isinstance(content, str):
            if first is None and content.strip():
                first = clock() - started
            pieces.append(content)
        if choice.get("finish_reason"):
            finish = choice["finish_reason"]
    if not done or finish not in ("stop", "length") or first is None:
        raise RuntimeError("No se recibió un stream completo con texto visible.")
    total = clock() - started
    answer = "".join(pieces)
    return {"primer_texto_s": round(first, 3), "total_s": round(total, 3),
            "palabras": len(answer.split()), "caracteres": len(answer),
            "finalizacion": finish, "respuesta": answer}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", default="¿Qué me puedo hacer de comer?")
    parser.add_argument("--mode", choices=["fast", "balanced", "deep"], default="fast")
    args = parser.parse_args()
    body = json.dumps({"model": "boitia", "messages": [{"role": "user", "content": args.prompt}],
                       "mode": args.mode, "stream": True}, ensure_ascii=False)
    cmd = ["curl", "-N", "-fsS", "--max-time", "180", "-X", "POST", URL,
           "-H", "Origin: " + ORIGIN, "-H", "Content-Type: application/json", "-d", body]
    started = time.perf_counter()
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as proc:
        try:
            metrics = measure(proc.stdout, started)
        except Exception:
            proc.terminate()
            raise
        if proc.wait() != 0:
            raise SystemExit("La prueba HTTP no finalizó correctamente.")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
