"""
Script para baixar FFmpeg automaticamente para Windows.
Execute: python download_ffmpeg.py
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path


def download_ffmpeg_windows():
    """
    Baixa uma build essentials do FFmpeg para Windows e extrai na pasta ffmpeg_bin/
    """
    print("Baixando FFmpeg para Windows...")
    
    # URL da build essentials (mais leve, ~80MB)
    # Para versão full, use: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-full.7z
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    
    output_dir = Path(__file__).parent / "ffmpeg_bin"
    output_dir.mkdir(exist_ok=True)
    
    zip_path = output_dir / "ffmpeg.zip"
    
    # Download com barra de progresso
    def download_progress(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownload: {percent}%")
        sys.stdout.flush()
    
    try:
        print(f"Baixando de {url}")
        urllib.request.urlretrieve(url, zip_path, download_progress)
        print("\n✓ Download concluído!")
        
        print("Extraindo arquivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Lista todos os arquivos
            for file_info in zip_ref.filelist:
                # Extrai apenas ffmpeg.exe e ffprobe.exe da pasta bin/
                if file_info.filename.endswith(('ffmpeg.exe', 'ffprobe.exe')):
                    file_info.filename = os.path.basename(file_info.filename)
                    zip_ref.extract(file_info, output_dir)
        
        print("✓ FFmpeg extraído com sucesso!")
        
        # Limpa o arquivo zip
        zip_path.unlink()
        
        # Verifica se os executáveis foram criados
        ffmpeg_exe = output_dir / "ffmpeg.exe"
        ffprobe_exe = output_dir / "ffprobe.exe"
        
        if ffmpeg_exe.exists() and ffprobe_exe.exists():
            print(f"\n✓ FFmpeg instalado em: {output_dir}")
            print(f"  - ffmpeg.exe: {ffmpeg_exe}")
            print(f"  - ffprobe.exe: {ffprobe_exe}")
            return True
        else:
            print("✗ Erro: Não foi possível encontrar os executáveis após extração")
            return False
            
    except Exception as e:
        print(f"\n✗ Erro ao baixar FFmpeg: {e}")
        if zip_path.exists():
            zip_path.unlink()
        return False


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Este script é apenas para Windows.")
        print("Em Linux/Mac, instale via gerenciador de pacotes:")
        print("  - Ubuntu/Debian: sudo apt install ffmpeg")
        print("  - macOS: brew install ffmpeg")
        sys.exit(1)
    
    success = download_ffmpeg_windows()
    sys.exit(0 if success else 1)
