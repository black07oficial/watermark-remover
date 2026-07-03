"""
Utilitário para gerenciar o FFmpeg — detecta instalação local ou usa binário empacotado.

Para distribuição com PyInstaller, os binários do FFmpeg devem estar na pasta 'ffmpeg_bin/'
ao lado do executável. O PyInstaller copiará essa pasta automaticamente se configurado.
"""

import os
import sys
import subprocess
from pathlib import Path


def get_ffmpeg_path() -> str:
    """
    Retorna o caminho para o executável ffmpeg.
    
    Ordem de busca:
    1. Binário empacotado junto com o .exe (para distribuição)
    2. FFmpeg no PATH do sistema (instalação do usuário)
    3. Lança exceção se não encontrar
    """
    # Se estiver rodando como executável empacotado pelo PyInstaller
    if getattr(sys, 'frozen', False):
        # Caminho base onde o executável está
        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
        
        # Procura por ffmpeg.exe na pasta ffmpeg_bin
        ffmpeg_bin = base_path / 'ffmpeg_bin' / 'ffmpeg.exe'
        if ffmpeg_bin.exists():
            return str(ffmpeg_bin)
    
    # Tenta encontrar no PATH do sistema
    try:
        result = subprocess.run(
            ['where' if sys.platform == 'win32' else 'which', 'ffmpeg'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            ffmpeg_path = result.stdout.strip().split('\n')[0]
            if os.path.exists(ffmpeg_path):
                return ffmpeg_path
    except Exception:
        pass
    
    raise FileNotFoundError(
        "FFmpeg não encontrado. Para processar vídeos:\n"
        "1. Instale o FFmpeg no sistema (https://ffmpeg.org/download.html)\n"
        "2. Ou coloque ffmpeg.exe na pasta ffmpeg_bin/ junto ao executável"
    )


def get_ffprobe_path() -> str:
    """
    Retorna o caminho para o executável ffprobe.
    Similar ao get_ffmpeg_path().
    """
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
        ffprobe_bin = base_path / 'ffmpeg_bin' / 'ffprobe.exe'
        if ffprobe_bin.exists():
            return str(ffprobe_bin)
    
    try:
        result = subprocess.run(
            ['where' if sys.platform == 'win32' else 'which', 'ffprobe'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            ffprobe_path = result.stdout.strip().split('\n')[0]
            if os.path.exists(ffprobe_path):
                return ffprobe_path
    except Exception:
        pass
    
    raise FileNotFoundError(
        "FFprobe não encontrado. Para processar vídeos:\n"
        "1. Instale o FFmpeg no sistema (https://ffmpeg.org/download.html)\n"
        "2. Ou coloque ffprobe.exe na pasta ffmpeg_bin/ junto ao executável"
    )


def check_ffmpeg_available() -> tuple[bool, str]:
    """
    Verifica se o FFmpeg está disponível.
    
    Returns:
        (disponível: bool, mensagem: str)
    """
    try:
        ffmpeg = get_ffmpeg_path()
        ffprobe = get_ffprobe_path()
        return True, f"FFmpeg encontrado:\n{ffmpeg}\n{ffprobe}"
    except FileNotFoundError as e:
        return False, str(e)
