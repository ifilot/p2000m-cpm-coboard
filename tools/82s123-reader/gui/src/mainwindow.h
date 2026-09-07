#pragma once

#include <QMainWindow>
#include <array>
#include <cstdint>

QT_BEGIN_NAMESPACE
class QComboBox;
class QPushButton;
class QTableWidget;
class QPlainTextEdit;
class QLabel;
class QDockWidget;
class QAction;
class QProgressDialog;
QT_END_NAMESPACE

class RomReader;
class FirmwareFlasher;

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    explicit MainWindow(QWidget *parent = nullptr);

private slots:
    void refreshPorts();
    void toggleConnection();
    void startRead();
    void saveData();
    void showAbout();
    void flashFirmware();
    void locateArduinoCli();

    void onConnected(const QString &portName, const QString &firmwareId);
    void onDisconnected();
    void onConnectionFailed(const QString &reason);
    void onRomReadStarted();
    void onRomReadFinished(const std::array<uint8_t, 32> &data);
    void onRomReadFailed(const QString &reason);
    void onLogMessage(const QString &message);

    void onFlashOutputLine(const QString &line);
    void onFlashFinished(bool success, const QString &message);

private:
    void buildUi();
    void updateTable();
    void setConnectedUiState(bool connected);
    void setFlashingUiState(bool busy);
    void appendLog(const QString &message);
    bool ensureArduinoCliPath();

    RomReader *m_reader;
    FirmwareFlasher *m_flasher;

    QComboBox *m_portCombo = nullptr;
    QPushButton *m_refreshButton = nullptr;
    QPushButton *m_connectButton = nullptr;
    QPushButton *m_readButton = nullptr;
    QPushButton *m_saveButton = nullptr;
    QPushButton *m_flashButton = nullptr;
    QTableWidget *m_table = nullptr;
    QPlainTextEdit *m_log = nullptr;
    QDockWidget *m_logDock = nullptr;
    QLabel *m_connectionStatusLabel = nullptr;
    QLabel *m_lastReadLabel = nullptr;
    QAction *m_flashAction = nullptr;
    QProgressDialog *m_flashProgress = nullptr;

    std::array<uint8_t, 32> m_data{};
    bool m_hasData = false;
};
