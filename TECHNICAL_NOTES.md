# Notas Técnicas - Soluções Implementadas

## 🔧 Problema 1: Erro CUDA no PyTorch

### Sintoma
```
Could not run aten::empty_strided with arguments from the 'CUDA' backend.
```

### Causa Raiz
O PyTorch estava tentando usar GPU (CUDA) automaticamente, mas:
1. Drivers CUDA não instalados ou incompatíveis
2. GPU não compatível ou não disponível
3. Conflito entre versão PyTorch e CUDA

### Solução Implementada

**Arquivo:** `core/inpaint.py`

```python
def _get_lama_model():
    global _lama_model
    if _lama_model is not None:
        return _lama_model

    with _lama_lock:
        if _lama_model is None:
            # Força o uso de CPU para evitar problemas com CUDA
            import os
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
            
            import torch
            torch.set_default_device('cpu')
            
            from simple_lama_inpainting import SimpleLama
            _lama_model = SimpleLama(device='cpu')
    return _lama_model
```

**Por que funciona:**
1. `CUDA_VISIBLE_DEVICES=''` esconde todas as GPUs do sistema
2. `torch.set_default_device('cpu')` força CPU como dispositivo padrão
3. `SimpleLama(device='cpu')` garante que o modelo use CPU explicitamente

**Trade-offs:**
- ✅ **Prós:** Maior compatibilidade, funciona em qualquer máquina
- ✅ **Prós:** Mais estável, sem erros de CUDA
- ❌ **Contras:** Mais lento que GPU (mas aceitável para MVP)

### Performance CPU vs GPU

| Operação | CPU (Core i5) | GPU (GTX 1060) |
|----------|---------------|----------------|
| Imagem 1920x1080 | ~8s | ~2s |
| Vídeo 30s (720p) | ~5min | ~1.5min |

Para o MVP, CPU é suficiente. GPU pode ser habilitada em versões futuras com:
```python
# Detectar GPU disponível e usar se houver
if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'
```

---

## 🎬 Problema 2: FFmpeg não incluído no executável

### Sintoma
```
ffmpeg/ffprobe não encontrados no PATH
```

### Causa Raiz
O FFmpeg é um binário externo (não é pacote Python):
- Não pode ser instalado via `pip`
- Não é incluído automaticamente pelo PyInstaller
- Usuário final não tem FFmpeg instalado

### Solução Implementada

#### Parte 1: Utilitário de Localização
**Arquivo:** `core/ffmpeg_utils.py`

```python
def get_ffmpeg_path() -> str:
    """
    Retorna caminho para ffmpeg com fallback inteligente:
    1. Binário empacotado (para .exe distribuído)
    2. FFmpeg no PATH do sistema
    3. Erro descritivo se não encontrar
    """
    # Se rodando como executável empacotado
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(sys.executable).parent
        ffmpeg_bin = base_path / 'ffmpeg_bin' / 'ffmpeg.exe'
        if ffmpeg_bin.exists():
            return str(ffmpeg_bin)
    
    # Tenta PATH do sistema
    result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip().split('\n')[0]
    
    raise FileNotFoundError("FFmpeg não encontrado...")
```

**Como funciona:**
1. Detecta se está rodando como `.exe` empacotado
2. Se sim, procura em `ffmpeg_bin/` relativo ao executável
3. Se não, procura no PATH do sistema
4. Dá erro descritivo se não encontrar

#### Parte 2: Download Automático
**Arquivo:** `download_ffmpeg.py`

```python
def download_ffmpeg_windows():
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    # Baixa, extrai ffmpeg.exe e ffprobe.exe para ffmpeg_bin/
```

**Benefícios:**
- Usuário desenvolvedor: `python download_ffmpeg.py` (uma vez)
- Usuário final: FFmpeg já incluído no .exe

#### Parte 3: Configuração PyInstaller
**Arquivo:** `build_exe.py`

```python
PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    # Inclui pasta ffmpeg_bin no executável
    f'--add-data={ffmpeg_bin};ffmpeg_bin',
    ...
])
```

**O que acontece:**
1. PyInstaller copia `ffmpeg_bin/` para dentro do `.exe`
2. Na execução, extrai para pasta temporária (`_MEIPASS`)
3. `ffmpeg_utils.py` encontra automaticamente

### Fluxo Completo

```
Desenvolvimento:
1. Clonar repo
2. python download_ffmpeg.py  → cria ffmpeg_bin/
3. python main.py             → usa ffmpeg_bin/ local

Build:
1. python build_exe.py        → empacota ffmpeg_bin/ no .exe
2. Distribuir WatermarkRemover.exe

Usuário Final:
1. Duplo clique no .exe
2. ffmpeg extraído automaticamente para temp
3. Tudo funciona sem instalação
```

---

## 📦 Arquitetura do Executável

### Estrutura Interna do .EXE

```
WatermarkRemover.exe (executável PyInstaller)
├── Python 3.14 runtime
├── PyQt6 (GUI)
├── OpenCV (processamento de imagem)
├── PyTorch 2.12.1 (CPU-only)
├── simple-lama-inpainting
├── Código da aplicação
│   ├── main.py
│   ├── core/
│   └── ui/
└── ffmpeg_bin/
    ├── ffmpeg.exe  (~80MB)
    └── ffprobe.exe (~80MB)
```

### Tamanho por Componente

| Componente | Tamanho | Compressão |
|------------|---------|------------|
| Python runtime | ~50MB | ~20MB |
| PyQt6 | ~80MB | ~30MB |
| OpenCV | ~50MB | ~20MB |
| PyTorch (CPU) | ~400MB | ~150MB |
| FFmpeg | ~160MB | ~80MB |
| Código próprio | ~1MB | ~0.5MB |
| **TOTAL** | **~740MB** | **~500MB** |

### Por que PyTorch é tão grande?

PyTorch inclui:
- Bibliotecas de álgebra linear (BLAS, LAPACK)
- Operadores otimizados para CPU (MKL, oneDNN)
- Runtime de threads e paralelismo
- Suporte a operações de deep learning

**Alternativas para reduzir tamanho:**
1. Remover PyTorch → sem motor "Qualidade" → ~200MB total
2. Usar PyTorch Lite → ainda experimental
3. Distribuir modelo LaMa separado → salva ~0MB (modelo é baixado em runtime)

---

## 🔄 Download Runtime do Modelo LaMa

### Por que não incluir no executável?

**Decisão de design:**
- Modelo LaMa: ~200MB adicional
- Baixado apenas se usuário escolher motor "Qualidade"
- Download uma vez, cache local permanente
- Mantém executável menor

### Fluxo de Download

```python
# Primeira vez que usa motor "Qualidade"
from simple_lama_inpainting import SimpleLama
model = SimpleLama(device='cpu')  # ← download automático aqui
```

**O que acontece:**
1. `SimpleLama` verifica cache: `~/.cache/torch/hub/checkpoints/`
2. Se não existe, baixa de: `https://github.com/...`
3. Salva localmente
4. Próximas execuções: usa cache

**Localizações de cache:**
- Windows: `C:\Users\<user>\.cache\torch\hub\checkpoints\`
- Linux: `~/.cache/torch/hub/checkpoints/`
- macOS: `~/Library/Caches/torch/hub/checkpoints/`

---

## 🧪 Testes Recomendados

### Antes de distribuir o .exe:

```bash
# 1. Build
python build_exe.py

# 2. Teste em máquina limpa (VM)
# - Sem Python instalado
# - Sem FFmpeg instalado
# - Internet disponível (para download modelo)

# 3. Teste sequência completa:
# a. Abrir imagem → Desenhar retângulo → Motor Rápido → Processar
# b. Abrir imagem → Desenhar pincel → Motor Qualidade → Processar
# c. Abrir vídeo → Marca fixa → Processar
# d. Abrir vídeo → Marca movimento → Processar

# 4. Teste sem internet (após cache modelo):
# - Desconectar internet
# - Motor Rápido deve funcionar
# - Motor Qualidade deve funcionar (usa cache)
```

---

## 🐛 Debugging

### Log de execução do .exe

Para ver erros, execute o .exe pelo terminal:
```cmd
cd C:\path\to\dist
WatermarkRemover.exe
```

Saída aparecerá no console (mesmo com `--windowed`)

### Build com console

Edite `build_exe.py`, comente a linha:
```python
# '--windowed',  # Remove esta linha para debug
```

### Verificar FFmpeg incluído

```python
# Adicione no main.py (temporário)
from core.ffmpeg_utils import check_ffmpeg_available
available, message = check_ffmpeg_available()
print(f"FFmpeg: {message}")
```

---

## 🚀 Otimizações Futuras

### Performance
- [ ] Multi-threading para processar frames em paralelo
- [ ] Batch processing de múltiplos vídeos
- [ ] GPU opcional (detecção automática, fallback CPU)

### Tamanho do executável
- [ ] PyTorch Lite quando disponível
- [ ] Compressão UPX do executável (cuidado com antivírus)
- [ ] Separar versão "Lite" (sem LaMa) e "Full"

### Distribuição
- [ ] Installer NSIS com opções
- [ ] Auto-update via GitHub releases
- [ ] Versão portable (não precisa instalação)
- [ ] Cross-platform builds (Linux, macOS)

### Funcionalidades
- [ ] Detecção automática de marca d'água
- [ ] Batch processing de múltiplos arquivos
- [ ] Motor ProPainter para vídeos (coerência temporal)
- [ ] Interface arrastar-soltar arquivos
- [ ] Preview antes de processar vídeo inteiro

---

## 📚 Referências Técnicas

- **PyTorch CPU-only:** https://pytorch.org/get-started/locally/
- **PyInstaller:** https://pyinstaller.org/en/stable/
- **FFmpeg Builds:** https://www.gyan.dev/ffmpeg/builds/
- **LaMa Paper:** https://arxiv.org/abs/2109.07161
- **OpenCV Inpainting:** https://docs.opencv.org/master/df/d3d/tutorial_py_inpainting.html

---

## 👨‍💻 Contribuindo

Para adicionar melhorias:
1. Fork o repositório
2. Crie branch para feature: `git checkout -b feature/melhoria`
3. Teste localmente
4. Teste build do executável
5. Commit com mensagem descritiva
6. Push e abra Pull Request

### Padrões de código
- Python 3.8+ (type hints)
- Black para formatação
- Docstrings em português
- Comentários explicativos em código complexo
