#!/usr/bin/env python3
"""Script de inicialização da aplicação integrada FastAPI + React (Checkpoint 1).

Garante build do frontend se necessário, instala dependências via npm ci se ausentes,
carrega variáveis de ambiente e inicia o servidor uvicorn com entrega vinculada a 127.0.0.1 por padrão.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def load_dotenv(dotenv_path: Path) -> None:
    """Carrega variáveis do arquivo .env sem sobrescrever variáveis de ambiente existentes."""
    if not dotenv_path.is_file():
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as exc:
        print(f"[WARN] Falha ao carregar .env: {exc}", file=sys.stderr)


def build_frontend(root_dir: Path, force_clean: bool = False) -> bool:
    """Executa instalação de dependências e compilação de produção do frontend."""
    frontend_dir = root_dir / "frontend"
    if not frontend_dir.is_dir():
        print(f"[ERROR] Diretório frontend não encontrado em {frontend_dir}.", file=sys.stderr)
        return False

    npm_path = shutil.which("npm")
    if not npm_path:
        print("[ERROR] 'npm' não localizado no PATH. Node.js e npm são obrigatórios para compilar o frontend.", file=sys.stderr)
        return False

    dist_dir = frontend_dir / "dist"
    index_html = dist_dir / "index.html"

    # Se limpeza for solicitada (ex: --build), remove o index.html antigo
    # para garantir que uma falha subsequente não mascare o erro com assets legados
    if force_clean and index_html.is_file():
        try:
            index_html.unlink()
        except OSError as exc:
            print(f"[WARN] Não foi possível remover index.html antigo: {exc}", file=sys.stderr)

    # Instala dependências em fresh checkout caso node_modules não exista
    node_modules_dir = frontend_dir / "node_modules"
    if not node_modules_dir.is_dir():
        print("[INFO] Diretório node_modules ausente. Executando 'npm ci'...", file=sys.stderr)
        try:
            subprocess.run(
                [npm_path, "ci"],
                cwd=str(frontend_dir),
                check=True,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
        except subprocess.CalledProcessError as exc:
            print(f"[ERROR] Falha na instalação de dependências ('npm ci', código {exc.returncode}).", file=sys.stderr)
            return False

    print("[INFO] Executando compilação do frontend ('npm run build')...", file=sys.stderr)
    try:
        subprocess.run(
            [npm_path, "run", "build"],
            cwd=str(frontend_dir),
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Falha na compilação do frontend ('npm run build', código {exc.returncode}).", file=sys.stderr)
        return False

    if not index_html.is_file():
        print("[ERROR] A compilação terminou sem erros mas 'frontend/dist/index.html' não foi gerado.", file=sys.stderr)
        return False

    print("[INFO] Build do frontend concluído com sucesso.", file=sys.stderr)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia o Deep Research com frontend integrado.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Endereço de bind do servidor (padrão estrito: 127.0.0.1 para entrega local)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Porta de escuta do servidor HTTP (padrão: 8000)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Força nova compilação do frontend antes de iniciar o servidor",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Habilita auto-reload para desenvolvimento",
    )
    args = parser.parse_args()

    # Garante importação correta da aplicação a partir de qualquer diretório de execução
    root_dir = Path(__file__).resolve().parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    os.chdir(str(root_dir))

    dotenv_path = root_dir / ".env"
    load_dotenv(dotenv_path)

    dist_index = root_dir / "frontend" / "dist" / "index.html"

    if args.build:
        print("[INFO] Flag --build informada: forçando nova compilação do frontend...", file=sys.stderr)
        build_ok = build_frontend(root_dir, force_clean=True)
        if not build_ok:
            print("[ERROR] Compilação forçada do frontend falhou (--build). Abortando inicialização.", file=sys.stderr)
            sys.exit(1)
    elif not dist_index.is_file():
        print("[INFO] Bundle do frontend não encontrado em frontend/dist. Iniciando build automático...", file=sys.stderr)
        build_ok = build_frontend(root_dir, force_clean=False)
        if not build_ok or not dist_index.is_file():
            print("[ERROR] Falha ao compilar bundle inicial do frontend. Abortando inicialização.", file=sys.stderr)
            sys.exit(1)

    print(f"[INFO] Iniciando Deep Research em http://{args.host}:{args.port}")
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
