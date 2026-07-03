"""
Sistema de logging para capturar erros do aplicativo.
Logs são salvos em watermark_remover.log na pasta do usuário.
"""

import logging
import sys
from pathlib import Path


def setup_logger():
    """
    Configura o sistema de logging para capturar todos os erros.
    Logs vão para arquivo E para console.
    """
    # Arquivo de log na pasta do usuário
    log_file = Path.home() / "watermark_remover.log"
    
    # Configuração do logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger('WatermarkRemover')
    logger.info("=" * 80)
    logger.info("WATERMARK REMOVER - Iniciando aplicação")
    logger.info(f"Arquivo de log: {log_file}")
    logger.info(f"Python: {sys.version}")
    logger.info("=" * 80)
    
    return logger, log_file


def setup_exception_hook(logger):
    """
    Configura hook para capturar exceções não tratadas.
    """
    def exception_hook(exctype, value, tb):
        import traceback
        logger.error("=" * 80)
        logger.error("EXCEÇÃO NÃO TRATADA!")
        logger.error("=" * 80)
        logger.error(f"Tipo: {exctype.__name__}")
        logger.error(f"Valor: {value}")
        logger.error("Traceback:")
        for line in traceback.format_tb(tb):
            logger.error(line.rstrip())
        logger.error("=" * 80)
        
        # Chama o hook padrão também
        sys.__excepthook__(exctype, value, tb)
    
    sys.excepthook = exception_hook


def log_imports(logger):
    """
    Loga as versões das bibliotecas principais.
    """
    try:
        import cv2
        logger.info(f"OpenCV: {cv2.__version__}")
    except Exception as e:
        logger.error(f"Erro ao importar OpenCV: {e}")
    
    try:
        import numpy as np
        logger.info(f"NumPy: {np.__version__}")
    except Exception as e:
        logger.error(f"Erro ao importar NumPy: {e}")
    
    try:
        import torch
        logger.info(f"PyTorch: {torch.__version__}")
        logger.info(f"CUDA disponível: {torch.cuda.is_available()}")
    except Exception as e:
        logger.error(f"Erro ao importar PyTorch: {e}")
    
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        logger.info(f"PyQt6: {QT_VERSION_STR}")
    except Exception as e:
        logger.error(f"Erro ao importar PyQt6: {e}")
