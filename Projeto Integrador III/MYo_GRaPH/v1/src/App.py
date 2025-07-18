import sys
import os
import numpy as np
import soundfile as sf
import serial
from collections import deque
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# -- Configuração Serial e Parâmetros Gerais --
SERIAL_PORT = "COM7"      # Ajuste para sua porta, ex. "/dev/ttyUSB0"
BAUDRATE = 115200
FS = 1000                 # taxa de amostragem esperada (Hz)
BUFFER_SIZE = 500         # janela deslizante
PLOT_INTERVAL_MS = 20     # redesenho em ms
NUM_CANAIS = 3            # máximo suportado pelo ESP32
RECORDINGS_ROOT = "recordings"

# Garante existência do diretório de gravações
os.makedirs(RECORDINGS_ROOT, exist_ok=True)


class SerialReader(QtCore.QThread):
    newData = QtCore.pyqtSignal(list)

    def __init__(self, port, baud):
        super().__init__()
        self.ser = serial.Serial(port, baud, timeout=1)
        self._running = True

    def run(self):
        while self._running:
            try:
                raw = self.ser.readline()
                line = raw.decode('ascii', errors='ignore').strip()
            except (serial.SerialException, PermissionError, OSError):
                continue
            if not line:
                continue
            parts = line.split('\t')[:NUM_CANAIS]
            try:
                vals = [float(v) for v in parts]
                self.newData.emit(vals)
            except ValueError:
                continue

    def stop(self):
        self._running = False
        self.wait()
        self.ser.close()


class AudioPlotWindow(QtWidgets.QWidget):
    def __init__(self, files, folder_name):
        super().__init__()
        self.setWindowTitle(f"MYo_PLoT ({folder_name})")
        layout = QtWidgets.QVBoxLayout(self)
        for f in files:
            data, sr = sf.read(f)
            t = np.arange(len(data)) / sr
            pw = pg.PlotWidget(title=os.path.basename(f))
            pw.plot(t, data, pen='b')
            pw.setLabel('bottom', 'Tempo (s)')
            pw.setLabel('left', 'Amplitude')
            layout.addWidget(pw)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MYo_GRaPH")
        self.dark_mode = False
        self.audio_windows = []

        # Buffers circulares e eixo de tempo
        self.buffers = [deque([0.0] * BUFFER_SIZE, maxlen=BUFFER_SIZE)
                        for _ in range(NUM_CANAIS)]
        self.t = np.linspace(-BUFFER_SIZE/FS, 0, BUFFER_SIZE)

        # Thread serial
        try:
            self.reader = SerialReader(SERIAL_PORT, BAUDRATE)
        except serial.SerialException as e:
            QtWidgets.QMessageBox.critical(self, "Erro Serial", str(e))
            sys.exit(1)
        self.reader.newData.connect(self.onSerialData)
        self.reader.start()
        self.ser = self.reader.ser

        # UI principal
        cw = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(cw)

        # Configurações iniciais
        cfg = QtWidgets.QHBoxLayout()
        cfg.addWidget(QtWidgets.QLabel("Canais:"))
        self.channel_spin = QtWidgets.QSpinBox()
        self.channel_spin.setRange(1, NUM_CANAIS)
        self.channel_spin.setValue(NUM_CANAIS)
        cfg.addWidget(self.channel_spin)
        cfg.addSpacing(20)
        self.dc_checkbox = QtWidgets.QCheckBox("Remove DC")
        cfg.addWidget(self.dc_checkbox)
        cfg.addSpacing(20)
        # Campo para duração em segundos, sem valores negativos
        cfg.addWidget(QtWidgets.QLabel("Duration (s):"))
        self.duration_spin = QtWidgets.QSpinBox()
        self.duration_spin.setRange(0, 10000)  # permite de 0 até 10000 segundos
        self.duration_spin.setValue(3)  # valor inicial agora 3 segundos
        cfg.addWidget(self.duration_spin)
        cfg.addStretch()
        vbox.addLayout(cfg)

        # Área de plots
        self.plotWidgets = []
        self.curves = []
        for i in range(NUM_CANAIS):
            pw = pg.PlotWidget(title=f"Canal {i+1}")
            pw.showGrid(x=True, y=True)
            pw.setLabel('bottom', 'Tempo', 's')
            pw.setLabel('left', 'Amplitude', 'V')
            pw.getAxis('bottom').setStyle(showValues=False)
            pw.setBackground('w')
            curve = pw.plot(self.t, list(self.buffers[i]), pen='b')
            vbox.addWidget(pw, 1)
            self.plotWidgets.append(pw)
            self.curves.append(curve)

        # Botões
        btns = QtWidgets.QHBoxLayout()
        self.start_btn  = QtWidgets.QPushButton("Start")
        self.stop_btn   = QtWidgets.QPushButton("Stop")
        self.record_btn = QtWidgets.QPushButton("Record")
        self.mode_btn   = QtWidgets.QPushButton("Dark Mode")

        # estados iniciais
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)

        for w in (self.start_btn, self.stop_btn, self.record_btn, self.mode_btn):
            btns.addWidget(w)
        vbox.addLayout(btns)

        self.setCentralWidget(cw)

        # Menu para abrir WAV
        mb = self.menuBar()
        fm = mb.addMenu("File")
        act = QtWidgets.QAction("Open WAV...", self)
        fm.addAction(act)
        act.triggered.connect(self.open_files)

        # Conexões de sinal
        self.channel_spin.valueChanged.connect(self.changeChannels)
        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)
        self.record_btn.clicked.connect(self.record)
        self.mode_btn.clicked.connect(self.toggleMode)

        # Timer de atualização
        self.plot_timer = QtCore.QTimer()
        self.plot_timer.setInterval(PLOT_INTERVAL_MS)
        self.plot_timer.timeout.connect(self.redrawPlots)

    def open_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Open WAV files", RECORDINGS_ROOT, "WAV Files (*.wav)"
        )
        if not files:
            return
        name = os.path.basename(os.path.commonpath(files).rstrip(os.sep))
        win = AudioPlotWindow(files, name)
        self.audio_windows.append(win)
        win.show()

    def changeChannels(self, n):
        self.ser.reset_input_buffer()
        self.ser.write(f"{n}\n".encode())
        for i, pw in enumerate(self.plotWidgets):
            self.buffers[i].clear()
            self.buffers[i].extend([0.0] * BUFFER_SIZE)
            pw.setVisible(i < n)

    def start(self):
        self.changeChannels(self.channel_spin.value())
        self.plot_timer.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.record_btn.setEnabled(True)

    def stop(self):
        self.plot_timer.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.record_btn.setEnabled(False)

    def record(self):
        # Desabilita Start e Stop ao iniciar gravação
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        # Aqui você pode usar self.duration_spin.value() para definir a duração

    @QtCore.pyqtSlot(list)
    def onSerialData(self, vals):
        for i, v in enumerate(vals):
            self.buffers[i].append(v)

    def redrawPlots(self):
        vis = [i for i, pw in enumerate(self.plotWidgets) if pw.isVisible()]
        if not vis:
            return
        processed = []
        for i in vis:
            data = np.array(self.buffers[i])
            if self.dc_checkbox.isChecked():
                data = data - data.mean()
            processed.append(data)
        all_data = np.hstack(processed)
        y0, y1 = all_data.min(), all_data.max()
        for idx, i in enumerate(vis):
            self.plotWidgets[i].setYRange(y0, y1)
            self.curves[i].setData(self.t, processed[idx])

    def toggleMode(self):
        self.dark_mode = not self.dark_mode
        bg = 'k' if self.dark_mode else 'w'
        axisColor = 'w' if self.dark_mode else 'k'
        for pw in self.plotWidgets:
            pw.setBackground(bg)
            ax0 = pw.getAxis('bottom')
            ax1 = pw.getAxis('left')
            ax0.setPen(axisColor); ax0.setTextPen(axisColor)
            ax1.setPen(axisColor); ax1.setTextPen(axisColor)
        self.mode_btn.setText("Light Mode" if self.dark_mode else "Dark Mode")

    def closeEvent(self, event):
        self.reader.stop()
        super().closeEvent(event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 700)
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
