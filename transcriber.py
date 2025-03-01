import os
import sys
import time
from pathlib import Path
import tempfile
from queue import Queue, Empty
import whisper
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                             QTextEdit, QVBoxLayout, QWidget, QFileDialog, 
                             QTableWidget, QTableWidgetItem, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import warnings

# Supported media extensions
MEDIA_EXTENSIONS = ['.mp3', '.wav', '.mp4', '.mkv', '.mov', '.flv', '.aac', '.m4a']

# --- Thread for Directory Monitoring ---
class FileMonitor(QThread):
    new_file_detected = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.observer = Observer()
        self.event_handler = MediaFileHandler(self)

    def run(self):
        self.observer.schedule(self.event_handler, self.directory, recursive=True)
        self.observer.start()
        self.log_message.emit(f"Started monitoring directory: {self.directory}")
        while not self.isInterruptionRequested():
            self.sleep(1)
        self.observer.stop()
        self.observer.join()
        self.log_message.emit("Stopped monitoring")

    def stop(self):
        self.requestInterruption()

class MediaFileHandler(FileSystemEventHandler):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def on_created(self, event):
        if not event.is_directory:
            file_path = Path(event.src_path)
            if file_path.suffix.lower() in MEDIA_EXTENSIONS:
                self.parent.new_file_detected.emit(str(file_path))
                self.parent.log_message.emit(f"Detected new file: {file_path}")

# --- Thread for Transcription ---
class TranscriptionWorker(QThread):
    transcription_started = pyqtSignal(str)
    transcription_finished = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(self, queue, model):
        super().__init__()
        self.queue = queue
        self.model = model
        self.is_stopped = False

    def run(self):
        while not self.is_stopped:
            try:
                file_path = self.queue.get(timeout=1)
                self.transcription_started.emit(file_path)
                self.log_message.emit(f"Started transcribing {file_path}")
                result = self.model.transcribe(file_path)
                transcription_path = Path(file_path).parent / (Path(file_path).name + '.txt')
                fd, temp_path = tempfile.mkstemp(dir=Path(file_path).parent, suffix='.txt')
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(result["text"])
                os.replace(temp_path, transcription_path)
                self.transcription_finished.emit(file_path)
                self.log_message.emit(f"Finished transcribing {file_path}")
                self.queue.task_done()
            except Empty:
                continue

    def stop(self):
        self.is_stopped = True

# --- Main GUI Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transcription System")
        self.setGeometry(100, 100, 800, 600)

        # Apply futuristic stylesheet
        self.setStyleSheet("""
            QMainWindow { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #1a1a2e, stop:1 #16213e);  /* Dark blue-purple gradient */
    }
    QLabel { 
        color: #b0e0e6;  /* Powder blue for status label */
        background: transparent; 
        font: bold 12px; 
    }
    QTableWidget { 
        background-color: #252540;  /* Darker blue-gray for table */
        color: #f0f0f5;  /* Off-white for table text */
        border: 1px solid #404075;  /* Subtle purple-blue border */
        font: 11px; 
    }
    QTextEdit { 
        background-color: #252540; 
        color: #f0f0f5;  /* Off-white for log text */
        border: 1px solid #404075; 
        font: 11px; 
    }
    QPushButton#dirButton { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #ff6f61, stop:1 #de4839);  /* Coral-to-red gradient */
        color: #ffffff;  /* White text */
        border: 2px solid #ff8c80;  /* Light coral border */
        border-radius: 8px; 
        padding: 6px; 
        font: bold 14px; 
    }
    QPushButton#dirButton:hover { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #ff8c80, stop:1 #ff6f61);  /* Reverse gradient on hover */
        border: 2px solid #ffffff; 
    }
    QPushButton#startStopButton { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #4facfe, stop:1 #00f2fe);  /* Sky blue-to-cyan gradient */
        color: #ffffff;  /* White text */
        border: 2px solid #80d4ff;  /* Light blue border */
        border-radius: 8px; 
        padding: 6px; 
        font: bold 14px; 
    }
    QPushButton#startStopButton:hover { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #80d4ff, stop:1 #4facfe);  
        border: 2px solid #ffffff; 
    }
    QProgressBar { 
        background-color: #252540; 
        border: 1px solid #404075; 
        text-align: center; 
        color: #b0e0e6; 
        font: bold 12px; 
    }
    QProgressBar::chunk { 
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                                    stop:0 #ffcc00, stop:1 #ff9900); 
        border-radius: 3px; 
    }
        """)

        # Load Whisper model and initialize queue
        self.model = whisper.load_model("base")
        self.queue = Queue()  # Initialize queue here
        self.file_monitor = None
        self.transcription_worker = None
        self.is_monitoring = False
        self.directory = None

        # Widgets
        self.dir_button = QPushButton("Select Directory")
        self.dir_button.setObjectName("dirButton")
        self.start_stop_button = QPushButton("Start Monitoring")
        self.start_stop_button.setObjectName("startStopButton")
        self.status_label = QLabel("Status: Idle")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(2)
        self.file_table.setHorizontalHeaderLabels(["File Name", "Status"])
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.dir_button)
        layout.addWidget(self.start_stop_button)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.file_table)
        layout.addWidget(self.log_viewer)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Connect buttons
        self.dir_button.clicked.connect(self.select_directory)
        self.start_stop_button.clicked.connect(self.toggle_monitoring)

    def add_file_to_queue(self, file_path):
        transcription_path = Path(file_path).parent / (Path(file_path).name + '.txt')
        if not transcription_path.exists():
            self.queue.put(file_path)
            row = self.file_table.rowCount()
            self.file_table.insertRow(row)
            item = QTableWidgetItem(os.path.basename(file_path))
            item.setData(Qt.UserRole, file_path)
            self.file_table.setItem(row, 0, item)
            self.file_table.setItem(row, 1, QTableWidgetItem("Waiting"))
            self.update_status()
        else:
            self.log_message(f"Skipped {file_path} - already transcribed")

    def select_directory(self):
        self.directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if self.directory:
            self.log_message(f"Selected directory: {self.directory}")
            # Process existing files immediately
            self.process_existing_files()

    def process_existing_files(self):
        """Process all existing media files in the directory."""
        media_files = []
        for path in Path(self.directory).rglob('*'):
            if path.suffix.lower() in MEDIA_EXTENSIONS:
                media_files.append(str(path))
        for file_path in media_files:
            self.add_file_to_queue(file_path)

    def toggle_monitoring(self):
        if self.is_monitoring:
            self.file_monitor.stop()
            self.transcription_worker.stop()
            self.start_stop_button.setText("Start Monitoring")
            self.dir_button.setEnabled(True)
            self.is_monitoring = False
            self.status_label.setText("Status: Idle")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
        else:
            if not self.directory:
                QMessageBox.warning(self, "No Directory", "Please select a directory first.")
                return
            # Use the existing queue (no reassignment here)
            self.file_monitor = FileMonitor(self.directory)
            self.file_monitor.new_file_detected.connect(self.add_file_to_queue)
            self.file_monitor.log_message.connect(self.log_message)
            self.transcription_worker = TranscriptionWorker(self.queue, self.model)
            self.transcription_worker.transcription_started.connect(self.on_transcription_started)
            self.transcription_worker.transcription_finished.connect(self.on_transcription_finished)
            self.transcription_worker.log_message.connect(self.log_message)
            self.file_monitor.start()
            self.transcription_worker.start()
            self.start_stop_button.setText("Stop Monitoring")
            self.dir_button.setEnabled(False)
            self.is_monitoring = True

    def add_file_to_queue(self, file_path):
        self.queue.put(file_path)
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        item = QTableWidgetItem(os.path.basename(file_path))
        item.setData(Qt.UserRole, file_path)
        self.file_table.setItem(row, 0, item)
        self.file_table.setItem(row, 1, QTableWidgetItem("Waiting"))
        self.update_status()

    def on_transcription_started(self, file_path):
        self.update_file_status(file_path, "Transcribing")
        self.status_label.setText(f"Status: Transcribing {os.path.basename(file_path)}")
        self.progress_bar.setRange(0, 0)  # Indeterminate mode

    def on_transcription_finished(self, file_path):
        self.update_file_status(file_path, "Done")
        if self.queue.empty():
            self.status_label.setText("Status: Idle")
            self.progress_bar.setRange(0, 1)
            self.progress_bar.setValue(0)
        else:
            self.status_label.setText(f"Status: Queue: {self.queue.qsize()} files waiting")

    def update_file_status(self, file_path, status):
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item and item.data(Qt.UserRole) == file_path:
                self.file_table.setItem(row, 1, QTableWidgetItem(status))
                break

    def update_status(self):
        if self.queue.qsize() > 0 and not any(
            self.file_table.item(row, 1).text() == "Transcribing"
            for row in range(self.file_table.rowCount())
        ):
            self.status_label.setText(f"Status: Queue: {self.queue.qsize()} files waiting")

    def log_message(self, message):
        self.log_viewer.append(message)

    def closeEvent(self, event):
        if self.is_monitoring:
            self.file_monitor.stop()
            self.transcription_worker.stop()
            self.file_monitor.wait()
            self.transcription_worker.wait()
        event.accept()

# --- Run the Application ---
if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=UserWarning)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())