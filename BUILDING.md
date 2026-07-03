# Guia de Construção do Executável

## Pré-requisitos

- Python 3.8 ou superior
- Todas as dependências instaladas: `pip install -r requirements.txt`
- PyInstaller: `pip install pyinstaller`

## Passos para criar o executável

### 1. Baixar FFmpeg (obrigatório)

O FFmpeg é necessário para processamento de vídeos e será incluído no executável.

```bash
python download_ffmpeg.py
```

Este comando baixa automaticamente o FFmpeg essentials (~80MB) e extrai os executáveis
necessários (`ffmpeg.exe` e `ffprobe.exe`) na pasta `ffmpeg_bin/`.

### 2. Criar o executável

```bash
python build_exe.py
```

O script `build_exe.py` usa PyInstaller para criar um executável standalone que inclui:
- Todas as bibliotecas Python necessárias
- PyQt6 (interface gráfica)
- OpenCV (processamento de imagem/vídeo)
- PyTorch (motor de deep learning para o LaMa)
- FFmpeg (processamento de áudio em vídeos)

### 3. Localização do executável

O executável final estará em:
```
dist/WatermarkRemover.exe
```

Tamanho aproximado: ~500MB (devido ao PyTorch incluído)

## Distribuição

O executável `WatermarkRemover.exe` pode ser distribuído sozinho - não precisa de nenhum
arquivo adicional.

**Importante:**
- O usuário NÃO precisa instalar Python
- O usuário NÃO precisa instalar FFmpeg
- O usuário NÃO precisa instalar nenhuma dependência
- O modelo LaMa (~200MB) será baixado automaticamente na primeira vez que o motor
  "Qualidade" for usado (requer internet apenas nesse primeiro uso)

## Resolução de Problemas

### Erro: "FFmpeg não encontrado"
Execute `python download_ffmpeg.py` antes de rodar `build_exe.py`.

### Erro durante build com PyInstaller
Certifique-se de que todas as dependências estão instaladas:
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### Executável muito grande
O tamanho é normal devido ao PyTorch (~400MB compactado). Para reduzir:
- Considere criar uma versão "lite" sem o motor LaMa (remova torch do requirements)
- Use PyTorch CPU-only (já configurado por padrão neste projeto)

### Erro ao executar o .exe: "Não foi possível carregar o modelo LaMa"
O modelo LaMa é baixado na primeira execução e requer internet. Após o download,
ele fica em cache e não precisa mais de internet:
- Windows: `C:\Users\<usuario>\.cache\torch\hub\checkpoints`

## Configurações Avançadas

### Adicionar ícone personalizado

Edite `build_exe.py` e altere a linha:
```python
'--icon=NONE',  # Mude para '--icon=icone.ico'
```

### Criar executável com console (para debug)

Remova ou comente a linha em `build_exe.py`:
```python
# '--windowed',  # Comentar para mostrar console
```

### Build para outras plataformas

O processo é similar em Linux/macOS:
1. Instale FFmpeg via gerenciador de pacotes
2. Execute `python build_exe.py`
3. Ajuste os caminhos no script se necessário

## Performance

### Tempo de inicialização
- Primeira execução: ~10-15 segundos (carregamento do PyTorch)
- Execuções seguintes: ~5-10 segundos

### Uso de memória
- Modo "Rápido" (OpenCV): ~200MB RAM
- Modo "Qualidade" (LaMa): ~1-2GB RAM

### CPU vs GPU
Por padrão, o executável usa apenas CPU para evitar problemas de compatibilidade
com drivers CUDA. Para habilitar GPU:

1. O usuário deve ter CUDA instalado e configurado
2. Edite `core/inpaint.py` e remova as linhas:
```python
os.environ['CUDA_VISIBLE_DEVICES'] = ''
torch.set_default_device('cpu')
```
3. Reconstrua o executável

**Nota**: GPU só acelera o motor "Qualidade" (LaMa). O motor "Rápido" sempre usa CPU.
