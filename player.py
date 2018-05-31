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
from gi.repository import GES, Gtk, Gdk, Gst, GObject, GstVideo, GLib

videoFile = "file:///home/david/gdrive/avery_house/rotation_video/player/videos/avery_tour.mp4"

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
        #print(extents)
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
        #print("LONGEST: {}".format(longest_text))
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


class Player:
 
    def __init__(self):

        self.world = world

        self.choices = ChoicesDialog(["WELCOME TO AVEROID ADVENTURES", "WHAT WILL YOU DO TODAY", "PLAN S", "TEST 1", "TEST 2", "TEST 3", "MORE TEXT"])




        self.timeline = GES.Timeline.new_audio_video()
        self.asset = GES.UriClipAsset.request_sync(videoFile)

        self.layer = GES.Layer()
        self.timeline.add_layer(self.layer)
        self.layer.add_asset(self.asset, 0, 0, self.asset.get_duration(), self.asset.get_supported_formats())
        self.timeline.commit()

        self.pipeline = GES.Pipeline()
        self.pipeline.set_timeline(self.timeline)
        self.pipeline.set_state(Gst.State.PLAYING)

        bin = Gst.Bin.new("my-bin")
        convert1 = Gst.ElementFactory.make("videoconvert")
        bin.add(convert1)
        pad = convert1.get_static_pad("sink")
        ghostpad = Gst.GhostPad.new("sink", pad)
        bin.add_pad(ghostpad)
        cairooverlay = Gst.ElementFactory.make("cairooverlay")
        bin.add(cairooverlay)
        cairooverlay.connect('draw', self.on_draw)
        convert1.link(cairooverlay)
        convert2 = Gst.ElementFactory.make("videoconvert")
        bin.add(convert2)
        cairooverlay.link(convert2)
        videosink = Gst.ElementFactory.make("xvimagesink")
        bin.add(videosink)
        convert2.link(videosink)

        self.pipeline.preview_set_video_sink(bin)

        window = Gtk.Window()
        window.set_title("Averoid Adventures")

        #drawing_area = Gtk.DrawingArea()
        #drawing_area.set_double_buffered (True)
        #drawing_area.set_name("drawing_area")
        #drawing_area.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(255, 255, 255, 255))
        window.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(255, 255, 0, 255))

        #window.add(drawing_area)

        accel = Gtk.AccelGroup()
        accel.connect(Gdk.keyval_from_name('Q'), 0, 0, self.on_q_pressed)
        accel.connect(Gdk.keyval_from_name('A'), 0, 0, self.on_a_pressed)
        window.add_accel_group(accel)

        window.connect("delete-event", self.window_closed)

        window.show_all()
        window.realize()
        window.fullscreen()

        xid = window.get_window().get_xid()
        videosink.set_window_handle (xid)

        
        #overlay.move(0, 0)

        #button = QPushButton("push me", player)
        #button.show()

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
        time = self.asset.get_base_time()
        print(time)
        self.choices.draw(context, timestamp)
        self.choices.update()

    def on_q_pressed(self, *args):
        self.quit()

    def on_a_pressed(self, *args):
        pass

    def quit(self):
        self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()
        exit(0)

    def window_closed(self, widget, event):
        self.quit()

    def error(self, error):
        print("Error: {}".format(error))

 
if __name__ == '__main__':
    Gst.init(None)
    GES.init()
    GObject.threads_init()
    Gst.init(None)
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    world = World(args.filename)

    player = Player()

    video = world.get_video()
    player.openFile(video)

    mainLoop = GLib.MainLoop.new(None, False)
    GLib.MainLoop().run()
