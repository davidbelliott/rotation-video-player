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


import random
import cairo
import gi
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gst, GObject, GstVideo


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

class VideoWindow(QMainWindow):
 
    def __init__(self, world, parent=None):
        super(VideoWindow, self).__init__(parent)

        self.setWindowTitle("Averoid Adventures") 
        self.world = world
        #self.setWindowFlags(Qt.CustomizeWindowHint | Qt.FramelessWindowHint)
        #self.setAttribute(Qt.WA_TranslucentBackground)
        #self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setCursor(Qt.BlankCursor)
        #self.setStyleSheet("background-color: rgba(255, 0, 0, 50%);")

        # Video item

        self.shortcut = QShortcut(QKeySequence("Q"), self)
        self.shortcut.activated.connect(self.exitCall)

        self.play_shortcut = QShortcut(QKeySequence("P"), self)
        self.play_shortcut.activated.connect(self.play_pause_toggle)


        #overlay.move(0, 0)

        #button = QPushButton("push me", player)
        #button.show()




        self.pipeline = Gst.parse_launch(
            'videotestsrc ! cairooverlay name=overlay ! videoconvert ! xvimagesink name=sink')
        cairo_overlay = self.pipeline.get_by_name('overlay')
        cairo_overlay.connect('draw', self.on_draw)

        sink = self.pipeline.get_by_name('sink')
        xid = self.winId()
        sink.set_window_handle (xid)

        self.pipeline.set_state(Gst.State.PLAYING)

 
    def openFile(self, fileName):
        pass
        '''if fileName != '':
            self.mediaPlayer.setMedia(
                    QMediaContent(QUrl.fromLocalFile(fileName)))
            self.fitInView(self.videoItem.boundingRect(), Qt.KeepAspectRatio)'''
 
    def exitCall(self):
        print("Exit")
        self.pipeline.set_state(Gst.State.NULL)
        sys.exit(app.exec_())
        
    def play(self):
        pass
        #self.mediaPlayer.play()

    def pause(self):
        pass
        #self.mediaPlayer.pause()

    def play_pause_toggle(self):
        pass
        '''if self.mediaPlayer.state() == QMediaPlayer.PlayingState:
            self.pause()
        else:
            self.play()'''

    def mediaStatusChanged(self, status):
        pass
        '''print("Status: {}".format(status))
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
                sys.exit(app.exec_())'''


    def on_draw(self, _overlay, context, _timestamp, _duration):
        """Each time the 'draw' signal is emitted"""
        context.select_font_face('Noto Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(20)
        context.move_to(100, 100)
        context.text_path('Fun Avery fact: {}'.format(random.randint(1,5)))
        context.set_source_rgba(1, 1, 1, 0.75)
        context.fill_preserve()

    def error(self, error):
        print("Error: {}".format(error))

 
if __name__ == '__main__':
    GObject.threads_init()
    Gst.init(None)
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    world = World(args.filename)

    player = VideoWindow(world)

    video = world.get_video()
    player.openFile(video)
    #player.showFullScreen()
    player.show()
    player.play()

    sys.exit(app.exec_())
