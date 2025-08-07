import argparse
import os

from aurora_runner.core.config_loader import load_config
from aurora_runner.core.proxy_manager import ProxyManager
from aurora_runner.core.runner import run_config
from aurora_runner.utils.logger import setup_logger


logger = setup_logger("aurora.main")


def parse_args():
    p = argparse.ArgumentParser(description="Aurora Runner - Ethical HTTP Automation")
    p.add_argument("--config", required=True, help="Caminho para arquivo YAML de configuração")
    p.add_argument("--concurrency", type=int, default=1, help="Número de threads (reservado para execuções com dataset)")
    p.add_argument("--proxies", help="Arquivo com lista de proxies (opcional)")
    return p.parse_args()


def main():
    args = parse_args()

    config_path = os.path.abspath(args.config)
    config = load_config(config_path)

    proxy_mgr = ProxyManager.from_file(args.proxies) if args.proxies else None

    logger.info(f"Iniciando: {config.name}")
    run_config(config, concurrency=args.concurrency, proxies=proxy_mgr)
    logger.info("Concluído com sucesso.")


if __name__ == "__main__":
    main()