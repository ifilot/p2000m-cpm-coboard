#pragma once

#include <QByteArray>
#include <QObject>
#include <QString>
#include <memory>

QT_BEGIN_NAMESPACE
class QProcess;
class QTemporaryDir;
QT_END_NAMESPACE

// Compiles and uploads the firmware sketch embedded into this binary (see
// generated/firmware_source.h, produced from the .ino at configure time) by
// shelling out to a user-supplied `arduino-cli`. Runs asynchronously via
// QProcess so it never blocks the UI; every failure mode (missing tool,
// missing port, process crash, non-zero exit) is surfaced through
// finished(false, ...) rather than left to hang or crash the app.
class FirmwareFlasher : public QObject
{
    Q_OBJECT

public:
    explicit FirmwareFlasher(QObject *parent = nullptr);
    ~FirmwareFlasher() override;

    // Searches PATH and a few well-known install locations. Returns an
    // empty string if nothing was found.
    static QString autoDetectArduinoCli();

    // Version string parsed out of the embedded sketch, for display only.
    static QString embeddedFirmwareVersion();

    QString arduinoCliPath() const { return m_arduinoCliPath; }
    void setArduinoCliPath(const QString &path) { m_arduinoCliPath = path; }

    bool isBusy() const { return m_process != nullptr; }

public slots:
    // Writes the embedded sketch to a temporary directory and runs
    // `arduino-cli compile --upload -p <portName> ...` against it.
    void flash(const QString &portName);
    void cancel();

signals:
    void started();
    void outputLine(const QString &line);
    void finished(bool success, const QString &message);

private:
    void cleanupProcess();

    QString m_arduinoCliPath;
    QProcess *m_process = nullptr;
    std::unique_ptr<QTemporaryDir> m_tempDir;
    QByteArray m_lineBuffer;
};
