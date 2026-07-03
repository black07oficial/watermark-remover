"""
Script para criar o executável do Watermark Remover usando PyInstaller.

Uso:
    1. Instale PyInstaller: pip install pyinstaller
    2. Baixe FFmpeg: python download_ffmpeg.py
    3. Execute: python build_exe.py
"""

import PyInstaller.__main__
import sys
from pathlib import Path

def build_executable():
    """
    Cria o executável standalone do Watermark Remover.
    """
    project_dir = Path(__file__).parent
    
    # Verifica se FFmpeg foi baixado
    ffmpeg_bin = project_dir / "ffmpeg_bin"
    if not (ffmpeg_bin / "ffmpeg.exe").exists():
        print("✗ FFmpeg não encontrado!")
        print("Execute primeiro: python download_ffmpeg.py")
        return False
    
    print("Criando executável...")
    
    PyInstaller.__main__.run([
        'main.py',                          # Script principal
        '--name=WatermarkRemover',          # Nome do executável
        '--windowed',                        # Sem console (apenas GUI)
        '--onefile',                         # Executável único
        '--icon=NONE',                       # Adicione um ícone .ico se tiver
        
        # Inclui a pasta ffmpeg_bin no executável
        f'--add-data={ffmpeg_bin};ffmpeg_bin',
        
        # Hidden imports necessários para PyTorch/LaMa
        '--hidden-import=torch',
        '--hidden-import=torchvision',
        '--hidden-import=simple_lama_inpainting',
        '--hidden-import=PIL',
        '--hidden-import=cv2',
        
        # Coleta todos os submódulos necessários
        '--collect-all=torch',
        '--collect-all=torchvision',
        '--collect-all=simple_lama_inpainting',
        
        # Otimizações
        '--clean',                           # Limpa cache antes de buildar
        '--noconfirm',                       # Não pede confirmação
        
        # Pasta de saída
        '--distpath=dist',
        '--workpath=build',
        '--specpath=.',
    ])
    
    print("\n✓ Executável criado com sucesso!")
    print(f"📦 Localização: {project_dir / 'dist' / 'WatermarkRemover.exe'}")
    print("\nObservação: O modelo LaMa (~200MB) será baixado na primeira execução")
    print("quando o usuário selecionar o motor 'Qualidade'.")
    
    return True


if __name__ == "__main__":
    try:
        success = build_executable()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Erro ao criar executável: {e}")
        print("\nCertifique-se de ter instalado: pip install pyinstaller")
        sys.exit(1)
