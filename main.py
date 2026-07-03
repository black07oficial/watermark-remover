"""
Ponto de entrada do MVP — Removedor de Marca D'água.

Uso:
    python main.py
    
Logs são salvos em: %USERPROFILE%\watermark_remover.log
"""

import sys
import logging

# Configura logging ANTES de qualquer import
from logger_setup import setup_logger, setup_exception_hook, log_imports

logger, log_file = setup_logger()
setup_exception_hook(logger)

logger.info("Importando dependências...")

try:
    from ui.main_window import main
    logger.info("Dependências importadas com sucesso")
    log_imports(logger)
except Exception as e:
    logger.exception("ERRO FATAL ao importar dependências:")
    sys.exit(1)

if __name__ == "__main__":
    try:
        logger.info("Iniciando interface gráfica...")
        main()
    except Exception as e:
        logger.exception("ERRO FATAL na execução:")
        sys.exit(1)
    finally:
        logger.info("Aplicação encerrada")
        print(f"\n{'='*80}")
        print(f"Logs salvos em: {log_file}")
        print(f"{'='*80}\n")
