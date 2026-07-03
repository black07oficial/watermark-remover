"""
Dashboard principal - Tela inicial do Watermark Remover.
Layout moderno com cards de ferramentas e navegação lateral.
"""

from __future__ import annotations

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor

logger = logging.getLogger('WatermarkRemover.Dashboard')


class ToolCard(QFrame):
    """Card clicável para uma ferramenta."""
    
    clicked = pyqtSignal(str)  # emite o ID da ferramenta
    
    def __init__(self, tool_id: str, title: str, description: str, 
                 color: str = "#E8DFF5", icon_text: str = "🎨", parent=None):
        super().__init__(parent)
        self.tool_id = tool_id
        self._setup_ui(title, description, color, icon_text)
    
    def _setup_ui(self, title: str, description: str, color: str, icon_text: str):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(140)
        self.setMaximumHeight(160)
        
        # Estilo do card
        self.setStyleSheet(f"""
            ToolCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {color}, stop:1 {self._adjust_color(color, -20)});
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.05);
            }}
            ToolCard:hover {{
                border: 2px solid #7B68EE;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {self._adjust_color(color, 10)}, stop:1 {color});
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)
        
        # Título
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2C3E50;")
        
        # Descrição
        desc_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(9)
        desc_label.setFont(desc_font)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #5D6D7E;")
        
        # Ícone (emoji grande no canto direito)
        icon_label = QLabel(icon_text)
        icon_font = QFont()
        icon_font.setPointSize(40)
        icon_label.setFont(icon_font)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        icon_label.setStyleSheet("color: rgba(123, 104, 238, 0.4);")
        
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        layout.addStretch()
        layout.addWidget(icon_label)
    
    def _adjust_color(self, hex_color: str, adjustment: int) -> str:
        """Ajusta o brilho de uma cor hex."""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        r = max(0, min(255, r + adjustment))
        g = max(0, min(255, g + adjustment))
        b = max(0, min(255, b + adjustment))
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.tool_id)
        super().mousePressEvent(event)


class SmallToolButton(QPushButton):
    """Botão pequeno para ferramentas secundárias."""
    
    def __init__(self, title: str, icon_text: str = "🛠", parent=None):
        super().__init__(parent)
        self.setText(f"{icon_text}  {title}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
        
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        
        self.setStyleSheet("""
            SmallToolButton {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                text-align: left;
                padding-left: 15px;
                color: #2C3E50;
            }
            SmallToolButton:hover {
                background: #F8F9FA;
                border: 2px solid #7B68EE;
            }
            SmallToolButton:pressed {
                background: #E8DFF5;
            }
        """)


class SidebarButton(QPushButton):
    """Botão da barra lateral."""
    
    def __init__(self, text: str, icon_text: str = "📁", parent=None):
        super().__init__(parent)
        self.setText(f"  {icon_text}  {text}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(45)
        self.setCheckable(True)
        
        font = QFont()
        font.setPointSize(11)
        self.setFont(font)
        
        self.setStyleSheet("""
            SidebarButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                text-align: left;
                padding-left: 20px;
                color: #5D6D7E;
            }
            SidebarButton:hover {
                background: rgba(123, 104, 238, 0.1);
                color: #7B68EE;
            }
            SidebarButton:checked {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FFE5B4, stop:1 #FFDAB9);
                color: #D2691E;
                font-weight: bold;
                border-left: 4px solid #FF8C00;
            }
        """)


class DashboardWidget(QWidget):
    """Widget principal do dashboard."""
    
    tool_selected = pyqtSignal(str)  # emite o ID da ferramenta selecionada
    
    def __init__(self, parent=None):
        super().__init__(parent)
        logger.info("Inicializando Dashboard...")
        self._setup_ui()
        logger.info("Dashboard inicializado")
    
    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Barra lateral
        sidebar = self._create_sidebar()
        main_layout.addWidget(sidebar)
        
        # Área principal
        main_area = self._create_main_area()
        main_layout.addWidget(main_area, stretch=1)
    
    def _create_sidebar(self) -> QWidget:
        """Cria a barra lateral de navegação."""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border-right: 1px solid #E0E0E0;
            }
        """)
        
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(5)
        
        # Logo/Título
        logo = QLabel("🎨 Watermark\n     Remover")
        logo_font = QFont()
        logo_font.setPointSize(11)
        logo_font.setBold(True)
        logo.setFont(logo_font)
        logo.setStyleSheet("color: #7B68EE; padding: 10px;")
        layout.addWidget(logo)
        
        layout.addSpacing(20)
        
        # Botões de navegação
        self.btn_home = SidebarButton("Home", "🏠")
        self.btn_home.setChecked(True)
        layout.addWidget(self.btn_home)
        
        self.btn_files = SidebarButton("Meus Arquivos", "📁")
        layout.addWidget(self.btn_files)
        
        layout.addSpacing(20)
        
        self.btn_tools = SidebarButton("Ferramentas", "🛠")
        layout.addWidget(self.btn_tools)
        
        layout.addSpacing(10)
        
        self.btn_settings = SidebarButton("Configurações", "⚙️")
        layout.addWidget(self.btn_settings)
        
        layout.addStretch()
        
        # Versão no rodapé
        version = QLabel("v1.0 MVP")
        version.setStyleSheet("color: #95A5A6; font-size: 9px; padding: 10px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)
        
        return sidebar
    
    def _create_main_area(self) -> QWidget:
        """Cria a área principal com scroll."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: white;")
        
        content = QWidget()
        scroll.setWidget(content)
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(25)
        
        # Cabeçalho
        header = self._create_header()
        layout.addWidget(header)
        
        # Cards principais (3 colunas)
        main_cards = self._create_main_cards()
        layout.addWidget(main_cards)
        
        # Ferramentas secundárias
        secondary_tools = self._create_secondary_tools()
        layout.addWidget(secondary_tools)
        
        # Seção AI Lab
        ai_lab = self._create_ai_lab_section()
        layout.addWidget(ai_lab)
        
        layout.addStretch()
        
        return scroll
    
    def _create_header(self) -> QWidget:
        """Cria o cabeçalho da dashboard."""
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setSpacing(5)
        
        title = QLabel("Bem-vindo ao Watermark Remover")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2C3E50;")
        
        subtitle = QLabel("Escolha uma ferramenta para começar")
        subtitle.setStyleSheet("color: #7F8C8D; font-size: 11pt;")
        
        layout.addWidget(title)
        layout.addWidget(subtitle)
        
        return header
    
    def _create_main_cards(self) -> QWidget:
        """Cria os cards principais em grid."""
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(15)
        
        # Card 1: Conversor (placeholder futuro)
        card1 = ToolCard(
            "converter",
            "Conversor",
            "Converta vídeo/áudio entre 1.000+ formatos.",
            "#FCE4EC",
            "🔄"
        )
        card1.clicked.connect(self.tool_selected.emit)
        grid.addWidget(card1, 0, 0)
        
        # Card 2: Downloader (placeholder futuro)
        card2 = ToolCard(
            "downloader",
            "Downloader",
            "Baixe vídeos e músicas de 10.000+ sites.",
            "#E3F2FD",
            "⬇️"
        )
        card2.clicked.connect(self.tool_selected.emit)
        grid.addWidget(card2, 0, 1)
        
        # Card 3: Compressor (placeholder futuro)
        card3 = ToolCard(
            "compressor",
            "Compressor",
            "Comprima arquivos sem perda de qualidade.",
            "#E8F5E9",
            "📦"
        )
        card3.clicked.connect(self.tool_selected.emit)
        grid.addWidget(card3, 0, 2)
        
        return container
    
    def _create_secondary_tools(self) -> QWidget:
        """Cria linha de ferramentas secundárias."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setSpacing(12)
        
        tools = [
            ("Editor", "✂️"),
            ("Screen Recorder", "📹"),
            ("DVD Burner", "💿"),
            ("Player", "▶️"),
            ("Fix Media Metadata", "🏷️"),
        ]
        
        for title, icon in tools:
            btn = SmallToolButton(title, icon)
            layout.addWidget(btn)
        
        # Botão "Ver Mais"
        more_btn = SmallToolButton("Mais", "»")
        more_btn.setMaximumWidth(80)
        layout.addWidget(more_btn)
        
        return container
    
    def _create_ai_lab_section(self) -> QWidget:
        """Cria a seção AI Lab com ferramentas de IA."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(15)
        
        # Título da seção
        header_layout = QHBoxLayout()
        title = QLabel("AI Lab")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setStyleSheet("color: #2C3E50;")
        header_layout.addWidget(title)
        
        # Badge "NEW"
        badge = QLabel("2")
        badge.setFixedSize(24, 24)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet("""
            background: #FF6B6B;
            color: white;
            border-radius: 12px;
            font-weight: bold;
            font-size: 10pt;
        """)
        header_layout.addWidget(badge)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Grid de ferramentas AI
        grid = QGridLayout()
        grid.setSpacing(12)
        
        # Watermark Editor - ATIVO (nossa ferramenta atual)
        watermark_card = ToolCard(
            "watermark_editor",
            "Watermark Editor",
            "Remova marcas d'água de imagens e vídeos",
            "#FFE5B4",
            "💧"
        )
        watermark_card.clicked.connect(self.tool_selected.emit)
        watermark_card.setStyleSheet(watermark_card.styleSheet() + """
            ToolCard {
                border: 2px solid #FF8C00;
            }
        """)
        grid.addWidget(watermark_card, 0, 0)
        
        # Outros cards (placeholders)
        other_tools = [
            ("smart_trimmer", "Smart Trimmer", "Corte inteligente de vídeos", "🎬"),
            ("auto_crop", "Auto Crop", "Recorte automático de imagens", "🖼️"),
            ("subtitle_editor", "Subtitle Editor", "Editor de legendas com IA", "💬"),
            ("vocal_remover", "Vocal Remover", "Remova vocais de músicas", "🎤"),
            ("noise_remover", "Noise Remover", "Remova ruídos de áudio", "🔇"),
            ("bg_remover", "Background Remover", "Remova fundos de imagens", "🎭"),
        ]
        
        row, col = 0, 1
        for tool_id, title, desc, icon in other_tools:
            card = ToolCard(tool_id, title, desc, "#F0F0F0", icon)
            card.clicked.connect(self.tool_selected.emit)
            grid.addWidget(card, row, col)
            col += 1
            if col > 3:
                col = 0
                row += 1
        
        # Botão "All Tools"
        all_tools_btn = SmallToolButton("All Tools  »", "🛠")
        all_tools_btn.setMinimumHeight(80)
        grid.addWidget(all_tools_btn, row, col)
        
        layout.addLayout(grid)
        
        return container


if __name__ == "__main__":
    # Teste standalone
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    dashboard = DashboardWidget()
    dashboard.tool_selected.connect(lambda tool: print(f"Ferramenta selecionada: {tool}"))
    dashboard.resize(1200, 800)
    dashboard.show()
    sys.exit(app.exec())
