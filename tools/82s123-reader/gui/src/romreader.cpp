#include "romreader.h"

#include <QSerialPort>
#include <QTimer>
#include <QRegularExpression>

namespace {
constexpr int kPingTimeoutMs = 1500;
constexpr int kReadTimeoutMs = 3000;
constexpr int kStartupDelayMs = 300; // let the board settle after opening the port
}

RomReader::RomReader(QObject *parent)
    : QObject(parent)
    , m_serial(new QSerialPort(this))
    , m_timeoutTimer(new QTimer(this))
{
    m_timeoutTimer->setSingleShot(true);
    connect(m_timeoutTimer, &QTimer::timeout, this, &RomReader::onTimeout);
    connect(m_serial, &QSerialPort::readyRead, this, &RomReader::onReadyRead);
    connect(m_serial, &QSerialPort::errorOccurred, this, &RomReader::onSerialError);
}

bool RomReader::isConnected() const
{
    return m_serial->isOpen();
}

QString RomReader::portName() const
{
    return m_serial->portName();
}

void RomReader::connectToPort(const QString &portName)
{
    if (m_serial->isOpen())
        m_serial->close();

    m_serial->setPortName(portName);
    m_serial->setBaudRate(QSerialPort::Baud115200);
    m_serial->setDataBits(QSerialPort::Data8);
    m_serial->setParity(QSerialPort::NoParity);
    m_serial->setStopBits(QSerialPort::OneStop);
    m_serial->setFlowControl(QSerialPort::NoFlowControl);

    if (!m_serial->open(QIODevice::ReadWrite)) {
        emit connectionFailed(m_serial->errorString());
        return;
    }

    // Native-USB boards (Leonardo/Micro) expose a "host connected" flag to
    // sketch code via the DTR control line; Qt does not assert it on open()
    // by default the way the Arduino Serial Monitor and avrdude do. Assert
    // it explicitly so a "while (!Serial);" gate in older/other firmware
    // doesn't hang waiting for it.
    m_serial->setDataTerminalReady(true);

    m_buffer.clear();
    m_state = State::WaitingPing;
    m_timeoutTimer->start(kPingTimeoutMs);

    // Give the (possibly just-enumerated) board a brief moment before we
    // address it, then send the handshake.
    QTimer::singleShot(kStartupDelayMs, this, [this]() {
        if (m_state == State::WaitingPing)
            sendCommand(QStringLiteral("PING"));
    });
}

void RomReader::disconnectFromPort()
{
    m_timeoutTimer->stop();
    if (m_serial->isOpen())
        m_serial->close();
    m_state = State::Idle;
    emit disconnected();
}

void RomReader::readRom()
{
    if (!m_serial->isOpen()) {
        emit romReadFailed(tr("Not connected."));
        return;
    }
    if (m_state != State::Idle) {
        emit romReadFailed(tr("Reader is busy, please wait."));
        return;
    }

    resetReadState();
    m_state = State::WaitingRead;
    m_timeoutTimer->start(kReadTimeoutMs);

    emit romReadStarted();
    sendCommand(QStringLiteral("READ"));
}

void RomReader::resetReadState()
{
    m_data.fill(0);
    m_received.fill(false);
    m_checksum = 0;
    m_checksumReceived = false;
}

void RomReader::sendCommand(const QString &cmd)
{
    emit logMessage(QStringLiteral("-> %1").arg(cmd));
    m_serial->write((cmd + QStringLiteral("\n")).toLatin1());
}

void RomReader::onReadyRead()
{
    m_buffer += m_serial->readAll();

    int idx;
    while ((idx = m_buffer.indexOf('\n')) >= 0) {
        const QByteArray lineBytes = m_buffer.left(idx);
        m_buffer.remove(0, idx + 1);
        const QString line = QString::fromLatin1(lineBytes).trimmed();
        if (!line.isEmpty())
            processLine(line);
    }
}

void RomReader::processLine(const QString &line)
{
    emit logMessage(QStringLiteral("<- %1").arg(line));

    if (m_state == State::WaitingPing) {
        if (line.startsWith(QStringLiteral("PONG"))) {
            m_timeoutTimer->stop();
            m_state = State::Idle;
            emit connected(m_serial->portName(), line.mid(5).trimmed());
        }
        // Ignore anything else (e.g. stray boot text) while we wait.
        return;
    }

    if (m_state == State::WaitingRead) {
        static const QRegularExpression dataRe(QStringLiteral("^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})$"));
        static const QRegularExpression chkRe(QStringLiteral("^CHK:([0-9A-Fa-f]{2})$"));

        if (line.compare(QStringLiteral("OK"), Qt::CaseInsensitive) == 0) {
            m_timeoutTimer->stop();

            for (int i = 0; i < 32; ++i) {
                if (!m_received[static_cast<size_t>(i)]) {
                    failRead(tr("Incomplete data: address 0x%1 was never received.")
                                 .arg(i, 2, 16, QLatin1Char('0')));
                    return;
                }
            }
            if (!m_checksumReceived) {
                failRead(tr("Checksum missing from device response."));
                return;
            }

            uint8_t computed = 0;
            for (uint8_t b : m_data) computed ^= b;
            if (computed != m_checksum) {
                failRead(tr("Checksum mismatch (expected 0x%1, device reported 0x%2). "
                             "The transfer may be corrupted, please read again.")
                             .arg(computed, 2, 16, QLatin1Char('0'))
                             .arg(m_checksum, 2, 16, QLatin1Char('0')));
                return;
            }

            m_state = State::Idle;
            emit romReadFinished(m_data);
            return;
        }

        if (line.startsWith(QStringLiteral("ERR"))) {
            m_timeoutTimer->stop();
            failRead(tr("Device reported an error: %1").arg(line));
            return;
        }

        const auto chkMatch = chkRe.match(line);
        if (chkMatch.hasMatch()) {
            m_checksum = static_cast<uint8_t>(chkMatch.captured(1).toUInt(nullptr, 16));
            m_checksumReceived = true;
            return;
        }

        const auto dataMatch = dataRe.match(line);
        if (dataMatch.hasMatch()) {
            const uint8_t addr = static_cast<uint8_t>(dataMatch.captured(1).toUInt(nullptr, 16));
            const uint8_t value = static_cast<uint8_t>(dataMatch.captured(2).toUInt(nullptr, 16));
            if (addr < 32) {
                m_data[addr] = value;
                m_received[addr] = true;
            }
            return;
        }

        // Unrecognized line while a read is pending: ignore and keep waiting.
        return;
    }
}

void RomReader::failRead(const QString &reason)
{
    m_timeoutTimer->stop();
    m_state = State::Idle;
    emit romReadFailed(reason);
}

void RomReader::onTimeout()
{
    if (m_state == State::WaitingPing) {
        m_state = State::Idle;
        if (m_serial->isOpen())
            m_serial->close();
        emit connectionFailed(tr("No response from the device (handshake timed out). "
                                  "Check that the correct port is selected and the "
                                  "82S123 reader firmware is flashed."));
    } else if (m_state == State::WaitingRead) {
        failRead(tr("Timed out waiting for ROM data from the device."));
    }
}

void RomReader::onSerialError(QSerialPort::SerialPortError error)
{
    if (error == QSerialPort::NoError)
        return;

    emit logMessage(QStringLiteral("Serial error: %1").arg(m_serial->errorString()));

    if (error == QSerialPort::ResourceError) {
        // Typically means the device was unplugged.
        const bool wasOpen = m_serial->isOpen();
        m_timeoutTimer->stop();
        m_serial->close();
        const State previousState = m_state;
        m_state = State::Idle;

        if (previousState == State::WaitingRead)
            emit romReadFailed(tr("Lost connection to the device during the read."));
        else if (previousState == State::WaitingPing)
            emit connectionFailed(tr("Lost connection to the device."));
        else if (wasOpen)
            emit disconnected();
    }
}
