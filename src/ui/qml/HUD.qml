import QtQuick 2.15
import QtQuick.Window 2.15

Window {
    id: hudWindow
    visible: false
    width: Screen.width
    height: Screen.height
    
    // Qt.FramelessWindowHint + WindowTransparentForInput perfectly handles Linux click-through transparent states
    // Note: The python-side `setAttribute(Qt.WA_TransparentForMouseEvents, True)` applies only to QWidget wrappers.
    // By using QQuickWindow directly with these native flags, we avoid the QWidget overhead entirely (Sub-50ms render).
    flags: Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "transparent"

    Text {
        id: hudText
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 20
        font.pixelSize: 13
        font.family: "monospace"
        color: "#00FFCC"
        style: Text.Outline
        styleColor: "#111111"
        text: "HUD Initialization..."
    }

    Connections {
        target: uiController
        function onTelemetryUpdated(data) {
            hudText.text = data;
        }
    }
}
