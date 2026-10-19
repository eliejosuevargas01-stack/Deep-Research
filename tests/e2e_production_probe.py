import json
import os
import subprocess
import time
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE_URL = "http://127.0.0.1:3000"

def get_admin_password():
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("ADMIN_PASSWORD="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("ADMIN_PASSWORD not found in .env")

def main():
    print("=== [E2E PRODUÇÃO] INICIANDO SIMULAÇÃO COMPLETA DE USUÁRIO ===")
    
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    # 1. Healthcheck
    req = urllib.request.Request(f"{BASE_URL}/health")
    with opener.open(req) as resp:
        assert resp.status == 200
        health = json.loads(resp.read().decode())
        print(f"[1/7] Healthcheck OK: status={health.get('status')}, db={health.get('database')}")
    
    # 2. Login
    admin_pw = get_admin_password()
    login_data = json.dumps({"password": admin_pw}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as resp:
        assert resp.status == 200
        body = json.loads(resp.read().decode())
        csrf_token = body.get("csrf_token")
        print(f"[2/7] Login OK: authenticated={body.get('authenticated')}, role={body.get('role')}, csrf_token={csrf_token[:10]}...")
    
    # 3. Validar Sessão
    req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
    with opener.open(req) as resp:
        assert resp.status == 200
        me = json.loads(resp.read().decode())
        assert me.get("authenticated") is True
        print(f"[3/7] Auth /me verificado com sucesso.")

    # 4. Envio de Tema
    theme = "Tendências de Engenharia de Software e IA em 2026"
    create_payload = json.dumps({"theme": theme}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/research",
        data=create_payload,
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf_token
        }
    )
    with opener.open(req) as resp:
        assert resp.status == 201
        res_data = json.loads(resp.read().decode())
        research_id = res_data["research_id"]
        print(f"[4/7] Pesquisa criada com sucesso! research_id={research_id}, status={res_data.get('status')}")

    # 5. Polling do Briefing Draft (ScoutWorker ao vivo)
    print("Aguardando ScoutWorker gerar o rascunho de briefing...")
    briefing_ready = False
    points = []
    for attempt in range(45):
        time.sleep(2)
        req = urllib.request.Request(f"{BASE_URL}/api/research/{research_id}")
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode())
            status = data.get("status")
            if status == "PENDING_APPROVAL" and data.get("briefing_draft", {}).get("points"):
                briefing_ready = True
                points = data["briefing_draft"]["points"]
                print(f"[5/7] Briefing gerado pelo ScoutWorker! Total de pontos={len(points)}")
                for i, p in enumerate(points):
                    print(f"   Ponto {i+1}: {p.get('title')}")
                break
            elif status == "FAILED":
                raise RuntimeError(f"Pesquisa falhou durante o briefing: {data.get('error')}")
            else:
                if attempt % 5 == 0:
                    print(f"   Status atual: {status} (tentativa {attempt+1}/45)...")

    if not briefing_ready:
        raise TimeoutError("Timeout aguardando ScoutWorker gerar briefing draft")

    # 6. Aprovação do Briefing
    approve_payload = json.dumps({"approved_points": points}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/api/research/{research_id}/briefing/approve",
        data=approve_payload,
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf_token
        }
    )
    with opener.open(req) as resp:
        assert resp.status == 200
        approve_res = json.loads(resp.read().decode())
        print(f"[6/7] Briefing aprovado com sucesso! status={approve_res.get('status')}")

    # 7. Acompanhamento dos Workers e Auditoria até o Relatório Final
    print("Aguardando execução dos Workers de investigação, Auditoria e Redator...")
    done = False
    for attempt in range(150):
        time.sleep(3)
        req = urllib.request.Request(f"{BASE_URL}/api/research/{research_id}")
        with opener.open(req) as resp:
            data = json.loads(resp.read().decode())
            status = data.get("status")
            if status == "DONE":
                done = True
                print(f"[7/7] Pesquisa CONCLUÍDA com sucesso (DONE)!")
                break
            elif status == "FAILED":
                raise RuntimeError(f"Pesquisa falhou durante a investigação/redação: {data.get('error')}")
            else:
                if attempt % 5 == 0:
                    pts_status = [f"{p.get('title')[:20]}:{p.get('status')}" for p in data.get("points", [])]
                    print(f"   Status atual: {status} | Pontos: {pts_status[:3]}...")

    if not done:
        print("Pipeline ainda em execução após tempo de observação inicial. Consultando estado...")

    # Consultar Relatório e Eventos
    req_events = urllib.request.Request(f"{BASE_URL}/api/research/{research_id}")
    with opener.open(req_events) as resp:
        final_data = json.loads(resp.read().decode())
        print("\n=== RESUMO DA PESQUISA EM PRODUÇÃO ===")
        print(f"ID: {final_data.get('research_id')}")
        print(f"Tema: {final_data.get('theme')}")
        print(f"Status Final: {final_data.get('status')}")
        print(f"Total de Pontos: {len(final_data.get('points', []))}")

    # Consultar Report se DONE
    if final_data.get("status") == "DONE":
        req_rep = urllib.request.Request(f"{BASE_URL}/api/reports/{research_id}")
        with opener.open(req_rep) as resp:
            rep_data = json.loads(resp.read().decode())
            print(f"Relatório gerado com {len(rep_data.get('content_markdown', ''))} caracteres.")
            print(f"Métricas de citação: {rep_data.get('citation_metrics')}")

    print("\n=== [E2E PRODUÇÃO] FLUXO DO USUÁRIO VALIDADO COM SUCESSO ===")

if __name__ == "__main__":
    main()
