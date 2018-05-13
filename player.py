# PyQt5 Video player
#!/usr/bin/env python
 
from PyQt5.QtCore import *
from PyQt5.QtMultimedia import *
from PyQt5.QtMultimediaWidgets import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import os, sys
import argparse
import json
import time

class World:
    def __init__(self, filename):
        self.world_path = os.path.abspath(filename)
        self.video_path = os.path.join(os.path.dirname(self.world_path), "videos")
        with open(self.world_path) as json_data:
            self.data = json.load(json_data)
        self.current_room_name = self.data["starting_room"]

    def next_room(self):
        print("Getting next room...")
        current_room = self.data["rooms"][self.current_room_name]
        has_choice = False
        has_next = False
        if "choice" in current_room:
            has_choice = True
        elif "next" in current_room:
            has_next = True
        if has_next:
            self.current_room_name = current_room["next"]
        else:
            self.current_room_name = ""

        return (self.current_room_name != "")

    def get_video(self):
        current_room = self.data["rooms"][self.current_room_name]
        return os.path.join(self.video_path, current_room["video"])
    
    def get_choice(self):
        current_room = self.data["rooms"][self.current_room_name]
        return current_room["choice"] if "choice" in current_room else None

class ChoiceOverlay(QWidget):

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)



        self.text = "Лев Николаевич Толстой\nАнна Каренина"

    def paintEvent(self, event):
        qp = QPainter()
        qp.begin(self)
        qp.fillRect(event.rect(), QBrush(QColor(128, 128, 255, 128)))
        self.drawText(event, qp)
        qp.end()

    def drawText(self, event, qp):
        qp.setPen(QColor(168, 34, 3))
        #qp.setFont(QFont('Decorative', 10))
        qp.drawText(event.rect(), Qt.AlignCenter, self.text)

class VideoWindow(QGraphicsView):
 
    def __init__(self, world, parent=None):
        super(VideoWindow, self).__init__(parent)

        self.setWindowTitle("Averoid Adventures") 
        self.world = world
        #self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        self.setCursor(Qt.BlankCursor)
        self.setBackgroundBrush(QBrush(Qt.black, Qt.SolidPattern))

        # Video item
        self.videoItem = QGraphicsVideoItem()
        self.videoItem.nativeSizeChanged.connect(self.resize)

        # Overlay item
        self.overlayItem = QGraphicsRectItem()
        
        # Media player
        self.mediaPlayer = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.mediaPlayer.mediaStatusChanged.connect(self.mediaStatusChanged)
        self.mediaPlayer.error.connect(self.error)
        self.mediaPlayer.setVideoOutput(self.videoItem)



        scene = QGraphicsScene(self)
        scene.addItem(self.videoItem)
        self.setScene(scene)


        self.shortcut = QShortcut(QKeySequence("Q"), self)
        self.shortcut.activated.connect(self.exitCall)

        self.play_shortcut = QShortcut(QKeySequence("P"), self)
        self.play_shortcut.activated.connect(self.play_pause_toggle)


        #overlay.move(0, 0)

        #button = QPushButton("push me", player)
        #button.show()


 
    def openFile(self, fileName):
        if fileName != '':
            self.mediaPlayer.setMedia(
                    QMediaContent(QUrl.fromLocalFile(fileName)))
            self.fitInView(self.videoItem.boundingRect(), Qt.KeepAspectRatio)
 
    def exitCall(self):
        sys.exit(app.exec_())
        
    def play(self):
        self.mediaPlayer.play()

    def pause(self):
        self.mediaPlayer.pause()

    def play_pause_toggle(self):
        if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()

    def mediaStatusChanged(self, status):
        print("Status: {}".format(status))
        if status == QMediaPlayer.EndOfMedia:
            if self.world.next_room():
                choice = self.world.get_choice()
                if choice:
                    print(choice)
                video = self.world.get_video()
                if video:
                    print("Opening {}".format(video))
                    self.openFile(video)
                    self.play()
            else:
                sys.exit(app.exec_())

    def error(self, error):
        print("Error: {}".format(error))

    def resizeEvent(self, event):
        print("Resizing")
        self.resize()

    def resize(self):
        self.fitInView(self.videoItem.boundingRect(), Qt.KeepAspectRatio)

    #override arbitrary and unwanted margins: https://bugreports.qt.io/browse/QTBUG-42331 - based on QT sources
    '''def fitInView(self, item, flags = Qt.IgnoreAspectRatio):
        rect = item.boundingRect()
        if self.scene() is None or rect.isNull():
            return
        self.last_scene_roi = rect
        unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
        self.scale(1/unity.width(), 1/unity.height())
        viewRect = self.viewport().rect()
        sceneRect = self.transform().mapRect(rect)
        xratio = viewRect.width() / sceneRect.width()
        yratio = viewRect.height() / sceneRect.height()
        if flags == Qt.KeepAspectRatio:
            xratio = yratio = min(xratio, yratio)
        elif flags == Qt.KeepAspectRatioByExpanding:
            xratio = yratio = max(xratio, yratio)
        self.scale(xratio, yratio)
        self.centerOn(rect.center())'''
 
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    world = World(args.filename)

    player = VideoWindow(world)

    video = world.get_video()
    player.openFile(video)
    player.showFullScreen()
    #player.show()
    player.play()

    sys.exit(app.exec_())
