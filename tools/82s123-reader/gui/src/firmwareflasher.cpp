#include "firmwareflasher.h"
#include "generated/firmware_source.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QProcess>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QTemporaryDir>

FirmwareFlasher::FirmwareFlasher(QObject *parent)
    : QObject(parent)
{
}

FirmwareFlasher::~FirmwareFlasher()
{
    if (m_process) {
        m_process->kill();
        m_process->waitForFinished(1000);
    }
}

QString FirmwareFlasher::embeddedFirmwareVersion()
{
    static const QRegularExpression versionRe(
        QStringLiteral("FIRMWARE_VERSION\\s*=\\s*\"([^\"]+)\""));
    const QString source = QString::fromUtf8(kFirmwareInoSource);
    const auto match = versionRe.match(source);
    return match.hasMatch() ? match.captured(1) : QStringLiteral("unknown");
}

QString FirmwareFlasher::autoDetectArduinoCli()
{
    const QString onPath = QStandardPaths::findExecutable(QStringLiteral("arduino-cli"));
    if (!onPath.isEmpty())
        return onPath;

    QStringList candidates;
#if defined(Q_OS_WIN)
    candidates << QStringLiteral("C:/Program Files/Arduino CLI/arduino-cli.exe")
               << QStringLiteral("C:/Program Files (x86)/Arduino CLI/arduino-cli.exe");
#else
    candidates << QStringLiteral("/usr/local/bin/arduino-cli")
               << QStringLiteral("/usr/bin/arduino-cli")
               << (QDir::homePath() + QStringLiteral("/.local/bin/arduino-cli"));
#endif
    for (const QString &candidate : candidates) {
        if (QFileInfo::exists(candidate))
            return candidate;
    }
    return QString();
}

void FirmwareFlasher::flash(const QString &portName)
{
    if (m_process) {
        emit finished(false, tr("A flash operation is already in progress."));
        return;
    }
    if (m_arduinoCliPath.isEmpty() || !QFileInfo::exists(m_arduinoCliPath)) {
        emit finished(false, tr("arduino-cli was not found. Locate it via "
                                 "Firmware > Locate arduino-cli\xE2\x80\xA6"));
        return;
    }
    if (portName.isEmpty()) {
        emit finished(false, tr("No serial port selected."));
        return;
    }

    m_tempDir = std::make_unique<QTemporaryDir>();
    if (!m_tempDir->isValid()) {
        emit finished(false, tr("Could not create a temporary directory for the sketch."));
        m_tempDir.reset();
        return;
    }

    const QString sketchName = QString::fromLatin1(kFirmwareSketchName);
    const QString sketchDir = m_tempDir->filePath(sketchName);
    if (!QDir().mkpath(sketchDir)) {
        emit finished(false, tr("Could not create the sketch folder in the temporary directory."));
        m_tempDir.reset();
        return;
    }

    QFile file(sketchDir + QStringLiteral("/") + sketchName + QStringLiteral(".ino"));
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        emit finished(false, tr("Could not write the embedded sketch to a temporary file:\n%1")
                                  .arg(file.errorString()));
        m_tempDir.reset();
        return;
    }
    file.write(kFirmwareInoSource);
    file.close();

    m_process = new QProcess(this);
    m_process->setProcessChannelMode(QProcess::MergedChannels);
    m_lineBuffer.clear();

    connect(m_process, &QProcess::readyReadStandardOutput, this, [this]() {
        m_lineBuffer += m_process->readAllStandardOutput();
        int idx;
        while ((idx = m_lineBuffer.indexOf('\n')) >= 0) {
            const QByteArray lineBytes = m_lineBuffer.left(idx);
            m_lineBuffer.remove(0, idx + 1);
            const QString line = QString::fromLocal8Bit(lineBytes).trimmed();
            if (!line.isEmpty())
                emit outputLine(line);
        }
    });

    connect(m_process, &QProcess::finished, this,
            [this](int exitCode, QProcess::ExitStatus exitStatus) {
        if (!m_lineBuffer.isEmpty()) {
            emit outputLine(QString::fromLocal8Bit(m_lineBuffer).trimmed());
            m_lineBuffer.clear();
        }
        const bool success = (exitStatus == QProcess::NormalExit && exitCode == 0);
        const QString message = success
            ? tr("Firmware flashed successfully.")
            : (exitStatus == QProcess::CrashExit
                   ? tr("arduino-cli crashed or was cancelled.")
                   : tr("arduino-cli exited with code %1. See the log for details.").arg(exitCode));
        cleanupProcess();
        emit finished(success, message);
    });

    connect(m_process, &QProcess::errorOccurred, this, [this](QProcess::ProcessError error) {
        // FailedToStart is the only error for which QProcess never emits
        // finished(); every other error is also followed by finished(),
        // which already reports it, so only handle that one case here.
        if (!m_process || error != QProcess::FailedToStart)
            return;
        const QString message = tr("Failed to start arduino-cli: %1").arg(m_process->errorString());
        cleanupProcess();
        emit finished(false, message);
    });

    const QStringList args = {
        QStringLiteral("compile"),
        QStringLiteral("--upload"),
        QStringLiteral("-p"), portName,
        QStringLiteral("--fqbn"), QString::fromLatin1(kFirmwareFqbn),
        sketchDir,
    };

    emit started();
    emit outputLine(tr("Running: %1 %2").arg(m_arduinoCliPath, args.join(QStringLiteral(" "))));
    m_process->start(m_arduinoCliPath, args);
}

void FirmwareFlasher::cancel()
{
    if (m_process)
        m_process->kill();
}

void FirmwareFlasher::cleanupProcess()
{
    if (m_process) {
        m_process->deleteLater();
        m_process = nullptr;
    }
    m_tempDir.reset();
}
