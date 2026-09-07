#include <QApplication>
#include <QIcon>

#include "mainwindow.h"

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setOrganizationName(QStringLiteral("82S123Reader"));
    QApplication::setApplicationName(QStringLiteral("82S123 ROM Reader"));
    QApplication::setApplicationVersion(QStringLiteral("0.1.0"));

    // Multi-resolution app icon: title bar, taskbar/dock, Alt-Tab, etc.
    // (the .exe's own icon on Windows comes from resources/app.ico via the
    // generated .rc resource script, embedded at link time.)
    QIcon appIcon;
    appIcon.addFile(QStringLiteral(":/icons/app-16.png"));
    appIcon.addFile(QStringLiteral(":/icons/app-32.png"));
    appIcon.addFile(QStringLiteral(":/icons/app-48.png"));
    appIcon.addFile(QStringLiteral(":/icons/app-128.png"));
    appIcon.addFile(QStringLiteral(":/icons/app-256.png"));
    QApplication::setWindowIcon(appIcon);

    MainWindow window;
    window.show();

    return QApplication::exec();
}
