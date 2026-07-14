import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15

Window {
    id: cliWindow
    visible: false
    width: 600
    height: 400
    x: (Screen.width - width) / 2
    y: (Screen.height - height) / 2
    
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    color: "#D9000000" // 85% transparent overlay

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: "#333333"
        border.width: 1
    }

    ListView {
        id: historyList
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: inputRect.top
        anchors.margins: 10
        model: ListModel { id: historyModel }
        
        delegate: Text {
            width: ListView.view.width
            text: model.text
            color: model.isError ? "#FF5555" : "#00FFCC"
            font.family: "monospace"
            font.pixelSize: 13
            wrapMode: Text.Wrap
        }
        
        onCountChanged: {
            historyList.positionViewAtEnd()
        }
    }

    Rectangle {
        id: inputRect
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 40
        color: "#1A1A1A"
        
        Text {
            id: prompt
            text: "SYNAPSE>"
            color: "#00FFCC"
            font.family: "monospace"
            font.pixelSize: 13
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 10
        }

        TextInput {
            id: commandInput
            anchors.left: prompt.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: 10
            color: "#FFFFFF"
            font.family: "monospace"
            font.pixelSize: 13
            verticalAlignment: TextInput.AlignVCenter
            
            onAccepted: {
                if (text.trim() !== "") {
                    historyModel.append({"text": "SYNAPSE> " + text, "isError": false});
                    uiController.submitCommand(text);
                    text = "";
                }
            }
        }
    }

    Connections {
        target: uiController
        function onCommandResponse(responseStr, isError) {
            historyModel.append({"text": responseStr, "isError": isError});
        }
    }
    
    onVisibleChanged: {
        if (visible) {
            commandInput.forceActiveFocus();
        }
    }
}
