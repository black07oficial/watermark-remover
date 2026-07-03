# Guia Rápido - Watermark Remover

## 🚀 Início Rápido para Desenvolvedores

### 1. Clonar e instalar
```bash
git clone https://github.com/black07oficial/watermark-remover.git
cd watermark-remover
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Baixar FFmpeg (necessário para vídeos)
```bash
python download_ffmpeg.py
```

### 3. Executar
```bash
python main.py
```

## 📦 Para Distribuição (Criar .EXE)

### 1. Instalar PyInstaller
```bash
pip install pyinstaller
```

### 2. Baixar FFmpeg
```bash
python download_ffmpeg.py
```

### 3. Criar executável
```bash
python build_exe.py
```

✓ Executável estará em: `dist/WatermarkRemover.exe`

## 🎯 Soluções para Problemas Comuns

### ❌ Erro: "Could not run aten::empty_strided with arguments from the CUDA backend"

**Solução implementada:** O código agora força o uso de CPU automaticamente.

**O que foi feito:**
- Modificado `core/inpaint.py` para desabilitar CUDA
- PyTorch agora usa apenas CPU (mais estável)
- GPU não é necessária para este aplicativo

### ❌ FFmpeg não encontrado

**Solução 1 (Recomendada):**
```bash
python download_ffmpeg.py
```

**Solução 2 (Manual):**
- Baixe: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
- Extraia `ffmpeg.exe` e `ffprobe.exe`
- Coloque na pasta `ffmpeg_bin/`

### ❌ Executável não funciona no computador do usuário

**Causas possíveis:**
1. **Modelo LaMa precisa de internet na 1ª vez** - é normal
2. **Antivírus bloqueando** - adicione exceção
3. **Windows 7** - requer atualização KB2533623

## 📋 Checklist Antes de Distribuir

- [ ] Testou o motor "Rápido" com imagens
- [ ] Testou o motor "Qualidade" com imagens (requer internet 1ª vez)
- [ ] Testou processamento de vídeo (marca fixa)
- [ ] Testou processamento de vídeo (marca em movimento)
- [ ] FFmpeg incluído no executável
- [ ] Executável testado em máquina limpa (sem Python instalado)

## 🔧 Configurações de Performance

### Para vídeos longos (>5 minutos)
- Use motor "Rápido" (Telea ou Navier-Stokes)
- Motor "Qualidade" (LaMa) pode levar muito tempo em CPU

### Para melhor qualidade em fundos complexos
- Use motor "Qualidade" (LaMa)
- Primeira execução baixa ~200MB (uma vez só)

### Para reduzir tamanho do executável
- Remova `simple-lama-inpainting` do requirements.txt
- Reconstrua o executável
- Tamanho reduz de ~500MB para ~200MB
- ⚠️ Motor "Qualidade" não estará disponível

## 📊 Especificações

### Requisitos mínimos do executável
- **SO:** Windows 7 SP1 ou superior (64-bit)
- **RAM:** 2GB mínimo, 4GB recomendado
- **Disco:** 500MB para instalação + 300MB para cache do modelo
- **Internet:** Necessária apenas na 1ª vez (download modelo LaMa)

### Funcionalidades incluídas
- ✅ Remoção de marca d'água em imagens (PNG, JPG, BMP)
- ✅ Remoção de marca d'água em vídeos (MP4, AVI, MOV, MKV)
- ✅ Marca fixa (mesma posição em todos os frames)
- ✅ Marca em movimento (rastreamento automático)
- ✅ Dois modos de desenho: Retângulo e Pincel livre
- ✅ Três motores: Rápido (Telea), Rápido (Navier-Stokes), Qualidade (LaMa)
- ✅ Preservação de áudio em vídeos
- ✅ Barra de progresso e cancelamento

## 🐛 Reportar Problemas

Abra uma issue no GitHub com:
1. Descrição do problema
2. Sistema operacional
3. Tipo de arquivo (imagem/vídeo)
4. Motor usado (Rápido/Qualidade)
5. Mensagem de erro (se houver)

## 📚 Documentação Completa

- **README.md** - Visão geral e instruções de uso
- **BUILDING.md** - Detalhes técnicos de construção do executável
- **QUICK_START.md** - Este arquivo (início rápido)

## 🎓 Exemplos de Uso

### Remover logo fixo de vídeo de apresentação
1. Abra o vídeo
2. Desenhe retângulo sobre o logo
3. Selecione "Marca Fixa"
4. Motor: "Rápido (Telea)" para velocidade
5. Processar

### Remover assinatura complexa de foto
1. Abra a imagem
2. Use "Pincel livre" para contornar a assinatura
3. Motor: "Qualidade (LaMa)" para melhor resultado
4. Processar

### Remover marca d'água que se move no vídeo
1. Abra o vídeo
2. Desenhe retângulo ao redor da marca NO PRIMEIRO FRAME
3. Selecione "Marca em Movimento"
4. Motor: "Rápido (Navier-Stokes)"
5. Processar (tracking automático)

## 🔗 Links Úteis

- **Repositório:** https://github.com/black07oficial/watermark-remover
- **FFmpeg:** https://ffmpeg.org/
- **PyInstaller:** https://pyinstaller.org/
- **Issues:** https://github.com/black07oficial/watermark-remover/issues
