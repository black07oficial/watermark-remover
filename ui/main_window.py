"""
Janela principal do MVP de remoção de marca d'água — imagem estática e vídeo
(marca fixa ou em movimento).
"""

from __future__ import annotations

import os
import sys
import threading
import logging

import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSlider, QButtonGroup, QRadioButton, QMessageBox, QScrollArea,
    QComboBox, QStatusBar, QProgressBar, QDialog, QStackedWidget
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from ui.canvas import MaskCanvas
from ui.dashboard import DashboardWidget
from core.inpaint import inpaint_image, InpaintMethod
from core.video import (
    probe_video, read_first_frame, process_video, process_video_moving_watermark, VideoError
)

logger = logging.getLogger('WatermarkRemover.UI')

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv")

WATERMARK_FIXED = "fixed"
WATERMARK_MOVING = "moving"


class ModelDownloadDialog(QDialog):
    """Dialog modal que mostra o progresso do download do modelo LaMa."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Baixando Modelo LaMa")
        self.setModal(True)
        self.setFixedSize(450, 150)
        
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Baixando Modelo de Deep Learning")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Mensagem
        self.message = QLabel(
            "Baixando modelo LaMa (~200MB)...\n"
            "Isso acontece apenas uma vez.\n"
            "Aguarde, pode levar alguns minutos."
        )
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        layout.addWidget(self.message)
        
        # Barra de progresso indeterminada
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # modo indeterminado
        layout.addWidget(self.progress)
        
        layout.addStretch()


class ModelDownloadWorker(QThread):
    """Worker para baixar/carregar o modelo LaMa em background."""
    
    finished_ok = pyqtSignal()
    finished_error = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self._logger = logging.getLogger('WatermarkRemover.ModelDownload')
    
    def run(self):
        try:
            self._logger.info("Iniciando download/carregamento do modelo LaMa...")
            # Importa e carrega o modelo (faz download se necessário)
            from core.inpaint import _get_lama_model
            self._logger.info("Chamando _get_lama_model()...")
            _get_lama_model()
            self._logger.info("Modelo LaMa carregado com sucesso!")
        except Exception as exc:
            self._logger.exception("ERRO ao carregar modelo LaMa:")
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit()


class ImageProcessWorker(QThread):
    """Roda o inpainting de uma imagem fora da thread da UI."""

    finished_ok = pyqtSignal(np.ndarray)
    finished_error = pyqtSignal(str)

    def __init__(self, image: np.ndarray, mask: np.ndarray, method: str, parent=None):
        super().__init__(parent)
        self._image = image
        self._mask = mask
        self._method = method
        self._logger = logging.getLogger('WatermarkRemover.ImageWorker')

    def run(self):
        try:
            self._logger.info(f"Iniciando processamento de imagem com método: {self._method}")
            self._logger.debug(f"Imagem: {self._image.shape}, Máscara: {self._mask.shape}")
            result = inpaint_image(self._image, self._mask, method=self._method)
            self._logger.info("Processamento de imagem concluído com sucesso")
        except Exception as exc:  # noqa: BLE001 - repassamos o erro pra UI mostrar
            self._logger.exception(f"Erro no processamento de imagem:")
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit(result)


class VideoProcessWorker(QThread):
    """
    Roda o processamento de vídeo completo (frame a frame + remux de áudio).

    Suporta os dois modos: marca fixa (uma máscara única) e marca em movimento
    (bounding box inicial + tracking automático).
    """

    progress = pyqtSignal(int, int)  # (frame_atual, total_frames)
    finished_ok = pyqtSignal(str)    # caminho do arquivo final
    finished_error = pyqtSignal(str)

    def __init__(
        self,
        input_path: str,
        output_path: str,
        method: str,
        watermark_mode: str,
        mask: np.ndarray | None = None,
        initial_bbox: tuple[int, int, int, int] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._input_path = input_path
        self._output_path = output_path
        self._method = method
        self._watermark_mode = watermark_mode
        self._mask = mask
        self._initial_bbox = initial_bbox
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        try:
            if self._watermark_mode == WATERMARK_MOVING:
                process_video_moving_watermark(
                    self._input_path,
                    self._output_path,
                    self._initial_bbox,
                    self._method,
                    progress_callback=lambda cur, total: self.progress.emit(cur, total),
                    should_cancel=self._cancel_event.is_set,
                )
            else:
                process_video(
                    self._input_path,
                    self._output_path,
                    self._mask,
                    self._method,
                    progress_callback=lambda cur, total: self.progress.emit(cur, total),
                    should_cancel=self._cancel_event.is_set,
                )
        except Exception as exc:  # noqa: BLE001 - repassamos o erro pra UI mostrar
            self.finished_error.emit(str(exc))
            return
        self.finished_ok.emit(self._output_path)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Inicializando MainWindow...")
        self.setWindowTitle("Watermark Remover - Dashboard")
        self.resize(1200, 800)

        self._result_image: np.ndarray | None = None  # último resultado de IMAGEM processada (BGR)
        self._image_worker: ImageProcessWorker | None = None
        self._video_worker: VideoProcessWorker | None = None
        self._model_download_worker: ModelDownloadWorker | None = None
        self._model_download_dialog: ModelDownloadDialog | None = None

        # estado do modo vídeo
        self._is_video = False
        self._video_path: str | None = None
        self._video_info = None  # core.video.VideoInfo
        
        # flag para saber se modelo LaMa já foi carregado
        self._lama_model_loaded = False
        self._pending_video_params = None  # guarda parâmetros durante download do modelo

        self._build_ui()
        logger.info("MainWindow inicializada com sucesso")

    # ---------- construção da UI ----------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Stack widget para alternar entre dashboard e editor
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack)
        
        # Página 0: Dashboard
        self.dashboard = DashboardWidget()
        self.dashboard.tool_selected.connect(self.on_tool_selected)
        self.stack.addWidget(self.dashboard)
        
        # Página 1: Watermark Editor
        self.editor_widget = self._build_editor_widget()
        self.stack.addWidget(self.editor_widget)
        
        # Inicia na dashboard
        self.stack.setCurrentIndex(0)
        
        # --- status bar ---
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bem-vindo! Selecione uma ferramenta para começar.")
    
    def on_tool_selected(self, tool_id: str):
        """Callback quando uma ferramenta é selecionada na dashboard."""
        logger.info(f"Ferramenta selecionada: {tool_id}")
        
        if tool_id == "watermark_editor":
            # Abre o editor de marca d'água
            self.stack.setCurrentIndex(1)
            self.status.showMessage("Watermark Editor: Abra uma imagem ou vídeo para começar.")
        else:
            # Outras ferramentas ainda não implementadas
            QMessageBox.information(
                self,
                "Em breve",
                f"A ferramenta '{tool_id}' estará disponível em breve!\n\n"
                "Por enquanto, apenas o Watermark Editor está funcional."
            )
    
    def _build_editor_widget(self) -> QWidget:
        """Constrói o widget do editor de marca d'água."""
        editor = QWidget()
        editor_layout = QVBoxLayout(editor)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        
        # Barra superior com botão voltar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(10, 5, 10, 5)
        
        self.btn_back = QPushButton("← Voltar")
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_back.setStyleSheet("""
            QPushButton {
                background: #7B68EE;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #6A5ACD;
            }
        """)
        top_bar.addWidget(self.btn_back)
        
        title_editor = QLabel("💧 Watermark Editor")
        title_editor.setStyleSheet("font-size: 14pt; font-weight: bold; color: #2C3E50;")
        top_bar.addWidget(title_editor)
        top_bar.addStretch()
        
        editor_layout.addLayout(top_bar)
        
        # Conteúdo do editor (UI original)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # --- barra de ferramentas superior ---
        toolbar = QHBoxLayout()

        self.btn_open = QPushButton("Abrir Imagem ou Vídeo")
        self.btn_open.clicked.connect(self.on_open_file)
        toolbar.addWidget(self.btn_open)

        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("Modo de seleção:"))

        self.radio_rect = QRadioButton("Retângulo")
        self.radio_brush = QRadioButton("Pincel livre")
        self.radio_rect.setChecked(True)
        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.radio_rect)
        self.mode_group.addButton(self.radio_brush)
        self.radio_rect.toggled.connect(self.on_mode_changed)
        toolbar.addWidget(self.radio_rect)
        toolbar.addWidget(self.radio_brush)

        toolbar.addSpacing(20)
        toolbar.addWidget(QLabel("Tamanho do pincel:"))
        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setMinimum(5)
        self.brush_slider.setMaximum(80)
        self.brush_slider.setValue(20)
        self.brush_slider.setFixedWidth(140)
        self.brush_slider.valueChanged.connect(self.on_brush_size_changed)
        toolbar.addWidget(self.brush_slider)

        toolbar.addSpacing(20)
        self.btn_clear_mask = QPushButton("Limpar Máscara")
        self.btn_clear_mask.clicked.connect(self.on_clear_mask)
        toolbar.addWidget(self.btn_clear_mask)

        toolbar.addStretch()
        content_layout.addLayout(toolbar)

        # --- barra específica de vídeo: marca fixa vs em movimento ---
        video_bar = QHBoxLayout()
        self.video_mode_label = QLabel("Comportamento da marca no vídeo:")
        video_bar.addWidget(self.video_mode_label)

        self.radio_watermark_fixed = QRadioButton("Fixa (mesma posição o vídeo todo)")
        self.radio_watermark_moving = QRadioButton("Em movimento (rastrear automaticamente)")
        self.radio_watermark_fixed.setChecked(True)
        self.watermark_mode_group = QButtonGroup()
        self.watermark_mode_group.addButton(self.radio_watermark_fixed)
        self.watermark_mode_group.addButton(self.radio_watermark_moving)
        self.radio_watermark_moving.toggled.connect(self.on_watermark_mode_changed)
        video_bar.addWidget(self.radio_watermark_fixed)
        video_bar.addWidget(self.radio_watermark_moving)
        video_bar.addStretch()
        content_layout.addLayout(video_bar)
        self._set_video_controls_visible(False)  # só aparece quando um vídeo é aberto

        # --- segunda barra: motor de processamento + ações ---
        actions_bar = QHBoxLayout()

        actions_bar.addWidget(QLabel("Motor:"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Rápido (Telea)", InpaintMethod.FAST_TELEA)
        self.engine_combo.addItem("Rápido (Navier-Stokes)", InpaintMethod.FAST_NS)
        self.engine_combo.addItem("Qualidade (LaMa, mais lento)", InpaintMethod.QUALITY_LAMA)
        actions_bar.addWidget(self.engine_combo)

        actions_bar.addSpacing(20)
        self.btn_process = QPushButton("Processar")
        self.btn_process.clicked.connect(self.on_process)
        actions_bar.addWidget(self.btn_process)

        self.btn_save = QPushButton("Salvar Resultado")
        self.btn_save.clicked.connect(self.on_save_result)
        actions_bar.addWidget(self.btn_save)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.on_cancel_video)
        self.btn_cancel.hide()
        actions_bar.addWidget(self.btn_cancel)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(200)
        self.progress.hide()
        actions_bar.addWidget(self.progress)

        actions_bar.addStretch()
        content_layout.addLayout(actions_bar)

        # --- canvas com scroll (imagens/frames grandes) ---
        self.canvas = MaskCanvas()
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(scroll, stretch=1)
        
        editor_layout.addWidget(content)
        
        return editor

    def _set_video_controls_visible(self, visible: bool):
        self.video_mode_label.setVisible(visible)
        self.radio_watermark_fixed.setVisible(visible)
        self.radio_watermark_moving.setVisible(visible)

    # ---------- abertura de arquivo ----------

    def on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir imagem ou vídeo", "",
            "Imagens e vídeos (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov *.avi *.mkv)"
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            self._open_video(path)
        elif ext in IMAGE_EXTENSIONS:
            self._open_image(path)
        else:
            QMessageBox.warning(self, "Formato não suportado", f"Extensão não reconhecida: {ext}")

    def _open_image(self, path: str):
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            QMessageBox.warning(self, "Erro", "Não foi possível abrir essa imagem.")
            return
        self._is_video = False
        self._video_path = None
        self._video_info = None
        self._set_video_controls_visible(False)
        self.canvas.set_image(image)
        self._result_image = None
        self.status.showMessage(f"Imagem carregada: {path}  ({image.shape[1]}x{image.shape[0]})")

    def _open_video(self, path: str):
        try:
            info = probe_video(path)
            first_frame = read_first_frame(path)
        except VideoError as exc:
            QMessageBox.critical(self, "Erro ao abrir vídeo", str(exc))
            return

        self._is_video = True
        self._video_path = path
        self._video_info = info
        self._result_image = None
        self._set_video_controls_visible(True)
        self.canvas.set_image(first_frame)

        audio_txt = "com áudio" if info.has_audio else "sem áudio"
        self.status.showMessage(
            f"Vídeo carregado: {path}  ({info.width}x{info.height}, {info.fps:.1f} fps, "
            f"{info.frame_count} frames, {audio_txt}). Marque a região da marca d'água no "
            f"primeiro frame."
        )

    # ---------- máscara ----------

    def on_mode_changed(self):
        self.canvas.mode = MaskCanvas.RECT_MODE if self.radio_rect.isChecked() else MaskCanvas.BRUSH_MODE

    def on_watermark_mode_changed(self):
        if self.radio_watermark_moving.isChecked():
            # marca em movimento só funciona com retângulo (é uma bounding box pro tracker)
            self.radio_rect.setChecked(True)
            self.radio_brush.setEnabled(False)
            self.canvas.clear_mask()
            self.status.showMessage(
                "Modo marca em movimento: desenhe um RETÂNGULO ao redor da marca no primeiro "
                "frame. Ela será rastreada automaticamente pelo resto do vídeo."
            )
        else:
            self.radio_brush.setEnabled(True)

    def on_brush_size_changed(self, value: int):
        self.canvas.brush_size = value

    def on_clear_mask(self):
        self.canvas.clear_mask()
        self.status.showMessage("Máscara limpa.")

    # ---------- processamento ----------

    def on_process(self):
        if self._is_video:
            self._process_video()
        else:
            self._process_image()

    def _process_image(self):
        if self._image_worker is not None and self._image_worker.isRunning():
            return

        image = self.canvas.get_original_image()
        if image is None:
            QMessageBox.information(self, "Aviso", "Abra uma imagem primeiro.")
            return
        if not self.canvas.has_mask():
            QMessageBox.information(self, "Aviso", "Marque a região da marca d'água antes de processar.")
            return

        mask = self.canvas.get_mask_as_numpy()
        method = self.engine_combo.currentData()

        # Se escolheu LaMa e modelo ainda não foi carregado, baixa primeiro
        if method == InpaintMethod.QUALITY_LAMA and not self._lama_model_loaded:
            self._download_lama_model_then_process(image, mask, method)
            return

        # Processa direto
        if method == InpaintMethod.QUALITY_LAMA:
            self.status.showMessage("Processando com LaMa...")
        else:
            self.status.showMessage("Processando...")

        self.progress.setRange(0, 0)  # indeterminado
        self._set_busy(True, cancelable=False)

        self._image_worker = ImageProcessWorker(image, mask, method)
        self._image_worker.finished_ok.connect(self._on_image_finished)
        self._image_worker.finished_error.connect(self._on_process_error)
        self._image_worker.start()
    
    def _download_lama_model_then_process(self, image: np.ndarray, mask: np.ndarray, method: str):
        """Baixa o modelo LaMa com popup de progresso, depois processa a imagem."""
        logger.info("Iniciando download do modelo LaMa...")
        
        # Cria dialog de download
        self._model_download_dialog = ModelDownloadDialog(self)
        
        # Cria worker de download
        self._model_download_worker = ModelDownloadWorker()
        self._model_download_worker.finished_ok.connect(
            lambda: self._on_model_download_finished(image, mask, method)
        )
        self._model_download_worker.finished_error.connect(self._on_model_download_error)
        
        # Inicia download e mostra dialog
        logger.info("Iniciando worker de download...")
        self._model_download_worker.start()
        logger.info("Mostrando dialog de download...")
        self._model_download_dialog.exec()
    
    def _on_model_download_finished(self, image: np.ndarray, mask: np.ndarray, method: str):
        """Modelo baixado com sucesso, agora processa a imagem."""
        self._lama_model_loaded = True
        if self._model_download_dialog:
            self._model_download_dialog.accept()
            self._model_download_dialog = None
        
        # Agora processa a imagem
        self.status.showMessage("Modelo carregado! Processando imagem...")
        self.progress.setRange(0, 0)
        self._set_busy(True, cancelable=False)
        
        self._image_worker = ImageProcessWorker(image, mask, method)
        self._image_worker.finished_ok.connect(self._on_image_finished)
        self._image_worker.finished_error.connect(self._on_process_error)
        self._image_worker.start()
    
    def _on_model_download_error(self, error_msg: str):
        """Erro ao baixar modelo."""
        if self._model_download_dialog:
            self._model_download_dialog.reject()
            self._model_download_dialog = None
        
        QMessageBox.critical(
            self, 
            "Erro ao carregar modelo",
            f"Não foi possível carregar o modelo LaMa (verifique sua conexão com a internet "
            f"na primeira execução — o modelo precisa ser baixado uma vez). Detalhe:\n\n{error_msg}"
        )
        self.status.showMessage("Erro ao carregar modelo LaMa.")

    def _on_image_finished(self, result: np.ndarray):
        self._set_busy(False)
        self._result_image = result
        self.canvas.set_image(result)
        self.canvas.clear_mask()
        self.status.showMessage("Processamento concluído. Revise o resultado e salve se estiver satisfeito.")

    def _process_video(self):
        if self._video_worker is not None and self._video_worker.isRunning():
            return
        if self._video_path is None or self._video_info is None:
            QMessageBox.information(self, "Aviso", "Abra um vídeo primeiro.")
            return
        if not self.canvas.has_mask():
            QMessageBox.information(self, "Aviso", "Marque a região da marca d'água antes de processar.")
            return

        watermark_mode = WATERMARK_MOVING if self.radio_watermark_moving.isChecked() else WATERMARK_FIXED

        method = self.engine_combo.currentData()
        
        # Se escolheu LaMa e modelo ainda não foi carregado, baixa primeiro
        if method == InpaintMethod.QUALITY_LAMA and not self._lama_model_loaded:
            # Salva os parâmetros para usar depois do download
            self._pending_video_params = (watermark_mode, method)
            self._download_lama_model_then_process_video()
            return
        
        # Aviso de performance para LaMa em vídeo
        if method == InpaintMethod.QUALITY_LAMA:
            resp = QMessageBox.question(
                self, "Aviso de desempenho",
                f"O motor Qualidade (LaMa) processa frame a frame e pode ser bem lento em vídeo "
                f"(este vídeo tem {self._video_info.frame_count} frames). "
                f"Em CPU, isso pode levar de minutos a horas dependendo do hardware. Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self._start_video_processing(watermark_mode, method)
    
    def _download_lama_model_then_process_video(self):
        """Baixa o modelo LaMa com popup de progresso, depois processa o vídeo."""
        # Cria dialog de download
        self._model_download_dialog = ModelDownloadDialog(self)
        
        # Cria worker de download
        self._model_download_worker = ModelDownloadWorker()
        self._model_download_worker.finished_ok.connect(self._on_model_download_finished_video)
        self._model_download_worker.finished_error.connect(self._on_model_download_error)
        
        # Inicia download e mostra dialog
        self._model_download_worker.start()
        self._model_download_dialog.exec()
    
    def _on_model_download_finished_video(self):
        """Modelo baixado com sucesso, agora processa o vídeo."""
        self._lama_model_loaded = True
        if self._model_download_dialog:
            self._model_download_dialog.accept()
            self._model_download_dialog = None
        
        # Recupera parâmetros salvos
        watermark_mode, method = self._pending_video_params
        
        # Aviso de performance
        resp = QMessageBox.question(
            self, "Aviso de desempenho",
            f"O motor Qualidade (LaMa) processa frame a frame e pode ser bem lento em vídeo "
            f"(este vídeo tem {self._video_info.frame_count} frames). "
            f"Em CPU, isso pode levar de minutos a horas dependendo do hardware. Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        
        self._start_video_processing(watermark_mode, method)
    
    def _start_video_processing(self, watermark_mode: str, method: str):
        """Inicia o processamento de vídeo propriamente dito."""
        default_name = os.path.splitext(os.path.basename(self._video_path))[0] + "_sem_marca.mp4"
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar vídeo processado como", default_name, "MP4 (*.mp4)"
        )
        if not output_path:
            return

        mask = self.canvas.get_mask_as_numpy()
        initial_bbox = None
        if watermark_mode == WATERMARK_MOVING:
            x, y, w, h = cv2.boundingRect(mask)
            if w == 0 or h == 0:
                QMessageBox.warning(self, "Aviso", "Não foi possível determinar a região marcada.")
                return
            initial_bbox = (x, y, w, h)
            self.status.showMessage("Rastreando e processando vídeo, frame a frame...")
        else:
            self.status.showMessage("Processando vídeo, frame a frame...")

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_busy(True, cancelable=True)

        self._video_worker = VideoProcessWorker(
            self._video_path, output_path, method, watermark_mode,
            mask=mask, initial_bbox=initial_bbox,
        )
        self._video_worker.progress.connect(self._on_video_progress)
        self._video_worker.finished_ok.connect(self._on_video_finished)
        self._video_worker.finished_error.connect(self._on_process_error)
        self._video_worker.start()

    def _on_video_progress(self, current: int, total: int):
        pct = int((current / total) * 100) if total else 0
        self.progress.setValue(pct)
        self.status.showMessage(f"Processando vídeo... frame {current}/{total} ({pct}%)")

    def _on_video_finished(self, output_path: str):
        self._set_busy(False)
        self.status.showMessage(f"Vídeo processado e salvo em: {output_path}")
        QMessageBox.information(self, "Concluído", f"Vídeo salvo em:\n{output_path}")

    def on_cancel_video(self):
        if self._video_worker is not None and self._video_worker.isRunning():
            self._video_worker.cancel()
            self.status.showMessage("Cancelando... aguarde o frame atual terminar.")

    def _on_process_error(self, message: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Erro no processamento", message)
        self.status.showMessage("Erro no processamento.")

    def _set_busy(self, busy: bool, cancelable: bool = False):
        self.btn_process.setEnabled(not busy)
        self.btn_open.setEnabled(not busy)
        self.engine_combo.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.btn_cancel.setVisible(busy and cancelable)

    # ---------- salvar (imagem) ----------

    def on_save_result(self):
        if self._is_video:
            QMessageBox.information(
                self, "Aviso",
                "Para vídeo, o caminho de saída já é escolhido ao clicar em Processar — "
                "não é necessário usar Salvar Resultado."
            )
            return
        if self._result_image is None:
            QMessageBox.information(self, "Aviso", "Nada para salvar ainda — processe uma imagem primeiro.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar resultado", "resultado.png", "PNG (*.png);;JPEG (*.jpg)"
        )
        if not path:
            return
        cv2.imwrite(path, self._result_image)
        self.status.showMessage(f"Resultado salvo em: {path}")


def main():
    from PyQt6.QtWidgets import QApplication
    import sys
    
    logger.info("Criando QApplication...")
    app = QApplication(sys.argv)
    logger.info("QApplication criada")
    
    logger.info("Criando MainWindow...")
    window = MainWindow()
    logger.info("MainWindow criada")
    
    logger.info("Mostrando janela...")
    window.show()
    logger.info("Janela visível, entrando no event loop...")
    
    exit_code = app.exec()
    logger.info(f"Event loop encerrado com código: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
