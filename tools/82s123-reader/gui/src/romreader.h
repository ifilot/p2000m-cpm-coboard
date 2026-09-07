#pragma once

#include <QObject>
#include <QByteArray>
#include <QSerialPort>
#include <array>
#include <cstdint>

QT_BEGIN_NAMESPACE
class QTimer;
QT_END_NAMESPACE

// Talks to the 82S123 reader firmware over a line-based serial protocol:
//   PING -> "PONG <id> <version>"
//   READ -> 32x "AA:DD" lines, then "CHK:xx", then "OK"
// All communication is asynchronous and timeout-guarded so a missing or
// unresponsive device never hangs the GUI.
class RomReader : public QObject
{
    Q_OBJECT

public:
    explicit RomReader(QObject *parent = nullptr);

    bool isConnected() const;
    QString portName() const;

public slots:
    void connectToPort(const QString &portName);
    void disconnectFromPort();
    void readRom();

signals:
    void connected(const QString &portName, const QString &firmwareId);
    void disconnected();
    void connectionFailed(const QString &reason);

    void romReadStarted();
    void romReadFinished(const std::array<uint8_t, 32> &data);
    void romReadFailed(const QString &reason);

    void logMessage(const QString &message);

private slots:
    void onReadyRead();
    void onSerialError(QSerialPort::SerialPortError error);
    void onTimeout();

private:
    enum class State { Idle, WaitingPing, WaitingRead };

    void processLine(const QString &line);
    void sendCommand(const QString &cmd);
    void failRead(const QString &reason);
    void resetReadState();

    QSerialPort *m_serial;
    QTimer *m_timeoutTimer;
    QByteArray m_buffer;
    State m_state = State::Idle;

    std::array<uint8_t, 32> m_data{};
    std::array<bool, 32> m_received{};
    uint8_t m_checksum = 0;
    bool m_checksumReceived = false;
};
