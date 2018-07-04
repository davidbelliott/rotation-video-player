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
import pygame
from collections import OrderedDict
from enum import Enum


import random
import cairo
import gi
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import GES, Gtk, Gdk, Gst, GObject, GstVideo, GLib
mainLoop = GLib.MainLoop.new(None, False)

_sound_library = {}
def play_sound(path):
    global _sound_library
    sound = _sound_library.get(path)
    if sound == None:
        canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
        sound = pygame.mixer.Sound(canonicalized_path)
        _sound_library[path] = sound
    sound.play()

videoFile = "file:///home/david/gdrive/avery_house/rotation_video/player/videos/main.mp4"
audioFile = "/home/david/gdrive/avery_house/rotation_video/player/videos/ding.wav"


class Option:
    def __init__(self, json_data):
        self.text = json_data['text']
        self.jump = json_data['jump']
        self.votes = 0

class Choice:
    def __init__(self, json_data):
        self.prompt = json_data['prompt']
        self.options = {key: Option(value) for (key, value) in json_data['options'].items()}
        self.duration = json_data['duration']


class Label:
    def __init__(self, name, json_data):
        self.name = name
        self.time = json_data['time']
        self.next = json_data['next'] if 'next' in json_data else None
        self.choice = Choice(json_data['choice']) if 'choice' in json_data else None
        self.jump = json_data['jump'] if 'jump' in json_data else None


class World:
    def __init__(self, filename):
        self.world_path = os.path.abspath(filename)
        self.video_path = os.path.join(os.path.dirname(self.world_path), "videos")
        with open(self.world_path) as json_datafile:
            self.data = json.load(json_datafile, object_pairs_hook=OrderedDict)
        print(json.dumps(self.data, indent=4))
        self.labels = self.data["labels"]
        self.current_label = self.data["starting_label"]
        self.current_label_index = list(self.data["labels"].keys()) \
                .index(self.current_label)

    def update(self, player, timestamp):
        return


MAX_SPEED = 0.5
DAMPING = 0.1
class ChoiceBox:
    
    def __init__(self, text, pattern, color, x, y, reftext='', display_x=None, display_y=None, choosable=False):
        self.text = text
        self.pattern = pattern
        self.color = color
        self.x = x
        self.display_x = x if display_x == None else display_x
        self.y = y
        self.display_y = y if display_y == None else display_y
        self.reftext = reftext
        display_x_offset = self.display_x - self.x
        display_y_offset = self.display_y - self.y
        self.vx = random.uniform(-MAX_SPEED-display_x_offset*DAMPING, MAX_SPEED-display_x_offset*DAMPING)
        self.vy = random.uniform(-MAX_SPEED-display_y_offset*DAMPING, MAX_SPEED-display_y_offset*DAMPING)
        self.fill_percent = 0.0
        self.choosable = choosable

    def update(self):
        self.display_x += self.vx
        self.display_y += self.vy
        display_x_offset = self.display_x - self.x
        display_y_offset = self.display_y - self.y
        if random.randint(0, 5) == 0:
            self.vx = random.uniform(-MAX_SPEED-display_x_offset*DAMPING, MAX_SPEED-display_x_offset*DAMPING)
            self.vy = random.uniform(-MAX_SPEED-display_y_offset*DAMPING, MAX_SPEED-display_y_offset*DAMPING)

        '''if random.randint(0, 100) == 0 and self.choosable:
            self.fill_percent = min(self.fill_percent + 0.1, 1)
            play_sound(audioFile)'''

    def draw(self, context, timestamp):
        context.select_font_face('Noto Sans', cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(40)

        margin = 20

        
        extents = context.text_extents(self.reftext if self.reftext != '' else self.text)
        context.rectangle(self.display_x, self.display_y, (extents.width + 2 * margin)*self.fill_percent, extents.height + 2 * margin)
        context.set_source(self.pattern)
        context.fill()

        context.rectangle(self.display_x, self.display_y, extents.width + 2 * margin, extents.height + 2 * margin)

        dashes = [30.0, 10.0]
        context.set_source_rgba(*self.color)
        context.set_line_width(5)
        context.set_dash(dashes, timestamp / 1E7)
        context.set_line_join(cairo.LINE_JOIN_BEVEL)
        context.stroke()

        context.move_to(self.display_x + margin, self.display_y + extents.height + margin)
        context.text_path(self.text)
        #print(extents)
        context.set_source_rgba(*self.color)
        context.fill()

class ChoiceDialog:

    def __init__(self, choice):
        self.choice = choice
        self.boxes = {}

        # get longest text
        texts = [option.text for (key, option) in choice.options.items()]
        texts.insert(0, choice.prompt)
        longest_text = max(texts, key=len)

        x = 910
        y = 610
        dy = 100
        dx = 0
        #print("LONGEST: {}".format(longest_text))

        self.boxes['prompt'] = ChoiceBox(choice.prompt, cairo.SolidPattern(0.5, 0.5, 0.5, 1), [0, 0, 0, 1], x, y, longest_text, 1920, 1080)
        for name, option in choice.options.items():
            y += dy
            x += dx
            self.boxes[name] = ChoiceBox(option.text, cairo.SolidPattern(0.5, 0.5, 0.5, 1), [0, 0, 0, 1], x, y, longest_text, 1920, 1080)

    def draw(self, context, timestamp):
        for name, box in self.boxes.items():
            box.draw(context, timestamp)

    def update(self):
        total_votes = 0
        for name, box in self.boxes.items():
            if name in self.choice.options:
                total_votes += self.choice.options[name].votes
        for name, box in self.boxes.items():
            if name in self.choice.options:
                fill_percent = self.choice.options[name].votes / total_votes \
                        if total_votes != 0 else 0.0
                box.fill_percent = fill_percent
            box.update()

STATE_IDLE = 0
STATE_CHOICE = 1
STATE_JUMP = 2

# indices of state_funcs
CB_ON_ENTER = 0
CB_RUN = 1
CB_ON_EXIT = 2

class Player:
 
    def __init__(self, world):
        # member initialization
        self.world = world
        #self.choices = ChoiceDialog(["WHERE TO NEXT?", "UPSTAIRS", "GROUND FLOOR"])
        self.active_dialog = None
        self.fullscreen = False


        #state machine stuff
        self.state = STATE_IDLE
        self.state_funcs = {
            STATE_IDLE: [self.enter_idle_cb, self.idle_cb, None],
            STATE_CHOICE: [self.enter_choice_cb, self.choice_cb, self.leave_choice_cb],
            STATE_JUMP: [self.enter_jump_cb, None, None]
        }
        self.set_label(self.world.current_label, 0)

        #GES stuff
        self.timeline = GES.Timeline.new_audio_video()
        self.layer = GES.Layer()
        self.timeline.add_layer(self.layer)
        self.openFile(videoFile)

        self.pipeline = GES.Pipeline()
        self.pipeline.set_timeline(self.timeline)
        self.pipeline.set_state(Gst.State.PLAYING)

        # GES bins
        sinkbin = Gst.Bin.new("sinkbin")
        convert1 = Gst.ElementFactory.make("videoconvert")
        sinkbin.add(convert1)
        pad = convert1.get_static_pad("sink")
        ghostpad = Gst.GhostPad.new("sink", pad)
        sinkbin.add_pad(ghostpad)
        cairooverlay = Gst.ElementFactory.make("cairooverlay")
        sinkbin.add(cairooverlay)
        cairooverlay.connect('draw', self.on_draw)
        convert1.link(cairooverlay)
        convert2 = Gst.ElementFactory.make("videoconvert")
        sinkbin.add(convert2)
        cairooverlay.link(convert2)
        videosink = Gst.ElementFactory.make("xvimagesink")
        sinkbin.add(videosink)
        convert2.link(videosink)
        self.pipeline.preview_set_video_sink(sinkbin)

        # GTK window stuff
        self.window = Gtk.Window()
        self.window.set_title("Averoid Adventures")

        accel = Gtk.AccelGroup()
        accel.connect(Gdk.keyval_from_name('Q'), 0, 0, self.on_q_pressed)
        accel.connect(Gdk.keyval_from_name('F'), 0, 0, self.on_f_pressed)
        self.window.add_accel_group(accel)

        self.window.connect("delete-event", self.window_closed)

        self.window.show_all()
        self.window.realize()
        #window.fullscreen()

        xid = self.window.get_window().get_xid()
        videosink.set_window_handle (xid)

    def update(self, timestamp):
        cur_callbacks = self.state_funcs[self.state]
        if cur_callbacks[CB_RUN] != None:
            cur_callbacks[CB_RUN](timestamp)

    def set_state(self, new_state, timestamp):
        exit_cb = self.state_funcs[self.state][CB_ON_EXIT]
        enter_cb = self.state_funcs[new_state][CB_ON_ENTER]
        if exit_cb:
            exit_cb(timestamp)
        if enter_cb:
            enter_cb(timestamp)
        self.state = new_state

    def jump_label(self, new_label, timestamp):
        set_label(self, new_label, timestamp)

    def set_label(self, new_label, timestamp):
        label_json = self.world.data['labels'][new_label]
        self.curr_label = Label(new_label, label_json)
        if self.curr_label.jump != None:
            print("Setting state to JUMP")
            self.set_state(STATE_JUMP, timestamp)
        elif self.curr_label.choice != None:
            print("Setting state to CHOICE")
            self.set_state(STATE_CHOICE, timestamp)
        else:
            print("Setting state to IDLE")
            self.set_state(STATE_IDLE, timestamp)

    def enter_idle_cb(self, timestamp):
        if self.curr_label.next != '':
            self.next_label_time = self.world.data['labels'][self.curr_label.next]['time']
        else:
            self.next_label_time = -1

    def idle_cb(self, timestamp):
        if self.next_label_time != -1 and timestamp > self.next_label_time * 1e9:
            print("Setting label to {}".format(self.curr_label.next))
            self.set_label(self.curr_label.next, timestamp)

    def enter_choice_cb(self, timestamp):
        self.active_dialog = ChoiceDialog(self.curr_label.choice)
        self.next_label_time = timestamp / 1e9 + self.curr_label.choice.duration

    def leave_choice_cb(self, timestamp):
        self.active_dialog = None

    def choice_cb(self, timestamp):
        if timestamp > self.next_label_time * 1e9:
            chosen_option_name = None
            max_num_votes = 0
            for name, option in self.curr_label.choice.options.items():
                if option.votes > max_num_votes:
                    chosen_option_name = name
                    max_num_votes = option.votes
            jump = self.curr_label.choice.options[chosen_option_name].jump
            print("Setting label to {}".format(jump))
            self.jump_label(jump, timestamp)


    def enter_jump_cb(self, timestamp):
        pass
 
    def openFile(self, fileName):
        self.asset = GES.UriClipAsset.request_sync(videoFile)
        self.layer.add_asset(self.asset, 0, 0, self.asset.get_duration(), self.asset.get_supported_formats())
        self.timeline.commit()
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
        (_, duration) = self.pipeline.query_duration(Gst.Format.TIME)
        #print("{} / {}".format(timestamp/1e9, duration/1e9))
        self.update(timestamp)
        if self.active_dialog != None:
            self.active_dialog.draw(context, timestamp)
            self.active_dialog.update()
            if random.randint(1,100) == 1:
                self.active_dialog.choice.options['upstairs'].votes += 1
                play_sound(audioFile)
            if random.randint(1,100) == 1:
                self.active_dialog.choice.options['downstairs'].votes += 1
                play_sound(audioFile)

    def on_q_pressed(self, *args):
        self.quit()

    def on_f_pressed(self, *args):
        if not self.fullscreen:
            self.window.fullscreen()
            self.fullscreen = True
        else:
            self.window.unfullscreen()
            self.fullscreen = False

    def quit(self):
        self.pipeline.set_state(Gst.State.NULL)
        mainLoop.quit()
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
    pygame.init()
    pygame.mixer.init()
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    world = World(args.filename)
    player = Player(world)


    GLib.MainLoop().run()
