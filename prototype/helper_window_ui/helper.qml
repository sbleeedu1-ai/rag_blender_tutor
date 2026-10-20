// 시제품(버릴 코드): QML 판 도우미 창 화면
import QtQuick
import QtQuick.Controls
import QtQuick.Window

Window {
    id: win
    required property var backend
    required property string fontName
    required property string firstQuestion
    property bool busy: false

    flags: Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint
    color: "transparent"
    minimumWidth: 300
    minimumHeight: 220
    visible: false

    function showHelper() {
        panel.opacity = 0
        panel.scale = 0.97
        win.show()
        win.raise()
        win.requestActivate()
        input.forceActiveFocus()
        showAnim.restart()
    }
    function hideHelper() {
        win.hide()
        backend.log("숨김(X 또는 Esc)")
    }
    function ask(q) {
        busy = true
        chat.append({ kind: "question", body: q })
        chat.append({ kind: "thinking", body: "생각 중…" })
        backend.ask(q)
    }

    Component.onCompleted: ask(firstQuestion)

    ListModel { id: chat }

    Connections {
        target: backend
        function onAnswerStarted() {
            chat.setProperty(chat.count - 1, "kind", "answer")
            chat.setProperty(chat.count - 1, "body", "")
        }
        function onChunk(s) {
            chat.setProperty(chat.count - 1, "body", chat.get(chat.count - 1).body + s)
            list.positionViewAtEnd()
        }
        function onFinished(sources) {
            // ListModel이 배열을 바꿔 버리지 않게 글로 넣음
            chat.append({ kind: "sources", body: JSON.stringify(sources) })
            busy = false
            list.positionViewAtEnd()
        }
    }

    Shortcut { sequence: "Esc"; onActivated: win.hideHelper() }

    // 창이 뜰 때 살짝 커지며 나타남
    ParallelAnimation {
        id: showAnim
        NumberAnimation { target: panel; property: "opacity"; to: 1; duration: 160; easing.type: Easing.OutCubic }
        NumberAnimation { target: panel; property: "scale"; to: 1; duration: 200; easing.type: Easing.OutBack }
    }

    // 둥근 어두운 반투명 판
    Rectangle {
        id: panel
        anchors.fill: parent
        radius: 22
        color: Qt.rgba(22 / 255, 22 / 255, 28 / 255, 0.84)
        border.color: Qt.rgba(1, 1, 1, 0.09)
        border.width: 1

        HoverHandler { id: hover }

        // 맨 위 띠: 끌어서 옮기기
        MouseArea {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 40
            onPressed: win.startSystemMove()
        }

        Text {
            x: 18; y: 16
            text: "시제품 · QML"
            color: Qt.rgba(1, 1, 1, 0.28)
            font { family: win.fontName; pixelSize: 11 }
        }

        // 마우스를 올리면 보이는 X
        Rectangle {
            id: closeBtn
            width: 24; height: 24; radius: 12
            anchors { right: parent.right; top: parent.top; rightMargin: 16; topMargin: 12 }
            color: closeArea.containsMouse ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(1, 1, 1, 0.10)
            opacity: hover.hovered ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }
            Behavior on color { ColorAnimation { duration: 120 } }
            Text {
                anchors.centerIn: parent
                text: "✕"
                color: Qt.rgba(1, 1, 1, 0.75)
                font.pixelSize: 12
            }
            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: win.hideHelper()
            }
        }

        // 대화
        ListView {
            id: list
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: input.top
                      leftMargin: 18; rightMargin: 14; topMargin: 44; bottomMargin: 10 }
            clip: true
            spacing: 8
            topMargin: Math.max(0, height - contentHeight)  // 대화를 아래부터 쌓음
            model: chat
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {
                width: 6
                contentItem: Rectangle { radius: 3; color: Qt.rgba(1, 1, 1, 0.18); opacity: list.contentHeight > list.height ? 1 : 0 }
            }

            delegate: Item {
                id: row
                required property string kind
                required property string body
                width: ListView.view.width - 10
                height: kind === "sources" ? card.height : label.implicitHeight

                // 새 줄이 아래에서 살짝 올라오며 나타남
                opacity: 0
                transform: Translate { id: shift; y: 8 }
                Component.onCompleted: appear.start()
                ParallelAnimation {
                    id: appear
                    NumberAnimation { target: row; property: "opacity"; to: 1; duration: 220 }
                    NumberAnimation { target: shift; property: "y"; to: 0; duration: 220; easing.type: Easing.OutCubic }
                }

                Text {
                    id: label
                    visible: row.kind !== "sources"
                    width: parent.width
                    wrapMode: Text.Wrap
                    text: row.kind === "answer" ? row.body.replace(/([.!?])\s+/g, "$1\n") : row.body
                    font.family: win.fontName
                    font.pixelSize: row.kind === "answer" ? 19 : row.kind === "thinking" ? 15 : 14
                    font.bold: row.kind === "answer"
                    color: row.kind === "answer" ? "white" : Qt.rgba(235 / 255, 235 / 255, 245 / 255, row.kind === "thinking" ? 0.45 : 0.55)
                    SequentialAnimation on opacity {
                        running: row.kind === "thinking"
                        onRunningChanged: if (!running) label.opacity = 1  // 반쯤 흐린 채 굳지 않게
                        loops: Animation.Infinite
                        NumberAnimation { to: 0.4; duration: 600 }
                        NumberAnimation { to: 1; duration: 600 }
                    }
                }

                // 근거 카드
                Rectangle {
                    id: card
                    visible: row.kind === "sources"
                    width: parent.width
                    height: cardCol.implicitHeight + 22
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.08)
                    Column {
                        id: cardCol
                        x: 14; y: 10
                        width: parent.width - 28
                        spacing: 4
                        Text {
                            text: "근거 · Blender 5.2 설명서"
                            color: Qt.rgba(235 / 255, 235 / 255, 245 / 255, 0.45)
                            font { family: win.fontName; pixelSize: 11; bold: true }
                        }
                        Repeater {
                            model: row.kind === "sources" ? JSON.parse(row.body) : []
                            Text {
                                required property var modelData
                                width: cardCol.width
                                wrapMode: Text.Wrap
                                textFormat: Text.RichText
                                font { family: win.fontName; pixelSize: 13 }
                                color: "white"
                                text: "<a style='color:#a9b6ff; text-decoration:none' href='" + modelData.url + "'>"
                                      + modelData.path + "</a>"
                                      + (modelData.note ? " <span style='color:#8a8a92'>· " + modelData.note + "</span>" : "")
                                onLinkActivated: (link) => Qt.openUrlExternally(link)
                                HoverHandler { cursorShape: Qt.PointingHandCursor }
                            }
                        }
                    }
                }
            }
        }

        // 알약 모양 입력칸
        TextField {
            id: input
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom
                      leftMargin: 18; rightMargin: 18; bottomMargin: 18 }
            height: 42
            leftPadding: 16; rightPadding: 16
            placeholderText: "질문을 입력하세요"
            placeholderTextColor: Qt.rgba(1, 1, 1, 0.35)
            color: "white"
            selectionColor: Qt.rgba(120 / 255, 140 / 255, 1, 0.6)
            font { family: win.fontName; pixelSize: 15 }
            background: Rectangle {
                radius: 21
                color: Qt.rgba(1, 1, 1, 0.10)
                border.width: 1
                border.color: input.activeFocus ? Qt.rgba(160 / 255, 175 / 255, 1, 0.45) : Qt.rgba(1, 1, 1, 0.08)
                Behavior on border.color { ColorAnimation { duration: 150 } }
            }
            onAccepted: {
                const q = text.trim()
                if (q.length === 0 || win.busy) return
                text = ""
                win.ask(q)
            }
        }

        // 테두리 없는 창의 크기 조절: 네 변과 네 모서리
        component Grip: MouseArea {
            property int edges
            onPressed: win.startSystemResize(edges)
        }
        Grip { edges: Qt.LeftEdge;   cursorShape: Qt.SizeHorCursor; width: 8; anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 8; bottomMargin: 8 } }
        Grip { edges: Qt.RightEdge;  cursorShape: Qt.SizeHorCursor; width: 8; anchors { right: parent.right; top: parent.top; bottom: parent.bottom; topMargin: 8; bottomMargin: 8 } }
        Grip { edges: Qt.TopEdge;    cursorShape: Qt.SizeVerCursor; height: 8; anchors { top: parent.top; left: parent.left; right: parent.right; leftMargin: 8; rightMargin: 8 } }
        Grip { edges: Qt.BottomEdge; cursorShape: Qt.SizeVerCursor; height: 8; anchors { bottom: parent.bottom; left: parent.left; right: parent.right; leftMargin: 8; rightMargin: 8 } }
        Grip { edges: Qt.LeftEdge | Qt.TopEdge;     cursorShape: Qt.SizeFDiagCursor; width: 10; height: 10; anchors { left: parent.left; top: parent.top } }
        Grip { edges: Qt.RightEdge | Qt.BottomEdge; cursorShape: Qt.SizeFDiagCursor; width: 10; height: 10; anchors { right: parent.right; bottom: parent.bottom } }
        Grip { edges: Qt.RightEdge | Qt.TopEdge;    cursorShape: Qt.SizeBDiagCursor; width: 10; height: 10; anchors { right: parent.right; top: parent.top } }
        Grip { edges: Qt.LeftEdge | Qt.BottomEdge;  cursorShape: Qt.SizeBDiagCursor; width: 10; height: 10; anchors { left: parent.left; bottom: parent.bottom } }
    }
}
