"""
Motor de inpainting (remoção de marca d'água) — MVP.

Motor "rápido": OpenCV (Telea / Navier-Stokes) — CPU, quase instantâneo, bom pra fundos simples.
Motor "qualidade": LaMa (deep learning, via pacote `simple-lama-inpainting`) — usa GPU se
  disponível (CUDA), bem melhor em fundos texturizados/complexos. O modelo (~200MB) é baixado
  automaticamente na primeira execução e fica em cache local (~/.cache/torch/hub/checkpoints).
"""

from __future__ import annotations

import threading

import numpy as np
import cv2


class InpaintMethod:
    FAST_TELEA = "telea"
    FAST_NS = "ns"          # Navier-Stokes
    QUALITY_LAMA = "lama"   # deep learning, melhor qualidade em fundos complexos


def inpaint_image(image_bgr: np.ndarray, mask: np.ndarray, method: str = InpaintMethod.FAST_TELEA,
                   radius: int = 5) -> np.ndarray:
    """
    Remove a região marcada pela máscara, preenchendo com conteúdo reconstruído.

    Args:
        image_bgr: imagem original em BGR (formato OpenCV), shape (H, W, 3), dtype uint8.
        mask: máscara em escala de cinza, mesma altura/largura da imagem, dtype uint8.
              Pixels != 0 indicam a área a ser removida/reconstruída.
        method: InpaintMethod.FAST_TELEA, InpaintMethod.FAST_NS ou InpaintMethod.QUALITY_LAMA.
        radius: raio de vizinhança considerado pelo algoritmo clássico (só usado nos métodos FAST_*).

    Returns:
        Imagem resultante (BGR, uint8) com a região reconstruída.
    """
    if image_bgr is None:
        raise ValueError("image_bgr não pode ser None")
    if mask is None:
        raise ValueError("mask não pode ser None")
    if mask.shape[:2] != image_bgr.shape[:2]:
        raise ValueError(
            f"Dimensões da máscara {mask.shape[:2]} não batem com a imagem {image_bgr.shape[:2]}"
        )

    # Garante que a máscara é binária (0 ou 255) e uint8, como o cv2.inpaint espera.
    _, binary_mask = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)
    binary_mask = binary_mask.astype(np.uint8)

    if method == InpaintMethod.FAST_TELEA:
        flag = cv2.INPAINT_TELEA
    elif method == InpaintMethod.FAST_NS:
        flag = cv2.INPAINT_NS
    elif method == InpaintMethod.QUALITY_LAMA:
        return inpaint_lama(image_bgr, binary_mask)
    else:
        raise ValueError(f"Método de inpainting desconhecido: {method}")

    result = cv2.inpaint(image_bgr, binary_mask, inpaintRadius=radius, flags=flag)
    return result


def inpaint_lama(image_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """
    Motor de qualidade — inpainting via LaMa (deep learning).

    Reconstrói a região marcada com muito mais fidelidade que o motor rápido em fundos
    complexos (texturas, padrões, gradientes), à custa de ser mais lento e exigir mais memória.

    Na primeira chamada, baixa o checkpoint pré-treinado (~200MB) e o mantém em cache;
    chamadas seguintes reaproveitam o modelo já carregado em memória (processo atual).
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Dependência faltando para o motor de qualidade. Rode: pip install -r requirements.txt"
        ) from exc

    try:
        model = _get_lama_model()
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível carregar o modelo LaMa (verifique sua conexão com a internet "
            "na primeira execução — o modelo precisa ser baixado uma vez). "
            f"Detalhe: {exc}"
        ) from exc

    h, w = image_bgr.shape[:2]

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    pil_mask = Image.fromarray(mask).convert("L")

    result_pil = model(pil_image, pil_mask)
    result_rgb = np.array(result_pil)

    # O LaMa faz padding interno (múltiplo de 8) e não recorta de volta — recortamos aqui
    # para garantir que a saída tem exatamente a mesma resolução da imagem original.
    result_rgb = result_rgb[:h, :w]

    result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
    return result_bgr


# ---------------------------------------------------------------------------
# Carregamento do modelo LaMa: feito uma única vez por processo (é pesado —
# tanto em tempo quanto em memória) e protegido por lock para uso seguro
# mesmo se chamado a partir de uma thread de worker da UI.
# ---------------------------------------------------------------------------

_lama_model = None
_lama_lock = threading.Lock()


def _get_lama_model():
    global _lama_model
    if _lama_model is not None:
        return _lama_model

    with _lama_lock:
        if _lama_model is None:  # checagem dupla após adquirir o lock
            # Força o uso de CPU para evitar problemas com CUDA mal configurado
            import os
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
            
            import torch
            # Força CPU explicitamente
            torch.set_default_device('cpu')
            
            from simple_lama_inpainting import SimpleLama
            _lama_model = SimpleLama(device='cpu')
    return _lama_model


def preload_lama_model_async(on_done=None, on_error=None):
    """
    Dispara o carregamento (e download, se necessário) do modelo LaMa em background,
    para que a UI não trave. Útil para pré-aquecer o modelo assim que o usuário
    seleciona o motor "Qualidade" no combo, antes de clicar em Processar.
    """
    def _worker():
        try:
            _get_lama_model()
            if on_done:
                on_done()
        except Exception as exc:  # noqa: BLE001 - repassamos qualquer erro pro callback
            if on_error:
                on_error(exc)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
