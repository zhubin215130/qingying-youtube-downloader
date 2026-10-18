"""Qingying — a small Windows desktop app for saving YouTube videos."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QSettings, Qt, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from core import DownloadCancelled, FormatChoice, VideoDetails, download_video, inspect_video, normalize_url


APP_NAME = "清影"


def asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / name


def duration_text(seconds: int | None) -> str:
    if not seconds:
        return "时长未知"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}" if hours else f"{minutes:02d}:{sec:02d}"


class InspectWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, url: str, node_path: Path):
        super().__init__()
        self.url = url
        self.node_path = node_path

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(inspect_video(self.url, self.node_path))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(int)
    stage = Signal(str)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, details: VideoDetails, choice: FormatChoice, folder: Path):
        super().__init__()
        self.details = details
        self.choice = choice
        self.folder = folder
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            result = download_video(
                self.details, self.choice, self.folder,
                asset_path("bin/node.exe"), asset_path("bin/ffmpeg.exe"),
                self.progress.emit, self.stage.emit, self.cancel_event,
            )
            self.succeeded.emit(str(result))
        except DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


STYLESHEET = """
QWidget { background: #0b0f17; color: #ecf3fc; font-family: 'Noto Sans SC'; font-size: 13px; }
QLabel { background: transparent; }
QFrame#card { background: #151c29; border: 1px solid #273247; border-radius: 18px; }
QFrame#videoCard { background: #111c2c; border: 1px solid #2a4161; border-radius: 18px; }
QLabel#brand { font-size: 27px; font-weight: 700; letter-spacing: 1px; }
QLabel#heading { font-size: 21px; font-weight: 650; }
QLabel#section { font-size: 13px; font-weight: 650; color: #dae6f7; }
QLabel#muted { color: #91a0b8; }
QLabel#meta { color: #8fc3ff; font-size: 12px; }
QLabel#videoTitle { font-size: 17px; font-weight: 650; }
QLabel#status { color: #a8b7cb; }
QLabel#logo { background: #2388ff; color: white; border-radius: 13px; font-size: 27px; font-weight: 700; }
QLineEdit, QComboBox { background: #0e1521; border: 1px solid #334158; border-radius: 10px; padding: 11px 13px; selection-background-color: #348dff; }
QLineEdit:focus, QComboBox:focus { border: 1px solid #4da7ff; }
QLineEdit:disabled, QComboBox:disabled { color: #738096; border-color: #263044; }
QComboBox { min-height: 20px; }
QComboBox::drop-down { border: 0; width: 30px; }
QComboBox QAbstractItemView { background: #172233; color: #f1f6ff; border: 1px solid #36506f; selection-background-color: #2d80da; padding: 5px; }
QPushButton { background: #263247; border: 1px solid #37465d; border-radius: 10px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #33445f; }
QPushButton:disabled { color: #69788e; background: #202a3a; border-color: #29364a; }
QPushButton#primary { background: #248bff; border: 1px solid #55a8ff; color: white; font-size: 15px; padding: 13px 20px; }
QPushButton#primary:hover { background: #439dff; }
QPushButton#primary:disabled { background: #244264; border-color: #36516e; color: #9fb3cc; }
QPushButton#subtle { background: transparent; border: 1px solid #35445c; }
QProgressBar { background: #0c1421; border: 1px solid #2c3b51; border-radius: 7px; height: 11px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #2f97ff; border-radius: 6px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("Qingying", "Qingying Downloader")
        self.details: VideoDetails | None = None
        self.last_file: Path | None = None
        self.inspect_thread: QThread | None = None
        self.download_thread: QThread | None = None
        self.inspect_worker: InspectWorker | None = None
        self.download_worker: DownloadWorker | None = None
        self.pending_inspect = False
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(650)
        self.debounce.timeout.connect(self.inspect_link)

        self.setWindowTitle("清影 · YouTube 视频下载")
        self.resize(850, 740)
        self.setMinimumSize(700, 710)
        icon = asset_path("assets/icon.ico")
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(36, 26, 36, 22)
        layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(15)
        logo = QLabel("↓")
        logo.setObjectName("logo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(49, 49)
        header.addWidget(logo)
        heading = QVBoxLayout()
        heading.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setObjectName("brand")
        heading.addWidget(title)
        sub = QLabel("YouTube 视频下载")
        sub.setObjectName("muted")
        heading.addWidget(sub)
        header.addLayout(heading)
        header.addStretch()
        layout.addLayout(header)

        intro = QLabel("粘贴链接，选择清晰度，开始下载")
        intro.setObjectName("heading")
        layout.addWidget(intro)

        link_card = self._card("card")
        link_layout = QVBoxLayout(link_card)
        link_layout.setContentsMargins(22, 19, 22, 21)
        link_layout.setSpacing(12)
        link_label = QLabel("视频链接")
        link_label.setObjectName("section")
        link_layout.addWidget(link_label)
        link_row = QHBoxLayout()
        link_row.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("粘贴 youtube.com/watch 或 youtube.com/shorts 链接")
        self.url_edit.textChanged.connect(self._url_changed)
        self.url_edit.returnPressed.connect(self.inspect_link)
        link_row.addWidget(self.url_edit, 1)
        paste = QPushButton("粘贴链接")
        paste.clicked.connect(self._paste)
        link_row.addWidget(paste)
        link_layout.addLayout(link_row)
        layout.addWidget(link_card)

        video_card = self._card("videoCard")
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(22, 20, 22, 20)
        video_layout.setSpacing(8)
        self.video_caption = QLabel("视频信息")
        self.video_caption.setObjectName("meta")
        video_layout.addWidget(self.video_caption)
        self.video_title = QLabel("等待粘贴链接")
        self.video_title.setObjectName("videoTitle")
        self.video_title.setWordWrap(True)
        video_layout.addWidget(self.video_title)
        self.video_meta = QLabel("支持普通视频和 Shorts · 自动识别可用清晰度")
        self.video_meta.setObjectName("muted")
        video_layout.addWidget(self.video_meta)
        layout.addWidget(video_card)

        choice_card = self._card("card")
        choice_layout = QVBoxLayout(choice_card)
        choice_layout.setContentsMargins(22, 18, 22, 19)
        choice_layout.setSpacing(10)
        quality_label = QLabel("下载清晰度")
        quality_label.setObjectName("section")
        choice_layout.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.setEnabled(False)
        self.quality_combo.addItem("解析视频后显示可用清晰度")
        choice_layout.addWidget(self.quality_combo)
        folder_label = QLabel("保存位置")
        folder_label.setObjectName("section")
        choice_layout.addWidget(folder_label)
        folder_row = QHBoxLayout()
        folder_row.setSpacing(10)
        initial_folder = str(self.settings.value("download_folder", str(Path.home() / "Downloads")))
        self.folder_edit = QLineEdit(initial_folder)
        folder_row.addWidget(self.folder_edit, 1)
        browse = QPushButton("选择文件夹")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(browse)
        choice_layout.addLayout(folder_row)
        layout.addWidget(choice_card)

        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        self.download_button = QPushButton("↓  下载视频")
        self.download_button.setObjectName("primary")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._start_download)
        action_row.addWidget(self.download_button, 1)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setObjectName("subtle")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_download)
        action_row.addWidget(self.cancel_button)
        layout.addLayout(action_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        footer = QHBoxLayout()
        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.open_button = QPushButton("打开文件夹  ↗")
        self.open_button.setObjectName("subtle")
        self.open_button.setVisible(False)
        self.open_button.clicked.connect(self._open_folder)
        footer.addWidget(self.open_button)
        layout.addLayout(footer)
        layout.addStretch(1)

    @staticmethod
    def _card(name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(name)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return card

    def _paste(self) -> None:
        self.url_edit.setText(QApplication.clipboard().text().strip())
        self.inspect_link()

    def _url_changed(self) -> None:
        self.details = None
        self.download_button.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.quality_combo.clear()
        self.quality_combo.addItem("解析视频后显示可用清晰度")
        self.open_button.setVisible(False)
        self.debounce.start() if self.url_edit.text().strip() else self.debounce.stop()

    def inspect_link(self) -> None:
        self.debounce.stop()
        if self.download_thread and self.download_thread.isRunning():
            return
        try:
            url = normalize_url(self.url_edit.text())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        if self.inspect_thread and self.inspect_thread.isRunning():
            self.pending_inspect = True
            return
        self.pending_inspect = False
        self.video_title.setText("正在读取视频信息…")
        self.video_meta.setText("请稍候")
        self.status_label.setText("正在获取可用清晰度…")
        thread = QThread(self)
        worker = InspectWorker(url, asset_path("bin/node.exe"))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.succeeded.connect(self._inspect_success)
        worker.failed.connect(self._inspect_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._inspect_thread_finished)
        self.inspect_thread = thread
        self.inspect_worker = worker
        thread.start()

    def _inspect_thread_finished(self) -> None:
        self.inspect_thread = None
        self.inspect_worker = None
        if self.pending_inspect:
            QTimer.singleShot(0, self.inspect_link)

    def _inspect_success(self, details: VideoDetails) -> None:
        try:
            if details.url != normalize_url(self.url_edit.text()):
                self.pending_inspect = True
                return
        except ValueError:
            return
        self.details = details
        self.video_title.setText(details.title)
        self.video_meta.setText(f"{details.channel}   ·   {duration_text(details.duration)}")
        self.quality_combo.clear()
        default_index = 0
        for index, choice in enumerate(details.choices):
            self.quality_combo.addItem(choice.label, choice)
            if choice.quality == 1440:
                default_index = index
        self.quality_combo.setCurrentIndex(default_index)
        self.quality_combo.setEnabled(True)
        self.download_button.setEnabled(True)
        if any(choice.quality == 1440 for choice in details.choices):
            self.status_label.setText("已选中 1440p；也可以选择其他画质。")
        else:
            self.status_label.setText("该视频未提供 1440p；已选中可用的最高画质。")

    def _inspect_failed(self, message: str) -> None:
        self.video_title.setText("无法读取视频")
        self.video_meta.setText("请检查链接或网络连接")
        self.status_label.setText(self._clean_error(message))

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择保存位置", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _start_download(self) -> None:
        if not self.details:
            return
        choice = self.quality_combo.currentData()
        if not isinstance(choice, FormatChoice):
            return
        text = self.folder_edit.text().strip()
        if not text:
            QMessageBox.warning(self, APP_NAME, "请选择保存位置。")
            return
        folder = Path(text).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"无法使用此文件夹：{exc}")
            return
        self.settings.setValue("download_folder", str(folder))
        self.url_edit.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.download_button.setEnabled(False)
        self.cancel_button.setVisible(True)
        self.open_button.setVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在连接 YouTube…")
        thread = QThread(self)
        worker = DownloadWorker(self.details, choice, folder)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self.progress_bar.setValue)
        worker.stage.connect(self.status_label.setText)
        worker.succeeded.connect(self._download_success)
        worker.failed.connect(self._download_failed)
        worker.cancelled.connect(self._download_cancelled)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._download_thread_finished)
        self.download_thread = thread
        self.download_worker = worker
        thread.start()

    def _cancel_download(self) -> None:
        if self.download_worker:
            self.download_worker.cancel_event.set()
            self.status_label.setText("正在取消…")
            self.cancel_button.setEnabled(False)

    def _download_success(self, path: str) -> None:
        self.last_file = Path(path)
        self.status_label.setText(f"下载完成 · {self.last_file.name}")
        self.progress_bar.setValue(100)
        self.open_button.setVisible(True)

    def _download_failed(self, message: str) -> None:
        self.status_label.setText("下载失败 · " + self._clean_error(message))

    def _download_cancelled(self) -> None:
        self.status_label.setText("已取消下载。再次下载可继续未完成的文件。")

    def _download_thread_finished(self) -> None:
        self.download_thread = None
        self.download_worker = None
        self.url_edit.setEnabled(True)
        self.quality_combo.setEnabled(self.details is not None)
        self.download_button.setEnabled(self.details is not None)
        self.cancel_button.setEnabled(True)
        self.cancel_button.setVisible(False)

    def _open_folder(self) -> None:
        if self.last_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_file.parent)))

    @staticmethod
    def _clean_error(message: str) -> str:
        text = message.replace("ERROR: ", "").strip()
        return text[:240] + ("…" if len(text) > 240 else "")

    def closeEvent(self, event) -> None:
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.information(self, APP_NAME, "下载进行中。请先取消下载，再关闭窗口。")
            event.ignore()
            return
        if self.inspect_thread and self.inspect_thread.isRunning():
            self.status_label.setText("正在读取视频信息，请稍候再关闭。")
            event.ignore()
            return
        event.accept()


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        output = Path(sys.argv[2])
        try:
            details = inspect_video(sys.argv[3], asset_path("bin/node.exe"))
            output.write_text(json.dumps({
                "title": details.title,
                "choices": [choice.label for choice in details.choices],
            }, ensure_ascii=False), encoding="utf-8")
            return 0
        except Exception as exc:
            output.write_text(json.dumps({"error": str(exc)}, ensure_ascii=False), encoding="utf-8")
            return 1
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Qingying")
    app.setStyle("Fusion")
    font_id = QFontDatabase.addApplicationFont(str(asset_path("assets/NotoSansSC.ttf")))
    if font_id >= 0:
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
