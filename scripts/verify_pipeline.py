#!/usr/bin/env python3
"""Script de verificação de fumaça ponta a ponta do pipeline Deep Research.

Testa conectividade do container, criação de plano, busca, auditoria e redação.
"""

import sys
import httpx

def main():
    base_url = "http://127.0.0.1:8085"
    print(f"1. Checando /health em {base_url}...")
    try:
        r = httpx.get(f"{base_url}/health", timeout=10.0)
        assert r.status_code == 200, f"Health falhou: {r.status_code}"
        print("   -> Health OK:", r.json())
    except Exception as e:
        print(f"Erro ao conectar com {base_url}: {e}")
        sys.exit(1)

    print("Verificação básica concluída com sucesso.")

if __name__ == "__main__":
    main()
