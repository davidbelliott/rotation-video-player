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
import threading
import pygame
from collections import OrderedDict
from enum import Enum
from multiprocessing.connection import Listener


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
        self.fill = json_data['fill']
        self.stroke = json_data['stroke']
        self.x = json_data['x']
        self.y = json_data['y']


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


MAX_SPEED = 0.5
DAMPING = 0.1
class ChoiceBox:
    
    def __init__(self, text, pattern, color, x, y, border=True, reftext='', display_x=None, display_y=None, choosable=False):
        self.text = text
        self.pattern = pattern
        self.color = color
        self.x = x
        self.display_x = x if display_x == None else display_x
        self.y = y
        self.display_y = y if display_y == None else display_y
        self.border = border
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


        context.set_source_rgba(*self.color)
        if self.border:
            context.rectangle(self.display_x, self.display_y, extents.width + 2 * margin, extents.height + 2 * margin)
            dashes = [30.0, 10.0]
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

        x = choice.x
        y = choice.y
        dy = 100
        dx = 0
        fill = cairo.SolidPattern(*choice.fill)
        stroke = choice.stroke
        #print("LONGEST: {}".format(longest_text))

        self.boxes['prompt'] = ChoiceBox(choice.prompt, fill, stroke, x, y, False, longest_text, 1920, 1080)
        for name, option in choice.options.items():
            y += dy
            x += dx
            self.boxes[name] = ChoiceBox(option.text, fill, stroke, x, y, True, longest_text, 1920, 1080)

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


LISTEN_ADDRESS = ('localhost', 6000)
AUTHKEY = b'overthrow'


class Player:
 
    def __init__(self, world):
        # member initialization
        self.world = world
        #self.choices = ChoiceDialog(["WHERE TO NEXT?", "UPSTAIRS", "GROUND FLOOR"])
        self.active_dialog = None
        self.fullscreen = False

        #GES stuff
        '''self.timeline = GES.Timeline.new_audio_video()
        self.layer = GES.Layer()
        self.timeline.add_layer(self.layer)
        self.openFile(videoFile)

        self.pipeline = GES.Pipeline()
        self.pipeline.set_timeline(self.timeline)
        self.pipeline.set_state(Gst.State.PAUSED)

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

        #TODO: uncomment these
        self.window.show_all()
        self.window.realize()
        xid = self.window.get_window().get_xid()
        videosink.set_window_handle (xid)'''



        #state machine stuff
        self.state = STATE_IDLE
        self.state_funcs = {
            STATE_IDLE: [self.enter_idle_cb, self.idle_cb, None],
            STATE_CHOICE: [self.enter_choice_cb, self.choice_cb, self.leave_choice_cb],
            STATE_JUMP: [self.enter_jump_cb, None, None]
        }
        self.next_label_time = -1 #TODO: better solution


        time.sleep(1)
        self.jump_label(self.world.current_label)
        #TODO: uncomment
        #self.pipeline.set_state(Gst.State.PLAYING)



    def update(self):
        cur_callbacks = self.state_funcs[self.state]
        if cur_callbacks[CB_RUN] != None:
            cur_callbacks[CB_RUN]()

    def set_state(self, new_state):
        print("Changed state to {}".format(new_state))
        exit_cb = self.state_funcs[self.state][CB_ON_EXIT]
        enter_cb = self.state_funcs[new_state][CB_ON_ENTER]
        self.state = new_state
        if exit_cb:
            exit_cb()
        if enter_cb:
            enter_cb()
        print("Done changing state to {}".format(new_state))

    def jump_label(self, new_label):
        lbl = Label(new_label, self.world.data['labels'][new_label])
        self.seek(lbl.time * 1e9)
        self.set_label(new_label)

    def set_label(self, new_label):
        label_json = self.world.data['labels'][new_label]
        self.curr_label = Label(new_label, label_json)
        print("Set label to {}".format(new_label))
        if self.curr_label.jump != None:
            print("Setting state to JUMP")
            self.set_state(STATE_JUMP)
        elif self.curr_label.choice != None:
            print("Setting state to CHOICE")
            self.set_state(STATE_CHOICE)
        else:
            print("Setting state to IDLE")
            self.set_state(STATE_IDLE)

    def enter_idle_cb(self):
        if self.curr_label.next != '':
            self.next_label_time = self.world.data['labels'][self.curr_label.next]['time']
        else:
            self.next_label_time = -1

    def idle_cb(self):
        '''timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
        if self.next_label_time != -1 and timestamp > self.next_label_time * 1e9:
            print("IDLE Setting label to {}".format(self.curr_label.next))
            self.set_label(self.curr_label.next)'''

    def enter_choice_cb(self):
        timestamp = self.curr_label.time
        self.active_dialog = ChoiceDialog(self.curr_label.choice)
        self.next_label_time = timestamp + self.curr_label.choice.duration
        print("timestamp: {}".format(timestamp))
        print("next label time: {}".format(self.next_label_time))

    def leave_choice_cb(self):
        self.active_dialog = None

    def choice_cb(self):
        if self.curr_label.choice:
            timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
            print("timestamp: {}".format(timestamp))
            print("next label time: {}".format(self.next_label_time))
            if timestamp > self.next_label_time * 1e9:
                chosen_option_name = None
                max_num_votes = -1
                for name, option in self.curr_label.choice.options.items():
                    if option.votes > max_num_votes:
                        chosen_option_name = name
                        max_num_votes = option.votes
                jump = self.curr_label.choice.options[chosen_option_name].jump
                print("CHOICE Setting label to {}".format(jump))
                self.jump_label(jump)


    def enter_jump_cb(self):
        jump_label_name = self.curr_label.jump
        self.jump_label(jump_label_name)

    def vote_cb(self, option):
        print("Vote callback")
        if self.active_dialog and type(self.active_dialog) == ChoiceDialog:
            if option in self.active_dialog.choice.options:
                self.active_dialog.choice.options[option].votes += 1
                play_sound(audioFile)

 
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


    def seek(self, location):
        """
        @param location: time to seek to, in nanoseconds
        """
        print("seeking to %r" % location)

        #TODO: uncomment
        #self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, location)

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
        self.update()
        if self.active_dialog != None:
            self.active_dialog.draw(context, timestamp)
            self.active_dialog.update()

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


def listen(player):
    listener = Listener(LISTEN_ADDRESS, authkey=AUTHKEY)
    conn = listener.accept()
    print("Connection accepted from {}".format(listener.last_accepted))
    while True:
        msg = conn.recv()
        if msg == 'close':
            conn.close()
            break
        player.vote_cb(msg)
    listener.close()

 
if __name__ == '__main__':
    # Call library init functions
    Gst.init(None)
    GES.init()
    GObject.threads_init()
    Gst.init(None)
    pygame.init()
    #pygame.mixer.init() #TODO: uncomment this

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    # Initialize objects
    world = World(args.filename)
    player = Player(world)

    # Start listener thread
    thread = threading.Thread(target=listen, args=[player]);
    thread.start()

    # Run main loop
    GLib.MainLoop().run()
