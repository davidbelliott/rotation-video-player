#!/usr/bin/env python
 
import os, sys
import argparse
import json
import time
import threading
import pygame
from collections import OrderedDict
from enum import Enum
from socketIO_client import SocketIO, LoggingNamespace
from queue import Queue

import random
import cairo
import gi
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import GES, Gtk, Gdk, Gst, GObject, GstVideo, GLib


SERVER_URL = 'localhost'
SERVER_PORT = 5000

mainLoop = GLib.MainLoop.new(None, False)

_sound_library = {}
def play_sound(path):
    '''global _sound_library
    sound = _sound_library.get(path)
    if sound == None:
        canonicalized_path = path.replace('/', os.sep).replace('\\', os.sep)
        sound = pygame.mixer.Sound(canonicalized_path)
        _sound_library[path] = sound
    sound.play()'''

videoFile = "file:///home/david/gdrive/avery_house/rotation_video/rotation-video-player/videos/main.mp4"
audioFile = "/home/david/gdrive/avery_house/rotation_video/rotation-video-player/videos/ding.wav"


class Option:
    @classmethod
    def from_json(cls, json_data):
        return cls(json_data['text'], json_data['jumpto'])

    def __init__(self, text, jumpto):
        self.text = text
        self.jumpto = jumpto
        self.votes = 0


class Choice:
    @classmethod
    def from_json(cls, json_data):
        prompt = json_data['prompt']
        options = {key: Option.from_json(value) for (key, value) in json_data['options'].items()}
        duration = json_data['duration']
        fill = json_data['fill']
        stroke = json_data['stroke']
        x = json_data['x']
        y = json_data['y']
        return cls(prompt, options, duration, fill, stroke, x, y)


    def __init__(self, prompt, options, duration=20, fill=[1, 1, 1, 1], stroke=[1, 1, 1, 1], x=700, y=500, room=None):
        self.prompt = prompt
        self.options = options
        self.duration = duration
        self.fill = fill
        self.stroke = stroke
        self.x = x
        self.y = y
        self.room = room

    def make_json_data(self):
        self_data = {"prompt": self.prompt, "options": {name: option.text for name, option in self.options.items()}, "room": self.room}
        print("SELF DATA: {}".format(self_data))
        return self_data


class Label:
    def __init__(self, name, json_data):
        self.name = name
        self.time = json_data['time']
        self.flowto = json_data['flowto'] if 'flowto' in json_data else None
        self.choice = Choice.from_json(json_data['choice']) if 'choice' in json_data else None
        self.jumpto = json_data['jumpto'] if 'jumpto' in json_data else None
        self.sportsball_quarter = SportsballQuarter(json_data['sportsball_quarter']) if 'sportsball_quarter'in json_data else None


class SportsballPlayer:
    def __init__(self, name, json_data, room_index):
        self.name = name
        self.ability_choice = Choice(name, {value: Option(key, value) for (key, value) in json_data['abilities'].items()}, room=str(room_index), x = json_data['x'], y = json_data['y'])

class SportsballGame:
    def __init__(self, json_data):
        room_index = 0
        self.players = []
        for (key, value) in json_data['players'].items():
            self.players.append(SportsballPlayer(key, value, room_index))
            room_index += 1

class SportsballQuarter:
    def __init__(self, json_data):
        self.duration = json_data['duration']
        self.required_move = json_data['required_move']
        self.enemy_moves = json_data['enemy_moves']
        self.lose_label = json_data['lose_label']
        self.win_label = json_data['win_label']


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

        self.sportsball = SportsballGame(self.data["sportsball"])


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
STATE_SPORTSBALL = 3

# indices of state_funcs
CB_ON_ENTER = 0
CB_RUN = 1
CB_ON_EXIT = 2


LISTEN_ADDRESS = ('localhost', 6000)
AUTHKEY = b'overthrow'


class Player:
 
    def __init__(self, world, socketIO):
        # member initialization
        self.world = world
        self.socketIO = socketIO
        #self.choices = ChoiceDialog(["WHERE TO NEXT?", "UPSTAIRS", "GROUND FLOOR"])
        self.active_dialogs = []
        self.label_queue = Queue()
        self.fullscreen = False

        #GES stuff
        self.timeline = GES.Timeline.new_audio_video()
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

        self.window.show_all()
        self.window.realize()
        xid = self.window.get_window().get_xid()
        videosink.set_window_handle (xid)



        #state machine stuff
        self.state = STATE_IDLE
        self.state_funcs = {
            STATE_IDLE: [self.enter_idle_cb, self.idle_cb, None],
            STATE_CHOICE: [self.enter_choice_cb, self.choice_cb, self.leave_choice_cb],
            STATE_JUMP: [self.enter_jump_cb, None, None],
            STATE_SPORTSBALL: [self.enter_sportsball_cb, self.sportsball_cb, self.leave_sportsball_cb]
        }
        self.end_label_time = -1 #TODO: better solution


        time.sleep(1)
        self.jump_label(self.world.current_label)
        self.pipeline.set_state(Gst.State.PLAYING)



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

    def enqueue_label(self, new_label):
        self.label_queue.put(new_label)

    def jump_label(self, new_label):
        print("Jumping to label")
        if new_label == "queued":
            if self.label_queue.empty():
                return
            new_label = self.label_queue.get_nowait()
        try:
            timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
            lbl = Label(new_label, self.world.data['labels'][new_label])
            if abs(lbl.time * 1e9 - timestamp) > 0.1 * 1e9:
                print("Cur time: {}".format(timestamp))
                print("Label time: {}".format(lbl.time * 1e9))
                self.seek(lbl.time * 1e9)
            self.set_label(new_label)
        except KeyError:
            print("Error: nonexistent label {}".format(new_label))

    def set_label(self, new_label):
        print("Setting label")
        label_json = self.world.data['labels'][new_label]
        self.curr_label = Label(new_label, label_json)
        print("Set label to {}".format(new_label))
        if self.curr_label.sportsball_quarter != None:
            print("Setting state to SPORTSBALL")
            self.set_state(STATE_SPORTSBALL)
        elif self.curr_label.jumpto != None:
            print("Setting state to JUMP")
            self.set_state(STATE_JUMP)
        elif self.curr_label.choice != None:
            print("Setting state to CHOICE")
            self.set_state(STATE_CHOICE)
        else:
            print("Setting state to IDLE")
            self.set_state(STATE_IDLE)

    def enter_idle_cb(self):
        if self.curr_label.flowto != '':
            self.end_label_time = self.world.data['labels'][self.curr_label.flowto]['time']
        else:
            self.end_label_time = -1

    def idle_cb(self):
        timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
        if self.end_label_time > 0 and timestamp > self.end_label_time * 1e9:
            print("IDLE Setting label to {}".format(self.curr_label.flowto))
            self.set_label(self.curr_label.flowto)

    def enter_choice_cb(self):
        timestamp = self.curr_label.time
        self.active_dialogs = [ChoiceDialog(self.curr_label.choice)]
        self.end_label_time = timestamp + self.curr_label.choice.duration
        self.socketIO.emit("show_choice", self.curr_label.choice.make_json_data())
        #print("timestamp: {}".format(timestamp))
        #print("end label time: {}".format(self.end_label_time))

    def leave_choice_cb(self):
        self.active_dialogs = []
        print("CLEARING CHOICE")
        self.socketIO.emit("clear_choice")

    def choice_cb(self):
        if self.curr_label.choice:
            timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
            #print("timestamp: {}".format(timestamp))
            #print("end label time: {}".format(self.end_label_time))
            if timestamp > self.end_label_time * 1e9:
                chosen_option_name = None
                max_num_votes = -1
                for name, option in self.curr_label.choice.options.items():
                    if option.votes > max_num_votes:
                        chosen_option_name = name
                        max_num_votes = option.votes
                jumpto = self.curr_label.choice.options[chosen_option_name].jumpto
                print("CHOICE Setting label to {}".format(jumpto))
                self.jump_label(jumpto)


    def enter_sportsball_cb(self):
        timestamp = self.curr_label.time
        self.active_dialogs = []
        for player in self.world.sportsball.players:
            new_dialog = ChoiceDialog(player.ability_choice)
            self.active_dialogs.append(new_dialog)
        self.end_label_time = timestamp + self.curr_label.sportsball_quarter.duration
        # Emit choice show event for each different player in corresponding room
        for i, player in enumerate(self.world.sportsball.players):
            self.socketIO.emit("show_choice", player.ability_choice.make_json_data())

    def leave_sportsball_cb(self):
        self.active_dialogs = []    # Clear active dialogs
        print("CLEARING CHOICE")
        self.socketIO.emit("clear_choice")

    def sportsball_cb(self):
        timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
        #print("timestamp: {}".format(timestamp))
        #print("end label time: {}".format(self.end_label_time))
        required_move_used = False
        if timestamp > self.end_label_time * 1e9:
            for i, player in enumerate(self.world.sportsball.players):
                chosen_move = None
                max_num_votes = -1
                for name, option in player.ability_choice.options.items():
                    if option.votes > max_num_votes:
                        chosen_move = name
                        max_num_votes = option.votes
                label_to_queue = player.ability_choice.options[chosen_move].jumpto
                print("SPORTSBALL enqueue label {}".format(label_to_queue))

                if label_to_queue == self.curr_label.sportsball_quarter.required_move:
                    # Play the enemy moves, if any
                    if self.curr_label.sportsball_quarter.enemy_moves:
                        for move in self.curr_label.sportsball_quarter.enemy_moves:
                            self.enqueue_label(move)
                    # Play the winning move (must go last into the queue)
                    self.enqueue_label(label_to_queue)
                    required_move_used = True
                    break
                self.enqueue_label(label_to_queue)


            if required_move_used:
                self.enqueue_label(self.curr_label.sportsball_quarter.win_label)
            # Lose if no winning move
            else:
                # Play the enemy moves, if any
                if self.curr_label.sportsball_quarter.enemy_moves:
                    for move in self.curr_label.sportsball_quarter.enemy_moves:
                        self.enqueue_label(move)
                self.enqueue_label(self.curr_label.sportsball_quarter.lose_label)
                self.enqueue_label(self.curr_label.name)    # retry from current label

            self.jump_label("queued")


    def enter_jump_cb(self):
        jump_label_name = self.curr_label.jumpto
        self.jump_label(jump_label_name)

    def vote_cb(self, option):
        print("Vote callback: {}".format(option))
        if self.active_dialogs:
            for dialog in self.active_dialogs:
                if type(dialog) == ChoiceDialog and option in dialog.choice.options:
                    dialog.choice.options[option].votes += 1
                    play_sound(audioFile)
                    break

 
    def openFile(self, fileName):
        print(videoFile)
        self.asset = GES.UriClipAsset.request_sync(videoFile)
        self.layer.add_asset(self.asset, 0, 0, self.asset.get_duration(), self.asset.get_supported_formats())
        self.timeline.commit()

 
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

    def seek(self, location):
        print("seeking to %r" % location)
        self.pipeline.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, location)


    def on_draw(self, _overlay, context, timestamp, _duration):
        (_, duration) = self.pipeline.query_duration(Gst.Format.TIME)
        self.update()
        if self.active_dialogs:
            for dialog in self.active_dialogs:
                dialog.draw(context, timestamp)
                dialog.update()

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


class SocketIOListener:

    def __init__(self, player, socketIO):
        self.player = player
        self.socketIO = socketIO

    def on_connect(self):
        print('connected')

    def on_disconnect(self):
        print('disconnected')

    def on_reconnect(self):
        print('reconnected')

    def on_cast_vote(self, data):
        self.player.vote_cb(data)

def listen_to_server(player, socketIO):
    try:
        listener = SocketIOListener(player, socketIO)
        socketIO.on('connect', listener.on_connect)
        socketIO.on('disconnect', listener.on_disconnect)
        socketIO.on('reconnect', listener.on_reconnect)
        socketIO.on('cast_vote', listener.on_cast_vote)
        socketIO.emit('join', {'is_movie_player': True})
        socketIO.emit('clear_choice')
        socketIO.wait()
    except ConnectionError:
        print('Connection error')
    except KeyboardInterrupt:
        print('Keyboard interrupt')



 
if __name__ == '__main__':
    # Call library init functions
    Gst.init(None)
    GES.init()
    GObject.threads_init()
    Gst.init(None)
    #pygame.init()
    #pygame.mixer.init()

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()

    # Initialize objects
    world = World(args.filename)
    socketIO = SocketIO(SERVER_URL, SERVER_PORT, LoggingNamespace)
    player = Player(world, socketIO)

    # Start listener thread
    thread = threading.Thread(target=listen_to_server, args=[player, socketIO], daemon=True);
    thread.start()

    # Run main loop
    GLib.MainLoop().run()
