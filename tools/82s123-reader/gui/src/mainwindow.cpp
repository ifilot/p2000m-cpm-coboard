#include "mainwindow.h"
#include "romreader.h"
#include "firmwareflasher.h"

#include <QComboBox>
#include <QPushButton>
#include <QTableWidget>
#include <QHeaderView>
#include <QPlainTextEdit>
#include <QLabel>
#include <QDockWidget>
#include <QStatusBar>
#include <QMenuBar>
#include <QFileDialog>
#include <QFileInfo>
#include <QMessageBox>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QWidget>
#include <QSerialPortInfo>
#include <QFile>
#include <QTextStream>
#include <QDateTime>
#include <QAction>
#include <QProgressDialog>
#include <QSettings>
#include <QApplication>

namespace {

QString hex2(uint8_t v)
{
    return QStringLiteral("%1").arg(v, 2, 16, QLatin1Char('0')).toUpper();
}

} // namespace

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , m_reader(new RomReader(this))
    , m_flasher(new FirmwareFlasher(this))
{
    buildUi();

    connect(m_reader, &RomReader::connected, this, &MainWindow::onConnected);
    connect(m_reader, &RomReader::disconnected, this, &MainWindow::onDisconnected);
    connect(m_reader, &RomReader::connectionFailed, this, &MainWindow::onConnectionFailed);
    connect(m_reader, &RomReader::romReadStarted, this, &MainWindow::onRomReadStarted);
    connect(m_reader, &RomReader::romReadFinished, this, &MainWindow::onRomReadFinished);
    connect(m_reader, &RomReader::romReadFailed, this, &MainWindow::onRomReadFailed);
    connect(m_reader, &RomReader::logMessage, this, &MainWindow::onLogMessage);

    connect(m_flasher, &FirmwareFlasher::outputLine, this, &MainWindow::onFlashOutputLine);
    connect(m_flasher, &FirmwareFlasher::finished, this, &MainWindow::onFlashFinished);

    // Recall a previously located arduino-cli, otherwise try to find one.
    QSettings settings;
    QString cliPath = settings.value(QStringLiteral("arduinoCli/path")).toString();
    if (cliPath.isEmpty() || !QFileInfo::exists(cliPath))
        cliPath = FirmwareFlasher::autoDetectArduinoCli();
    m_flasher->setArduinoCliPath(cliPath);

    refreshPorts();
    setConnectedUiState(false);

    setWindowTitle(tr("82S123 ROM Reader"));
    resize(760, 600);
}

void MainWindow::buildUi()
{
    auto *central = new QWidget(this);
    auto *mainLayout = new QVBoxLayout(central);

    // --- Connection group ---------------------------------------------
    auto *connGroup = new QGroupBox(tr("Connection"), central);
    auto *connLayout = new QHBoxLayout(connGroup);

    m_portCombo = new QComboBox(connGroup);
    m_portCombo->setMinimumWidth(220);
    m_refreshButton = new QPushButton(tr("Refresh"), connGroup);
    m_connectButton = new QPushButton(tr("Connect"), connGroup);

    connLayout->addWidget(new QLabel(tr("Port:"), connGroup));
    connLayout->addWidget(m_portCombo, 1);
    connLayout->addWidget(m_refreshButton);
    connLayout->addWidget(m_connectButton);

    mainLayout->addWidget(connGroup);

    // --- Actions ---------------------------------------------------------
    auto *actionsLayout = new QHBoxLayout();
    m_readButton = new QPushButton(tr("Read ROM"), central);
    m_saveButton = new QPushButton(tr("Save As…"), central);
    m_flashButton = new QPushButton(tr("Flash Firmware…"), central);
    actionsLayout->addWidget(m_readButton);
    actionsLayout->addWidget(m_saveButton);
    actionsLayout->addStretch(1);
    actionsLayout->addWidget(m_flashButton);
    mainLayout->addLayout(actionsLayout);

    // --- Data table --------------------------------------------------
    m_table = new QTableWidget(32, 5, central);
    m_table->setHorizontalHeaderLabels({tr("Address"), tr("Hex"), tr("Decimal"), tr("Binary"), tr("ASCII")});
    m_table->verticalHeader()->setVisible(false);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setSelectionMode(QAbstractItemView::SingleSelection);
    m_table->setAlternatingRowColors(true);
    m_table->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);

    for (int row = 0; row < 32; ++row) {
        auto *addrItem = new QTableWidgetItem(QStringLiteral("0x%1").arg(hex2(static_cast<uint8_t>(row))));
        addrItem->setTextAlignment(Qt::AlignCenter);
        m_table->setItem(row, 0, addrItem);
        for (int col = 1; col < 5; ++col) {
            auto *item = new QTableWidgetItem(QStringLiteral("–"));
            item->setTextAlignment(Qt::AlignCenter);
            m_table->setItem(row, col, item);
        }
    }

    mainLayout->addWidget(m_table, 1);

    setCentralWidget(central);

    // --- Log dock (hidden by default) ---------------------------------
    m_log = new QPlainTextEdit(this);
    m_log->setReadOnly(true);
    m_log->setMaximumBlockCount(2000);
    m_logDock = new QDockWidget(tr("Log"), this);
    m_logDock->setWidget(m_log);
    addDockWidget(Qt::BottomDockWidgetArea, m_logDock);
    m_logDock->setVisible(false);

    // --- Menu ------------------------------------------------------------
    auto *fileMenu = menuBar()->addMenu(tr("&File"));
    QAction *saveAction = fileMenu->addAction(tr("&Save As…"), this, &MainWindow::saveData);
    saveAction->setShortcut(QKeySequence::Save);
    fileMenu->addSeparator();
    fileMenu->addAction(tr("E&xit"), this, &QWidget::close);

    auto *firmwareMenu = menuBar()->addMenu(tr("F&irmware"));
    m_flashAction = firmwareMenu->addAction(tr("&Flash Firmware…"), this, &MainWindow::flashFirmware);
    firmwareMenu->addAction(tr("&Locate arduino-cli…"), this, &MainWindow::locateArduinoCli);

    auto *viewMenu = menuBar()->addMenu(tr("&View"));
    QAction *logAction = m_logDock->toggleViewAction();
    logAction->setText(tr("Show &Log"));
    viewMenu->addAction(logAction);

    auto *helpMenu = menuBar()->addMenu(tr("&Help"));
    helpMenu->addAction(tr("&About"), this, &MainWindow::showAbout);

    // --- Status bar --------------------------------------------------
    m_connectionStatusLabel = new QLabel(tr("Disconnected"), this);
    m_lastReadLabel = new QLabel(tr("No data read yet"), this);
    statusBar()->addWidget(m_connectionStatusLabel, 1);
    statusBar()->addPermanentWidget(m_lastReadLabel);

    connect(m_refreshButton, &QPushButton::clicked, this, &MainWindow::refreshPorts);
    connect(m_connectButton, &QPushButton::clicked, this, &MainWindow::toggleConnection);
    connect(m_readButton, &QPushButton::clicked, this, &MainWindow::startRead);
    connect(m_saveButton, &QPushButton::clicked, this, &MainWindow::saveData);
    connect(m_flashButton, &QPushButton::clicked, this, &MainWindow::flashFirmware);
}

void MainWindow::refreshPorts()
{
    const QString current = m_portCombo->currentData().toString();
    m_portCombo->clear();

    const auto ports = QSerialPortInfo::availablePorts();
    for (const QSerialPortInfo &info : ports) {
        QString label = info.portName();
        if (!info.description().isEmpty())
            label += QStringLiteral(" (%1)").arg(info.description());
        m_portCombo->addItem(label, info.portName());
    }
    if (ports.isEmpty())
        m_portCombo->addItem(tr("No ports found"), QString());

    const int idx = m_portCombo->findData(current);
    if (idx >= 0)
        m_portCombo->setCurrentIndex(idx);
}

void MainWindow::toggleConnection()
{
    if (m_reader->isConnected()) {
        m_reader->disconnectFromPort();
        return;
    }

    const QString port = m_portCombo->currentData().toString();
    if (port.isEmpty()) {
        QMessageBox::warning(this, tr("No Port Selected"), tr("Please select a valid serial port."));
        return;
    }

    m_connectButton->setEnabled(false);
    m_connectionStatusLabel->setText(tr("Connecting to %1…").arg(port));
    m_reader->connectToPort(port);
}

void MainWindow::startRead()
{
    m_reader->readRom();
}

void MainWindow::saveData()
{
    if (!m_hasData) {
        QMessageBox::information(this, tr("No Data"), tr("Read the ROM before saving."));
        return;
    }

    const QString binFilter = tr("Binary file (*.bin)");
    const QString hexFilter = tr("Intel HEX file (*.hex)");
    const QString txtFilter = tr("Text dump (*.txt)");
    QString selectedFilter = binFilter;

    const QString fileName = QFileDialog::getSaveFileName(
        this, tr("Save ROM Data"), QStringLiteral("82s123_dump.bin"),
        QStringList{binFilter, hexFilter, txtFilter}.join(QStringLiteral(";;")),
        &selectedFilter);

    if (fileName.isEmpty())
        return;

    QFile file(fileName);
    const auto mode = QIODevice::WriteOnly |
        (selectedFilter == binFilter ? QIODevice::NotOpen : QIODevice::Text);
    if (!file.open(mode)) {
        QMessageBox::critical(this, tr("Save Failed"),
                               tr("Could not open file for writing:\n%1").arg(file.errorString()));
        return;
    }

    if (selectedFilter == binFilter) {
        file.write(reinterpret_cast<const char *>(m_data.data()), static_cast<qint64>(m_data.size()));
    } else if (selectedFilter == hexFilter) {
        // Single Intel HEX data record covering all 32 bytes at address 0,
        // followed by the end-of-file record.
        QTextStream out(&file);
        uint16_t sum = 32 + 0x00 + 0x00 + 0x00; // byte count + addr hi/lo + record type
        QString line = QStringLiteral(":20000000");
        for (uint8_t b : m_data) {
            line += hex2(b);
            sum += b;
        }
        const uint8_t checksum = static_cast<uint8_t>((~sum + 1) & 0xFF);
        line += hex2(checksum);
        out << line << '\n' << QStringLiteral(":00000001FF") << '\n';
    } else {
        QTextStream out(&file);
        out << tr("Address | Hex | Decimal | Binary   | ASCII") << '\n';
        out << QStringLiteral("--------+-----+---------+----------+------") << '\n';
        for (int row = 0; row < 32; ++row) {
            const uint8_t value = m_data[static_cast<size_t>(row)];
            const QChar ch = (value >= 32 && value < 127) ? QChar(value) : QChar(QLatin1Char('.'));
            out << QStringLiteral("0x%1    | 0x%2 | %3       | %4 | %5")
                       .arg(hex2(static_cast<uint8_t>(row)), hex2(value))
                       .arg(value, 3)
                       .arg(value, 8, 2, QLatin1Char('0'))
                       .arg(ch)
                << '\n';
        }
    }

    file.close();
    appendLog(tr("Saved ROM data to %1").arg(fileName));
    statusBar()->showMessage(tr("Saved to %1").arg(fileName), 4000);
}

void MainWindow::showAbout()
{
    QMessageBox::about(this, tr("About 82S123 ROM Reader"),
        tr("<b>82S123 ROM Reader</b> v%1<br><br>"
           "A Qt6 front-end for the Arduino Leonardo based 82S123 PROM reader.<br>"
           "Reads all 32 bytes over a checksummed serial command protocol.<br><br>"
           "Bundled firmware version: %2")
            .arg(QApplication::applicationVersion(), FirmwareFlasher::embeddedFirmwareVersion()));
}

bool MainWindow::ensureArduinoCliPath()
{
    if (!m_flasher->arduinoCliPath().isEmpty() && QFileInfo::exists(m_flasher->arduinoCliPath()))
        return true;

    QMessageBox::information(this, tr("Locate arduino-cli"),
        tr("Flashing firmware requires the Arduino CLI tool (arduino-cli), which could "
           "not be found automatically. Please select the arduino-cli executable."));

    const QString path = QFileDialog::getOpenFileName(this, tr("Locate arduino-cli"));
    if (path.isEmpty() || !QFileInfo::exists(path))
        return false;

    m_flasher->setArduinoCliPath(path);
    QSettings settings;
    settings.setValue(QStringLiteral("arduinoCli/path"), path);
    return true;
}

void MainWindow::locateArduinoCli()
{
    const QString path = QFileDialog::getOpenFileName(this, tr("Locate arduino-cli"),
                                                        m_flasher->arduinoCliPath());
    if (path.isEmpty())
        return;

    m_flasher->setArduinoCliPath(path);
    QSettings settings;
    settings.setValue(QStringLiteral("arduinoCli/path"), path);
    statusBar()->showMessage(tr("arduino-cli path set to %1").arg(path), 4000);
}

void MainWindow::flashFirmware()
{
    if (m_flasher->isBusy())
        return;

    const QString port = m_portCombo->currentData().toString();
    if (port.isEmpty()) {
        QMessageBox::warning(this, tr("No Port Selected"),
                              tr("Please select the serial port the board is connected to."));
        return;
    }

    if (!ensureArduinoCliPath())
        return;

    const auto answer = QMessageBox::question(this, tr("Flash Firmware"),
        tr("This will overwrite the firmware currently on the board at %1 with the "
           "reader firmware bundled in this application (%2).\n\n"
           "Any active connection to the board will be closed first. Continue?")
            .arg(port, FirmwareFlasher::embeddedFirmwareVersion()),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);
    if (answer != QMessageBox::Yes)
        return;

    if (m_reader->isConnected())
        m_reader->disconnectFromPort();

    m_logDock->setVisible(true);
    appendLog(tr("Starting firmware flash on %1…").arg(port));

    m_flashProgress = new QProgressDialog(tr("Flashing firmware…"), tr("Cancel"), 0, 0, this);
    m_flashProgress->setWindowModality(Qt::WindowModal);
    m_flashProgress->setMinimumDuration(0);
    m_flashProgress->setAutoClose(false);
    m_flashProgress->setAutoReset(false);
    connect(m_flashProgress, &QProgressDialog::canceled, m_flasher, &FirmwareFlasher::cancel);

    setFlashingUiState(true);
    m_flasher->flash(port);
}

void MainWindow::onFlashOutputLine(const QString &line)
{
    appendLog(line);
    if (m_flashProgress)
        m_flashProgress->setLabelText(line);
}

void MainWindow::onFlashFinished(bool success, const QString &message)
{
    if (m_flashProgress) {
        m_flashProgress->close();
        m_flashProgress->deleteLater();
        m_flashProgress = nullptr;
    }

    setFlashingUiState(false);
    appendLog((success ? tr("Flash succeeded: %1") : tr("Flash failed: %1")).arg(message));

    if (success) {
        refreshPorts();
        QMessageBox::information(this, tr("Flash Complete"),
                                  tr("%1\n\nReconnect to the board to continue.").arg(message));
    } else {
        QMessageBox::critical(this, tr("Flash Failed"), message);
    }
}

void MainWindow::onConnected(const QString &portName, const QString &firmwareId)
{
    m_connectButton->setEnabled(true);
    m_connectButton->setText(tr("Disconnect"));
    m_connectionStatusLabel->setText(tr("Connected to %1 — %2").arg(portName, firmwareId));
    setConnectedUiState(true);
    appendLog(tr("Connected to %1 (%2).").arg(portName, firmwareId));
}

void MainWindow::onDisconnected()
{
    m_connectButton->setEnabled(true);
    m_connectButton->setText(tr("Connect"));
    m_connectionStatusLabel->setText(tr("Disconnected"));
    setConnectedUiState(false);
    appendLog(tr("Disconnected."));
}

void MainWindow::onConnectionFailed(const QString &reason)
{
    m_connectButton->setEnabled(true);
    m_connectButton->setText(tr("Connect"));
    m_connectionStatusLabel->setText(tr("Disconnected"));
    setConnectedUiState(false);
    appendLog(tr("Connection failed: %1").arg(reason));
    QMessageBox::critical(this, tr("Connection Failed"), reason);
}

void MainWindow::onRomReadStarted()
{
    m_readButton->setEnabled(false);
    m_saveButton->setEnabled(false);
    m_connectionStatusLabel->setText(tr("Reading ROM…"));
}

void MainWindow::onRomReadFinished(const std::array<uint8_t, 32> &data)
{
    m_data = data;
    m_hasData = true;
    updateTable();

    m_readButton->setEnabled(true);
    m_saveButton->setEnabled(true);
    m_connectionStatusLabel->setText(tr("Connected to %1").arg(m_reader->portName()));
    m_lastReadLabel->setText(tr("Last read: %1").arg(QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss"))));
    appendLog(tr("ROM read complete (32 bytes, checksum verified)."));
}

void MainWindow::onRomReadFailed(const QString &reason)
{
    m_readButton->setEnabled(m_reader->isConnected());
    m_saveButton->setEnabled(m_hasData);
    if (m_reader->isConnected())
        m_connectionStatusLabel->setText(tr("Connected to %1").arg(m_reader->portName()));
    appendLog(tr("ROM read failed: %1").arg(reason));
    QMessageBox::warning(this, tr("Read Failed"), reason);
}

void MainWindow::onLogMessage(const QString &message)
{
    appendLog(message);
}

void MainWindow::updateTable()
{
    for (int row = 0; row < 32; ++row) {
        const uint8_t value = m_data[static_cast<size_t>(row)];
        m_table->item(row, 1)->setText(QStringLiteral("0x%1").arg(hex2(value)));
        m_table->item(row, 2)->setText(QString::number(value));
        m_table->item(row, 3)->setText(QStringLiteral("%1").arg(value, 8, 2, QLatin1Char('0')));
        const QChar ch = (value >= 32 && value < 127) ? QChar(value) : QChar(QLatin1Char('.'));
        m_table->item(row, 4)->setText(QString(ch));
    }
}

void MainWindow::setConnectedUiState(bool connected)
{
    m_readButton->setEnabled(connected);
    m_portCombo->setEnabled(!connected);
    m_refreshButton->setEnabled(!connected);
}

void MainWindow::setFlashingUiState(bool busy)
{
    m_flashAction->setEnabled(!busy);
    m_flashButton->setEnabled(!busy);
    m_connectButton->setEnabled(!busy);
    m_portCombo->setEnabled(!busy && !m_reader->isConnected());
    m_refreshButton->setEnabled(!busy && !m_reader->isConnected());
    m_readButton->setEnabled(!busy && m_reader->isConnected());
    m_saveButton->setEnabled(!busy && m_hasData);
}

void MainWindow::appendLog(const QString &message)
{
    m_log->appendPlainText(QStringLiteral("[%1] %2")
                                .arg(QDateTime::currentDateTime().toString(QStringLiteral("HH:mm:ss")), message));
}
