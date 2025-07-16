import sys
import os
import numpy as np
import soundfile as sf
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# Pasta raiz onde todas as gravações serão salvas
RECORDINGS_ROOT = "recordings"
os.makedirs(RECORDINGS_ROOT, exist_ok=True)

# Parâmetros da simulação e gravação
FS = 1000             # taxa de amostragem (Hz)
BUFFER_SIZE = 500     # pontos exibidos
UPDATE_INTERVAL_MS = 2
NUM_CANAIS = 3

class AudioPlotWindow(QtWidgets.QWidget):
    def __init__(self, files, folder_name):
        super().__init__()
        # Título com o nome da pasta de onde vieram os arquivos
        self.setWindowTitle(f"MYo_PLoT ({folder_name})")
        layout = QtWidgets.QVBoxLayout(self)
        for fpath in files:
            data, samplerate = sf.read(fpath)
            t = np.arange(len(data)) / samplerate
            pw = pg.PlotWidget(title=os.path.basename(fpath))
            pw.plot(t, data, pen='c')
            pw.setLabel('bottom', 'Tempo', 's')
            pw.setLabel('left', 'Amplitude', '')
            layout.addWidget(pw)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MYo_GRaPH")

        # Buffers e fase para dados sintéticos
        self.buffers = [np.zeros(BUFFER_SIZE) for _ in range(NUM_CANAIS)]
        self.t       = np.linspace(-BUFFER_SIZE/FS, 0, BUFFER_SIZE)
        self.phase   = [0.0] * NUM_CANAIS

        # Widget central e layout
        cw = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(cw)

        # Três gráficos para sinal em tempo real
        self.curves = []
        for i in range(NUM_CANAIS):
            pw = pg.PlotWidget(title=f"Canal {i+1}")
            pw.showGrid(x=True, y=True)
            pw.setLabel('bottom','Tempo','s')
            pw.setLabel('left','Amplitude','V')
            curve = pw.plot(self.t, self.buffers[i], pen='y')
            vbox.addWidget(pw)
            self.curves.append(curve)

        # Campo de duração
        h_dur = QtWidgets.QHBoxLayout()
        h_dur.addWidget(QtWidgets.QLabel("Duração (s):"))
        self.duration_input = QtWidgets.QLineEdit("5")
        self.duration_input.setFixedWidth(60)
        h_dur.addWidget(self.duration_input)
        h_dur.addStretch()
        vbox.addLayout(h_dur)

        # Botões Start / Stop / Record
        hbtn = QtWidgets.QHBoxLayout()
        self.start_btn  = QtWidgets.QPushButton("Start")
        self.stop_btn   = QtWidgets.QPushButton("Stop")
        self.record_btn = QtWidgets.QPushButton("Record")
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)
        hbtn.addWidget(self.start_btn)
        hbtn.addWidget(self.stop_btn)
        hbtn.addWidget(self.record_btn)
        vbox.addLayout(hbtn)

        self.setCentralWidget(cw)

        # Menu flutuante: File → Open file...
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        open_action = QtWidgets.QAction("Open file...", self)
        file_menu.addAction(open_action)
        open_action.triggered.connect(self.open_files)

        # Conecta botões
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.record_btn.clicked.connect(self.start_record)

        # Timer de atualização
        self.timer = QtCore.QTimer()
        self.timer.setInterval(UPDATE_INTERVAL_MS)
        self.timer.timeout.connect(self.update_plots)

        # Estado de gravação
        self.wav_files         = [None] * NUM_CANAIS
        self.recording         = False
        self.samples_to_record = 0
        self.samples_recorded  = 0

    def open_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open WAV files", "", "WAV Files (*.wav)"
        )
        if not files:
            return
        if len(files) > 3:
            QtWidgets.QMessageBox.warning(
                self, "Atenção",
                "Selecione no máximo 3 arquivos. Serão plotados apenas os primeiros 3."
            )
            files = files[:3]

        # Extrai o nome da pasta comum onde estão os arquivos
        common_dir = os.path.commonpath(files)
        folder_name = os.path.basename(common_dir.rstrip(os.sep))

        self.audio_window = AudioPlotWindow(files, folder_name)
        self.audio_window.show()

    def start(self):
        """Inicia plotagem e habilita Stop e Record."""
        self.timer.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.record_btn.setEnabled(True)

    def stop(self):
        """Para plotagem e gravação (se ocorrer)."""
        self.timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)
        if self.recording:
            self.stop_record()

    def start_record(self):
        """Cria nova subpasta em RECORDINGS_ROOT e inicia gravação."""
        if self.recording:
            return
        try:
            secs = float(self.duration_input.text())
            assert secs > 0
        except:
            QtWidgets.QMessageBox.warning(self, "Duração inválida",
                "Informe um número positivo.")
            return

        # encontra próximo índice de pasta disponível
        existing = [
            d for d in os.listdir(RECORDINGS_ROOT)
            if os.path.isdir(os.path.join(RECORDINGS_ROOT, d)) and d.startswith('recording_')
        ]
        indices = [
            int(d.split('_')[1]) for d in existing
            if len(d.split('_')) == 2 and d.split('_')[1].isdigit()
        ]
        next_idx = max(indices) + 1 if indices else 1

        # cria a subpasta para esta gravação
        self.record_dir = os.path.join(RECORDINGS_ROOT, f"recording_{next_idx}")
        os.makedirs(self.record_dir)

        # prepara amostras
        self.samples_to_record = int(secs * FS)
        self.samples_recorded  = 0

        # abre arquivos WAV dentro da nova subpasta
        for i in range(NUM_CANAIS):
            path = os.path.join(self.record_dir, f"canal{i+1}.wav")
            self.wav_files[i] = sf.SoundFile(
                path, mode='w',
                samplerate=FS, channels=1, subtype='PCM_16'
            )

        self.recording = True
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)

    def stop_record(self):
        """Encerra gravação e reabilita Stop e Record."""
        for wf in self.wav_files:
            if wf:
                wf.close()
        self.wav_files = [None] * NUM_CANAIS
        self.recording = False
        self.stop_btn.setEnabled(True)
        self.record_btn.setEnabled(True)

    def update_plots(self):
        """Gera ponto, atualiza gráfico e grava se estiver gravando."""
        for i in range(NUM_CANAIS):
            freq = 1 + i * 0.5
            self.phase[i] += 2 * np.pi * freq / FS
            new_sample = np.sin(self.phase[i]) + 0.1 * np.random.randn()
            buf = np.roll(self.buffers[i], -1)
            buf[-1] = new_sample
            self.buffers[i] = buf
            self.curves[i].setData(self.t, buf)
            if self.recording and self.wav_files[i]:
                self.wav_files[i].write(np.array([new_sample], dtype='float32'))

        if self.recording:
            self.samples_recorded += 1
            if self.samples_recorded >= self.samples_to_record:
                self.stop_record()

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 700)
    win.show()
    sys.exit(app.exec_())
