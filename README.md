# Removedor de Marca D'água — MVP

Protótipo desktop: remoção de marca d'água em **imagens estáticas e vídeos**, com dois modos
para vídeo (**fixa** ou **em movimento**), seleção manual de região (retângulo ou pincel livre)
e dois motores de inpainting: um rápido (OpenCV) e um de qualidade real (LaMa, deep learning).

## Instalação

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> A instalação do motor LaMa inclui PyTorch como dependência — o download pode demorar alguns
> minutos dependendo da sua internet. Se você só quer testar o motor rápido (OpenCV) por
> enquanto, pode remover a linha `simple-lama-inpainting` do `requirements.txt` antes de instalar.

**Para processar vídeos, você também precisa do `ffmpeg` instalado e disponível no PATH**
(usado para checar/remuxar o áudio original de volta no vídeo final):
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: baixe em https://ffmpeg.org/download.html e adicione ao PATH

## Uso — Imagem

1. Clique em **Abrir Imagem ou Vídeo** e selecione um PNG/JPG.
2. Escolha o modo de seleção (**Retângulo** ou **Pincel livre**) e desenhe sobre a marca d'água.
3. Escolha o **motor** (veja detalhes abaixo).
4. Clique em **Processar**. O resultado substitui o preview.
5. Clique em **Salvar Resultado** para exportar o arquivo final.

## Uso — Vídeo

1. Clique em **Abrir Imagem ou Vídeo** e selecione um MP4/MOV/AVI/MKV. O app carrega o
   **primeiro frame** para você marcar a região da marca d'água.
2. Escolha o comportamento da marca:
   - **Fixa**: a região marcada é removida na mesma posição em **todos** os frames.
     Aceita retângulo ou pincel livre.
   - **Em movimento**: você desenha um **retângulo** ao redor da marca no primeiro frame,
     e um tracker de visão computacional acompanha automaticamente a posição dela pelo
     resto do vídeo, reposicionando a remoção a cada frame. Só aceita retângulo (é a
     região inicial que o tracker usa como referência).
3. Escolha o motor e clique em **Processar**. Você escolhe o arquivo de saída (`.mp4`)
   **antes** do processamento começar.
4. Uma barra de progresso mostra o andamento frame a frame; dá pra **cancelar** a qualquer
   momento (o app não deixa um arquivo de saída incompleto para trás).
5. O áudio original é preservado automaticamente no vídeo final, se houver.

> Motor **Qualidade (LaMa)** em vídeo processa frame a frame — em CPU pode ficar bem lento
> para vídeos longos. O app avisa e pede confirmação antes de iniciar nesse caso. Para vídeo,
> o motor **Rápido** costuma ser a escolha mais prática no dia a dia; use o LaMa quando o fundo
> for muito complexo e a qualidade valer a espera extra.

### Sobre o modo "Em movimento" — limitações importantes

- **Não há detecção automática da marca** — você ainda precisa indicar onde ela está no
  primeiro frame. O que esse modo automatiza é o *rastreamento* da posição pelos frames
  seguintes, não a detecção inicial.
- O tracker (algoritmo `MIL` do OpenCV por padrão) funciona bem para marcas que se deslocam
  de forma relativamente suave e contínua sobre um fundo com contraste razoável. Ele pode
  perder a marca em cortes de cena abruptos, movimentos muito rápidos, ou quando a marca
  fica pouco visível (baixo contraste com o fundo) — nesses casos o app **não trava**: ele
  reaproveita a última posição conhecida e continua, mas o resultado nesses trechos deve ser
  revisado com atenção.
- Se você tiver `opencv-contrib-python` instalado (em vez do `opencv-python` padrão deste
  projeto), o app detecta automaticamente e usa o tracker **CSRT**, mais preciso que o MIL —
  mas isso é opcional, não é uma dependência exigida.
- **Sempre revise o vídeo processado** antes de considerá-lo pronto, especialmente em cenas
  visualmente complexas (bordas nítidas, mudanças de cena, texturas).

## Motores de inpainting

- **Rápido (Telea)** / **Rápido (Navier-Stokes)** — instantâneo, funciona bem em fundos lisos.
- **Qualidade (LaMa)** — muito melhor em fundos complexos/texturizados, porém mais lento.
  Na primeira vez que você usa esse motor, o app baixa automaticamente o checkpoint
  (~200MB) e o guarda em cache (`~/.cache/torch/hub/checkpoints`); é necessário ter
  internet nesse primeiro uso. Chamadas seguintes reaproveitam o modelo já carregado.
  Detecta e usa GPU (CUDA) automaticamente se disponível.

## Estrutura do projeto

```
watermark_remover/
├── main.py                # ponto de entrada
├── core/
│   ├── inpaint.py         # motores de inpainting: OpenCV (rápido) e LaMa (qualidade)
│   └── video.py           # leitura/escrita de vídeo, marca fixa e em movimento (tracking),
│                           #   remux de áudio via ffmpeg
├── ui/
│   ├── main_window.py     # janela principal, lógica da aplicação e workers (imagem e vídeo)
│   └── canvas.py          # widget de desenho de máscara sobre a imagem/frame
└── requirements.txt
```

## Como funciona o processamento de vídeo

- O vídeo é lido frame a frame com OpenCV (`cv2.VideoCapture`) — não escreve todos os frames
  em disco, então funciona bem mesmo com vídeos longos sem estourar espaço em disco.
- **Marca fixa**: a mesma máscara desenhada no primeiro frame é aplicada em cada frame lido.
- **Marca em movimento**: a região marcada no primeiro frame inicializa um tracker (`cv2.Tracker`);
  a cada frame seguinte, a posição rastreada é usada pra gerar a máscara daquele frame
  (com uma pequena margem extra ao redor, configurável em `core/video.py`).
- Os frames processados são escritos direto num vídeo temporário via `cv2.VideoWriter`.
- Se o vídeo original tinha áudio, o `ffmpeg` remuxa (copia, sem recodificar) esse áudio para
  dentro do vídeo processado, gerando o arquivo final na resolução/duração originais.
- O processamento roda numa thread separada (`QThread`) — a janela não trava, e dá pra cancelar.

## O que falta para as próximas fases (ver PRD)

- **Detecção automática** da marca (sem seleção manual do frame inicial) e **processamento em
  lote** (múltiplos arquivos de uma vez).
- Trocar o LaMa (que só olha um frame por vez) por um motor de vídeo com coerência temporal,
  como o **ProPainter**, especialmente relevante pro modo "em movimento" — hoje, aplicar o LaMa
  frame a frame pode gerar pequenas inconsistências visuais entre frames consecutivos por não
  levar em conta os frames vizinhos.
- Tracker mais robusto (ex: usar `opencv-contrib-python` com CSRT como dependência padrão, ou
  um tracker baseado em deep learning) pra lidar melhor com cortes de cena e perda de contraste.
- Empacotamento com PyInstaller/Nuitka para gerar executável standalone por SO — atenção: como
  o checkpoint do LaMa é baixado em tempo de execução (não embutido no instalador), isso mantém
  o instalador leve, mas exige internet no primeiro uso em cada máquina.

## Notas técnicas

- O motor **Telea** costuma dar resultados mais suaves; **Navier-Stokes** pode preservar melhor
  bordas retas. Vale testar os dois em fundos diferentes.
- Em fundos muito texturizados ou com padrões repetitivos (ou em bordas de cenas com cores
  muito contrastantes), o resultado do OpenCV pode deixar um resíduo visível — é exatamente
  o tipo de caso onde o **LaMa** faz diferença real.
- Se quiser trocar a fonte do checkpoint do LaMa (ex: um mirror próprio), defina a variável de
  ambiente `LAMA_MODEL_URL` antes de rodar o app.
- O vídeo de saída é sempre `.mp4` (codec `mp4v` para o vídeo silencioso + `aac` para o áudio
  remuxado). Se precisar de outro container/codec, ajuste `core/video.py`.
