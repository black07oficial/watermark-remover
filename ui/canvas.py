"""
Canvas interativo: exibe a imagem carregada e permite ao usuário desenhar
a máscara da região a ser removida (retângulo ou pincel livre).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QMouseEvent
from PyQt6.QtCore import Qt, QPoint, QRect
import numpy as np


class MaskCanvas(QLabel):
    RECT_MODE = "rect"
    BRUSH_MODE = "brush"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._original_image: np.ndarray | None = None  # BGR, resolução original
        self._display_pixmap: QPixmap | None = None
        self._mask_image: QImage | None = None  # escala de cinza, MESMA resolução da exibição

        self.mode = self.RECT_MODE
        self.brush_size = 20

        self._drawing = False
        self._start_point = QPoint()
        self._last_point = QPoint()

    # ---------- carregamento ----------

    def set_image(self, image_bgr: np.ndarray):
        """Recebe uma imagem BGR (OpenCV) e prepara o canvas para exibição/edição."""
        self._original_image = image_bgr
        h, w = image_bgr.shape[:2]

        rgb = image_bgr[:, :, ::-1].copy()  # BGR -> RGB para o Qt
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        self._display_pixmap = QPixmap.fromImage(qimg)

        # máscara em branco (preto = nada selecionado), mesma resolução da imagem exibida
        self._mask_image = QImage(w, h, QImage.Format.Format_Grayscale8)
        self._mask_image.fill(0)

        self.setPixmap(self._display_pixmap)
        self.setFixedSize(self._display_pixmap.size())
        self._refresh()

    def clear_mask(self):
        if self._mask_image is not None:
            self._mask_image.fill(0)
            self._refresh()

    def get_mask_as_numpy(self) -> np.ndarray | None:
        """Retorna a máscara atual como array numpy (H, W) uint8, na resolução original."""
        if self._mask_image is None:
            return None
        w, h = self._mask_image.width(), self._mask_image.height()
        ptr = self._mask_image.bits()
        ptr.setsize(h * w)
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, w)).copy()
        return arr

    def has_mask(self) -> bool:
        mask = self.get_mask_as_numpy()
        return mask is not None and mask.max() > 0

    # ---------- interação do mouse ----------

    def mousePressEvent(self, event: QMouseEvent):
        if self._display_pixmap is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._start_point = event.position().toPoint()
            self._last_point = self._start_point
            if self.mode == self.BRUSH_MODE:
                self._paint_brush(self._start_point)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self._drawing or self._display_pixmap is None:
            return
        current = event.position().toPoint()
        if self.mode == self.BRUSH_MODE:
            self._paint_brush(current)
            self._last_point = current
        else:
            # modo retângulo: preview em tempo real
            self._refresh(preview_rect=QRect(self._start_point, current).normalized())

    def mouseReleaseEvent(self, event: QMouseEvent):
        if not self._drawing or self._display_pixmap is None:
            return
        self._drawing = False
        if self.mode == self.RECT_MODE:
            end_point = event.position().toPoint()
            rect = QRect(self._start_point, end_point).normalized()
            self._paint_rect(rect)
        self._refresh()

    # ---------- desenho na máscara ----------

    def _paint_rect(self, rect: QRect):
        painter = QPainter(self._mask_image)
        painter.setBrush(QColor(255, 255, 255))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        painter.end()

    def _paint_brush(self, point: QPoint):
        painter = QPainter(self._mask_image)
        pen = QPen(QColor(255, 255, 255))
        pen.setWidth(self.brush_size)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(self._last_point, point)
        painter.end()
        self._last_point = point
        self._refresh()

    # ---------- renderização ----------

    def _refresh(self, preview_rect: QRect | None = None):
        if self._display_pixmap is None:
            return
        combined = QPixmap(self._display_pixmap)
        painter = QPainter(combined)

        # overlay semitransparente vermelho mostrando a máscara atual
        mask_np = self.get_mask_as_numpy()
        if mask_np is not None and mask_np.max() > 0:
            h, w = mask_np.shape
            rgba = np.zeros((h, w, 4), dtype=np.uint8)
            rgba[..., 0] = 255  # R
            rgba[..., 3] = (mask_np.astype(np.float32) * 0.45).astype(np.uint8)  # alpha
            qoverlay = QImage(rgba.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
            painter.drawImage(0, 0, qoverlay)

        if preview_rect is not None:
            pen = QPen(QColor(255, 0, 0))
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(preview_rect)

        painter.end()
        self.setPixmap(combined)

    def get_original_image(self) -> np.ndarray | None:
        return self._original_image
