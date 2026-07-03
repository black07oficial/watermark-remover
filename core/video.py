"""
Processamento de vídeo.

Dois modos suportados:

1) Marca FIXA (process_video): mesma máscara aplicada em todos os frames.

2) Marca em MOVIMENTO (process_video_moving_watermark): o usuário marca a região só no
   primeiro frame; um tracker de visão computacional (OpenCV) acompanha essa região ao
   longo do vídeo, e a máscara é reposicionada frame a frame na posição rastreada antes
   do inpainting. Não há detecção automática da marca (isso é uma fase futura) — o usuário
   ainda precisa indicar onde ela está no primeiro frame, mas não precisa mais marcar frame
   a frame se ela se mover.

Estratégia comum aos dois modos:
  1. Lê o vídeo frame a frame com OpenCV (não escreve todos os frames em disco).
  2. Aplica inpainting em cada frame com a máscara apropriada (fixa ou rastreada).
  3. Escreve os frames processados num vídeo temporário (sem áudio) via cv2.VideoWriter.
  4. Se o vídeo original tiver trilha de áudio, usa ffmpeg para remuxar (copiar, sem recodificar)
     o áudio original para dentro do vídeo processado, gerando o arquivo final.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

import cv2
import numpy as np

from core.inpaint import inpaint_image

BBox = Tuple[int, int, int, int]  # (x, y, largura, altura)


class VideoError(RuntimeError):
    pass


@dataclass
class VideoInfo:
    width: int
    height: int
    fps: float
    frame_count: int
    has_audio: bool


def probe_video(path: str) -> VideoInfo:
    """Lê metadados do vídeo (resolução, fps, nº de frames, se tem áudio)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError(f"Não foi possível abrir o vídeo: {path}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    has_audio = _probe_has_audio(path)

    return VideoInfo(width=width, height=height, fps=fps, frame_count=frame_count, has_audio=has_audio)


def read_first_frame(path: str) -> np.ndarray:
    """Lê apenas o primeiro frame — usado para o usuário desenhar a máscara/região na UI."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError(f"Não foi possível abrir o vídeo: {path}")
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise VideoError("Não foi possível ler o primeiro frame do vídeo.")
    return frame


def _probe_has_audio(path: str) -> bool:
    if not _ffmpeg_available():
        return False
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a",
                "-show_entries", "stream=index", "-of", "csv=p=0", path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ---------------------------------------------------------------------------
# Pipeline comum: lê o vídeo, chama frame_processor(frame, index) pra cada frame,
# escreve o resultado e remuxa áudio no final. Usado tanto pelo modo de marca fixa
# quanto pelo modo de marca em movimento.
# ---------------------------------------------------------------------------

def _run_frame_pipeline(
    input_path: str,
    output_path: str,
    info: VideoInfo,
    frame_processor: Callable[[np.ndarray, int], np.ndarray],
    progress_callback: Optional[Callable[[int, int], None]],
    should_cancel: Optional[Callable[[], bool]],
) -> None:
    if not _ffmpeg_available():
        raise VideoError(
            "ffmpeg/ffprobe não encontrados no PATH. Instale o ffmpeg "
            "(https://ffmpeg.org/download.html) para processar vídeos."
        )

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise VideoError(f"Não foi possível abrir o vídeo: {input_path}")

    tmp_dir = tempfile.mkdtemp(prefix="watermark_remover_")
    silent_video_path = os.path.join(tmp_dir, "video_sem_audio.mp4")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(silent_video_path, fourcc, info.fps, (info.width, info.height))
    if not writer.isOpened():
        cap.release()
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise VideoError("Não foi possível iniciar a codificação do vídeo de saída.")

    frame_index = 0
    try:
        while True:
            if should_cancel is not None and should_cancel():
                raise VideoError("Processamento cancelado pelo usuário.")

            ok, frame = cap.read()
            if not ok:
                break

            processed = frame_processor(frame, frame_index)
            writer.write(processed)

            frame_index += 1
            if progress_callback is not None:
                progress_callback(frame_index, info.frame_count or frame_index)
    finally:
        cap.release()
        writer.release()

    try:
        if info.has_audio:
            _mux_audio(silent_video_path, input_path, output_path)
        else:
            shutil.move(silent_video_path, output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _mux_audio(silent_video_path: str, original_with_audio_path: str, output_path: str) -> None:
    """Copia (sem recodificar) o áudio do vídeo original para dentro do vídeo já processado."""
    cmd = [
        "ffmpeg", "-y",
        "-i", silent_video_path,
        "-i", original_with_audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        raise VideoError(f"Falha ao remuxar áudio com ffmpeg: {result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# Modo 1: marca FIXA
# ---------------------------------------------------------------------------

def process_video(
    input_path: str,
    output_path: str,
    mask: np.ndarray,
    method: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Remove a marca d'água (fixa) de um vídeo inteiro.

    Args:
        input_path: caminho do vídeo original.
        output_path: caminho final desejado (ex: "saida.mp4").
        mask: máscara (H, W) uint8, na MESMA resolução do vídeo, aplicada em todos os frames.
        method: um dos InpaintMethod (core.inpaint).
        progress_callback: chamado como progress_callback(frame_atual, total_frames).
        should_cancel: se fornecido e retornar True, interrompe o processamento.
    """
    info = probe_video(input_path)
    if mask.shape[:2] != (info.height, info.width):
        raise VideoError(
            f"Máscara ({mask.shape[1]}x{mask.shape[0]}) não bate com a resolução "
            f"do vídeo ({info.width}x{info.height})."
        )

    def frame_processor(frame: np.ndarray, index: int) -> np.ndarray:
        return inpaint_image(frame, mask, method=method)

    _run_frame_pipeline(input_path, output_path, info, frame_processor, progress_callback, should_cancel)


# ---------------------------------------------------------------------------
# Modo 2: marca em MOVIMENTO (tracking automático a partir de uma região inicial)
# ---------------------------------------------------------------------------

def _create_tracker():
    """
    Cria o melhor tracker disponível na instalação do OpenCV do usuário.

    CSRT é mais preciso mas só existe se `opencv-contrib-python` estiver instalado.
    TrackerMIL vem no `opencv-python` padrão (nossa dependência no requirements.txt),
    então funciona em qualquer instalação — é o fallback garantido.
    """
    candidates = []

    if hasattr(cv2, "TrackerCSRT_create"):
        candidates.append(cv2.TrackerCSRT_create)
    legacy = getattr(cv2, "legacy", None)
    if legacy is not None and hasattr(legacy, "TrackerCSRT_create"):
        candidates.append(legacy.TrackerCSRT_create)
    if hasattr(cv2, "TrackerKCF_create"):
        candidates.append(cv2.TrackerKCF_create)
    if hasattr(cv2, "TrackerMIL_create"):
        candidates.append(cv2.TrackerMIL_create)

    for create_fn in candidates:
        try:
            return create_fn()
        except Exception:
            continue

    raise VideoError(
        "Nenhum tracker de vídeo disponível nesta instalação do OpenCV. "
        "Reinstale as dependências com: pip install -r requirements.txt"
    )


def _bbox_to_mask(bbox: BBox, width: int, height: int, padding: int) -> np.ndarray:
    x, y, w, h = [int(round(v)) for v in bbox]
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(width, x + w + padding)
    y1 = min(height, y + h + padding)

    mask = np.zeros((height, width), dtype=np.uint8)
    if x1 > x0 and y1 > y0:
        mask[y0:y1, x0:x1] = 255
    return mask


def process_video_moving_watermark(
    input_path: str,
    output_path: str,
    initial_bbox: BBox,
    method: str,
    padding: int = 6,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """
    Remove uma marca d'água que MUDA DE POSIÇÃO ao longo do vídeo.

    O usuário indica a região da marca apenas no primeiro frame (initial_bbox); a partir
    daí, um tracker de visão computacional (CSRT se disponível, senão MIL) acompanha essa
    região frame a frame, e a máscara de inpainting é reposicionada de acordo.

    Args:
        initial_bbox: (x, y, largura, altura) da marca no PRIMEIRO frame, em pixels da
            resolução original do vídeo.
        padding: margem extra (em pixels) adicionada ao redor da caixa rastreada, pra
            absorver pequenas imprecisões do tracker sem deixar borda da marca visível.
        Demais argumentos: mesmo significado de process_video().

    Observações importantes:
        - Se o tracker "perder" a marca (ex: ela sai de cena, ou há uma mudança de cena
          abrupta), o app continua usando a última posição conhecida em vez de travar —
          o resultado pode ficar impreciso nesses trechos, mas o processamento não para.
        - Funciona bem para marcas que se deslocam de forma relativamente suave/contínua
          (ex: um logo "flutuando" pela tela). Marcas que somem e reaparecem em posições
          muito diferentes, ou vídeos com cortes de cena, são mais desafiadores para o
          tracker — nesses casos o resultado deve ser revisado com atenção.
    """
    info = probe_video(input_path)

    x, y, w, h = initial_bbox
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > info.width or y + h > info.height:
        raise VideoError("Região inicial da marca d'água é inválida para a resolução do vídeo.")

    state = {"tracker": None, "bbox": (float(x), float(y), float(w), float(h))}

    def frame_processor(frame: np.ndarray, index: int) -> np.ndarray:
        if index == 0:
            state["tracker"] = _create_tracker()
            state["tracker"].init(frame, (x, y, w, h))
            bbox = (x, y, w, h)
        else:
            ok, tracked_bbox = state["tracker"].update(frame)
            if ok:
                state["bbox"] = tracked_bbox
            # se o tracker falhar, reaproveita a última posição conhecida em vez de parar
            bbox = state["bbox"]

        mask = _bbox_to_mask(bbox, info.width, info.height, padding)
        return inpaint_image(frame, mask, method=method)

    _run_frame_pipeline(input_path, output_path, info, frame_processor, progress_callback, should_cancel)
