"""Exercise the isolated real FastAPI service over HTTP; never live providers."""

import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8011"
HEADERS = {"Content-Type": "application/json", "X-API-Key": "frontend-contract-key"}


def post(endpoint, payload):
    request = urllib.request.Request(
        BASE + "/api/v1/" + endpoint,
        data=json.dumps(payload).encode(),
        headers=HEADERS,
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.status, json.load(response), round(time.monotonic() - started, 3)


if __name__ == "__main__":
    evidence = {"mode": "real_fastapi_http_with_mocked_providers_and_isolated_sqlite", "steps": []}
    code, plan, elapsed = post("plan", {"tema": "Transição Energética Global", "async_execute": False})
    assert code == 201 and plan["pontos"] and plan["status_pipeline"] == "planejado"
    research_id = plan["id_pesquisa"]
    evidence["steps"].append({"endpoint": "plan", "http": code, "point_count": plan["n_pontos"], "elapsed_s": elapsed})
    code, search, elapsed = post("search", {"id_pesquisa": research_id})
    assert code == 200 and search["total_falhas_coleta"] == 0
    evidence["steps"].append({"endpoint": "search", "http": code, "processed": search["total_pontos_processados"], "elapsed_s": elapsed})
    code, audit, elapsed = post("audit", {"id_pesquisa": research_id})
    assert code == 200 and audit["pronto_para_writer"] is True
    evidence["steps"].append({"endpoint": "audit", "http": code, "ready_for_writer": audit["pronto_para_writer"], "elapsed_s": elapsed})
    code, writer, elapsed = post("writer", {"id_pesquisa": research_id})
    assert code == 200 and writer["status"] == "concluido" and writer["dossier_final"]
    assert writer.get("reasoning_dossier") is None
    evidence["steps"].append({"endpoint": "writer", "http": code, "status": writer["status"], "report_characters": len(writer["dossier_final"]), "private_reasoning_absent": True, "elapsed_s": elapsed})
    evidence["passed"] = True
    output = ROOT / "docs/frontend/evidence/real-fastapi-http.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False))
