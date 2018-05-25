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

MAX_SPEED = 0.5
DAMPING = 0.1
class ChoiceBox:
    
    def __init__(self, text, pattern, x, y, reftext=''):
        self.text = text
        self.reftext = reftext
        self.pattern = pattern
        self.x = x
        self.display_x = x
        self.y = y
        self.display_y = y
        self.vx = random.uniform(-MAX_SPEED, MAX_SPEED)
        self.vy = random.uniform(-MAX_SPEED, MAX_SPEED)

    def update(self):
        self.display_x += self.vx
        self.display_y += self.vy
        display_x_offset = self.display_x - self.x
        display_y_offset = self.display_y - self.y
        if random.randint(0, 5) == 0:
            self.vx = random.uniform(-MAX_SPEED-display_x_offset*DAMPING, MAX_SPEED-display_x_offset*DAMPING)
            self.vy = random.uniform(-MAX_SPEED-display_y_offset*DAMPING, MAX_SPEED-display_y_offset*DAMPING)

    def draw(self, context, timestamp):
        context.select_font_face('Noto Sans', cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(40)

        margin = 20

        
        extents = context.text_extents(self.reftext if self.reftext != '' else self.text)
        context.rectangle(self.display_x, self.display_y, (extents.width + 2 * margin)*((timestamp % 1E9)/1E9), extents.height + 2 * margin)
        context.set_source(self.pattern)
        context.fill()

        context.rectangle(self.display_x, self.display_y, extents.width + 2 * margin, extents.height + 2 * margin)

        dashes = [30.0, 10.0]
        context.set_source_rgba(0, 0, 1, 1)
        context.set_line_width(5)
        context.set_dash(dashes, timestamp / 1E7)
        context.set_line_join(cairo.LINE_JOIN_BEVEL)
        context.stroke()

        context.move_to(self.display_x + margin, self.display_y + extents.height + margin)
        context.text_path(self.text)
        print(extents)
        context.set_source_rgba(0, 0, 1, 1)
        context.fill()

class ChoicesDialog:

    def __init__(self, texts):
        self.boxes = []
        longest_text = max(texts, key=len)
        x = 100
        y = 100
        dy = 100
        dx = 0
        print("LONGEST: {}".format(longest_text))
        for text in texts:
            self.boxes.append(ChoiceBox(text, cairo.SolidPattern(1, 0, 0), x, y, longest_text))
            y += dy
            x += dx

    def draw(self, context, timestamp):
        for box in self.boxes:
            box.draw(context, timestamp)

    def update(self):
        for box in self.boxes:
            box.update()


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

        #WRepaintNoErase
        #WResizeNoErase

        # Video item

        self.shortcut = QShortcut(QKeySequence("Q"), self)
        self.shortcut.activated.connect(self.exitCall)

        self.play_shortcut = QShortcut(QKeySequence("P"), self)
        self.play_shortcut.activated.connect(self.play_pause_toggle)


        #overlay.move(0, 0)

        #button = QPushButton("push me", player)
        #button.show()

        self.choices = ChoicesDialog(["WELCOME TO AVEROID ADVENTURES", "WHAT WILL YOU DO TODAY", "PLAN S", "TEST 1", "TEST 2", "TEST 3", "MORE TEXT"])

        self.pipeline = Gst.parse_launch(
            #'videotestsrc ! cairooverlay name=overlay ! videoconvert ! xvimagesink name=sink')
            'filesrc location=/home/david/gdrive/avery_house/rotation_video/player/videos/vsync.mp4 ! decodebin name=dec ! videoconvert ! cairooverlay name=overlay ! videoconvert ! xvimagesink name=sink dec. ! audioconvert ! audioresample ! alsasink')
        cairo_overlay = self.pipeline.get_by_name('overlay')
        if cairo_overlay != None:
            cairo_overlay.connect('draw', self.on_draw)

        image_overlay = self.pipeline.get_by_name('image')
        if image_overlay != None:
            print("SETTING ALPHA")
            image_overlay.alpha = 0.5

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


    def on_draw(self, _overlay, context, timestamp, _duration):
        print("DRAW")
        """Each time the 'draw' signal is emitted"""
        """COLOR_PERIOD = 2E9
        colors = [[1.0, 1.0, 0.0], [0.0, 1.0, 1.0]]
        cycle_progression = timestamp % (COLOR_PERIOD * len(colors)) / COLOR_PERIOD
        current_progression = timestamp % COLOR_PERIOD / COLOR_PERIOD
        previous_color = int(cycle_progression)
        target_color = (previous_color + 1) % len(colors)
        current_color = [colors[previous_color][i] * (1-current_progression) + colors[target_color][i] * current_progression for i in range(0, 3)]
        context.set_source_rgba(current_color[0], current_color[1], current_color[2], 0.8)
        context.rectangle(20, 20, 300, 100)
        context.fill()
        context.stroke()"""

        self.choices.draw(context, timestamp)
        self.choices.update()


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
    player.showFullScreen()
    #player.show()
    player.play()

    sys.exit(app.exec_())
