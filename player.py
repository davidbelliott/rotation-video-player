#!/usr/bin/env python
 
import os, sys
import argparse
import json
import time
import threading
from collections import OrderedDict
from enum import Enum
from socketIO_client import SocketIO, LoggingNamespace
from queue import Queue
from uuid import uuid4
from random_words import RandomWords

import random
import cairo
import subprocess
import urllib
import gi
gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import GES, Gtk, Gdk, Gst, GObject, GstVideo, GLib


SERVER_URL = 'https://avery.caltech.edu/'
MEDIA_PATH = 'videos/'

mainLoop = GLib.MainLoop.new(None, False)
rw = RandomWords()
random.seed()

def play_sound(path):
    subprocess.Popen(["ffplay", "-nodisp", "-autoexit", path])

music_proc = None
def play_music(path):
    global music_proc
    if music_proc:
        music_proc.kill()
        music_proc = None
    print("Playing music: {}".format(path))
    music_proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loop", "0", path])

def stop_music():
    global music_proc
    print("Stopping music")
    if music_proc:
        music_proc.kill()
        music_proc = None


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
        dx = json_data['dx'] if 'dx' in json_data else 0
        dy = json_data['dy'] if 'dy' in json_data else 100
        draw_prompt = json_data['draw_prompt'] if 'draw_prompt' in json_data else True
        return cls(prompt, options, duration, fill, stroke, x, y, dx, dy, draw_prompt)


    def __init__(self, prompt, options, duration=20, fill=[1, 1, 1, 0.25], stroke=[1, 1, 1, 1], x=700, y=500, dx=0, dy=100, draw_prompt=True, room=None):
        self.prompt = prompt
        self.options = options
        self.duration = duration
        self.fill = fill
        self.stroke = stroke
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.draw_prompt = draw_prompt
        self.room = room

    def make_json_data(self, choice_dialog):
        self_data = {"prompt": self.prompt, "options": {name: option.text for name, option in self.options.items()}, "room": self.room, "uuid": choice_dialog.uuid}
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
        self.poem = Poem(json_data['poem']) if 'poem' in json_data else None
        self.play_music = PlayMusic(json_data['play_music']) if 'play_music' in json_data else None
        self.stop_music = StopMusic(json_data['stop_music']) if 'stop_music' in json_data else None


class PlayMusic:
    def __init__(self, json_data):
        self.filename = json_data["filename"]
        self.on = json_data["on"]

class StopMusic:
    def __init__(self, json_data):
        self.on = json_data["on"]

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

class Poem:
    def __init__(self, json_data):
        self.duration = json_data['duration']
        self.max_words = json_data['max_words']
        self.girl_options = json_data['girl_options']
        self.jumpto = json_data['jumpto']
        self.words = []
        self.liked_words = []
        self.girl = None

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
        self.uuid = uuid4().hex

        # get longest text
        texts = [option.text for (key, option) in choice.options.items()]
        if choice.draw_prompt:
            texts.insert(0, choice.prompt)
        longest_text = max(texts, key=len)

        x = choice.x
        y = choice.y
        dy = choice.dy
        dx = choice.dx
        fill = cairo.SolidPattern(*choice.fill)
        stroke = choice.stroke
        #print("LONGEST: {}".format(longest_text))

        if choice.draw_prompt:
            self.boxes['prompt'] = ChoiceBox(choice.prompt, fill, stroke, x, y, False, longest_text, 1920, 1080)
            y += dy
            x += dx
        for name, option in choice.options.items():
            self.boxes[name] = ChoiceBox(option.text, fill, stroke, x, y, True, longest_text, 1920, 1080)
            y += dy
            x += dx

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

class PoemDialog:

    def __init__(self, poem):
        self.poem = poem
        self.uuid = uuid4().hex
        self.title_x = 100
        self.title_y = 100
        self.starting_x = 100
        self.starting_y = 200

    def draw(self, context, timestamp):
        context.move_to(self.title_x, self.title_y)
        context.select_font_face('Noto Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(60)
        context.set_source_rgba(1, 1, 1, 1)
        if not self.poem.girl:
            context.text_path("Let's write a poem! Everybody choose a word!")
        else:
            context.text_path("{} loves these words you used!".format(self.poem.girl))
        context.fill()
        context.move_to(self.starting_x, self.starting_y)
        context.select_font_face('Noto Sans', cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_BOLD)
        for word in self.poem.words:
            context.set_font_size(40)
            if word in self.poem.liked_words:
                context.set_source_rgba(1, 0, 0, 1)
                context.text_path(word)
            else:
                if not self.poem.girl:
                    context.set_source_rgba(1, 1, 1, 1)
                    context.text_path(word)
            (x, y) = context.get_current_point()
            print("({}, {})".format(x, y))
            if x > 1700:
                x = self.starting_x
                y += 50
            else:
                x += 20
            context.move_to(x, y)
        context.fill()

    def update(self):
        pass

STATE_IDLE = 0
STATE_CHOICE = 1
STATE_JUMP = 2
STATE_SPORTSBALL = 3
STATE_POEM = 4

# indices of state_funcs
CB_ON_ENTER = 0
CB_RUN = 1
CB_ON_EXIT = 2


class Player:
 
    def __init__(self, world, socketIO):
        # member initialization
        self.world = world
        self.socketIO = socketIO
        #self.choices = ChoiceDialog(["WHERE TO NEXT?", "UPSTAIRS", "GROUND FLOOR"])
        self.active_dialogs = []
        self.users = []
        self.label_queue = Queue()
        self.curr_label = None
        self.fullscreen = False
        self.girl = None

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
            STATE_IDLE: [self.enter_idle_cb, self.idle_cb, self.leave_idle_cb],
            STATE_CHOICE: [self.enter_choice_cb, self.choice_cb, self.leave_choice_cb],
            STATE_JUMP: [self.enter_jump_cb, self.jump_cb, self.leave_jump_cb],
            STATE_SPORTSBALL: [self.enter_sportsball_cb, self.sportsball_cb, self.leave_sportsball_cb],
            STATE_POEM: [self.enter_poem_cb, self.poem_cb, self.leave_poem_cb]
        }
        self.end_label_time = -1 #TODO: better solution


        time.sleep(1)
        self.jump_label(self.world.current_label)
        self.pipeline.set_state(Gst.State.PLAYING)



    def update(self):
        cur_callbacks = self.state_funcs[self.state]
        if cur_callbacks[CB_RUN] != None:
            cur_callbacks[CB_RUN]()

    def enqueue_label(self, new_label):
        self.label_queue.put(new_label)

    def jump_label(self, new_label):
        print("Jumping to label")
        if new_label == "queued":
            if self.label_queue.empty():
                return
            new_label = self.label_queue.get_nowait()
        if self.girl:
            print("Replacing with {}".format(self.girl))
            new_label = new_label.replace("{girl}", self.girl)
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
        lbl = Label(new_label, label_json)
        new_state = STATE_IDLE
        if lbl.poem != None:
            new_state = STATE_POEM
        elif lbl.sportsball_quarter != None:
            new_state = STATE_SPORTSBALL
        elif lbl.jumpto != None:
            new_state = STATE_JUMP
        elif lbl.choice != None:
            new_state = STATE_CHOICE

        exit_cb = self.state_funcs[self.state][CB_ON_EXIT]
        enter_cb = self.state_funcs[new_state][CB_ON_ENTER]
        if exit_cb and self.curr_label:
            exit_cb()
        self.state = new_state
        self.curr_label = lbl
        if enter_cb:
            enter_cb()
        print("Done changing state to {}".format(new_state))

    def enter_any_cb(self):
        if self.curr_label.play_music and self.curr_label.play_music.on == "enter":
            play_music(MEDIA_PATH + self.curr_label.play_music.filename)
        if self.curr_label.stop_music and self.curr_label.stop_music.on == "enter":
            stop_music()

    def any_cb(self):
        pass

    def leave_any_cb(self):
        if self.curr_label.play_music and self.curr_label.play_music.on == "exit":
            play_music(MEDIA_PATH + self.curr_label.play_music.filename)
        if self.curr_label.stop_music and self.curr_label.stop_music.on == "exit":
            stop_music()

    def enter_idle_cb(self):
        self.enter_any_cb()
        if self.curr_label.flowto != '':
            self.end_label_time = self.world.data['labels'][self.curr_label.flowto]['time']
        else:
            self.end_label_time = -1

    def idle_cb(self):
        self.any_cb()
        timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
        if self.end_label_time > 0 and timestamp > self.end_label_time * 1e9:
            print("IDLE Setting label to {}".format(self.curr_label.flowto))
            self.set_label(self.curr_label.flowto)

    def leave_idle_cb(self):
        self.leave_any_cb()

    def enter_choice_cb(self):
        self.enter_any_cb()
        timestamp = self.curr_label.time
        self.active_dialogs = [ChoiceDialog(self.curr_label.choice)]
        self.end_label_time = timestamp + self.curr_label.choice.duration
        if self.socketIO:
            self.socketIO.emit("show_choice", self.curr_label.choice.make_json_data(self.active_dialogs[0]))
        #print("timestamp: {}".format(timestamp))
        #print("end label time: {}".format(self.end_label_time))

    def choice_cb(self):
        self.any_cb()
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


    def leave_choice_cb(self):
        self.leave_any_cb()
        self.active_dialogs = []
        print("CLEARING CHOICE")
        if self.socketIO:
            self.socketIO.emit("clear_choice")


    def enter_sportsball_cb(self):
        self.enter_any_cb()
        timestamp = self.curr_label.time
        self.active_dialogs = []
        for player in self.world.sportsball.players:
            for name, option in player.ability_choice.options.items():
                print("Option: {}".format(option))
                option.votes = 0
            new_dialog = ChoiceDialog(player.ability_choice)
            self.active_dialogs.append(new_dialog)
            # Emit choice show event for each different player in corresponding room
            if self.socketIO:
                self.socketIO.emit("show_choice", player.ability_choice.make_json_data(new_dialog))
        self.end_label_time = timestamp + self.curr_label.sportsball_quarter.duration

    def sportsball_cb(self):
        self.any_cb()
        '''if random.randint(0,100) == 0:
            self.vote_cb("evan_pep_talk")
            for i, player in enumerate(self.world.sportsball.players):
                for name, option in player.ability_choice.options.items():
                    if random.randint(0, 5) == 0:
                        self.vote_cb(name)
                        break'''

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

    def leave_sportsball_cb(self):
        self.leave_any_cb()
        self.active_dialogs = []    # Clear active dialogs
        print("CLEARING CHOICE")
        if self.socketIO:
            self.socketIO.emit("clear_choice")


    def enter_poem_cb(self):
        self.enter_any_cb()
        print("ENTERING POEM")
        timestamp = self.curr_label.time
        self.active_dialogs = [PoemDialog(self.curr_label.poem)]
        self.end_label_time = timestamp + self.curr_label.poem.duration
        print("Poem duration: {}".format(self.curr_label.poem.duration))
        if self.socketIO:
            for user in self.users:
                words = rw.random_words(count=5)
                self.socketIO.emit("show_choice", Choice("Choose a word for the poem", {word: Option(word, None) for word in words}, self.curr_label.poem.duration, room=user).make_json_data(self.active_dialogs[0]))

    def poem_cb(self):
        self.any_cb()
        print(self.curr_label.poem.words)
        timestamp = self.pipeline.query_position(Gst.Format.TIME)[1]
        #print("timestamp: {}".format(timestamp))
        #print("end label time: {}".format(self.end_label_time))
        if timestamp > (self.end_label_time - 5) * 1e9 and not self.girl:
            self.girl = "natsuki"#random.choice(self.curr_label.poem.girl_options)
            self.active_dialogs[0].poem.girl = self.girl
            self.active_dialogs[0].poem.liked_words = random.sample(self.curr_label.poem.words, min(len(self.curr_label.poem.words), 5))
            print("LIKED WORDS: {}".format(self.active_dialogs[0].poem.liked_words))
        if timestamp > self.end_label_time * 1e9:
            jumpto = self.curr_label.poem.jumpto
            print("POEM Setting label to {}".format(jumpto))
            self.jump_label(jumpto)

    def leave_poem_cb(self):
        self.leave_any_cb()
        self.active_dialogs = []
        print("CLEARING CHOICE")
        if self.socketIO:
            self.socketIO.emit("clear_choice")

    def enter_jump_cb(self):
        self.enter_any_cb()
        jump_label_name = self.curr_label.jumpto
        self.jump_label(jump_label_name)

    def jump_cb(self):
        self.any_cb()
    
    def leave_jump_cb(self):
        self.leave_any_cb()

    def vote_cb(self, option):
        print("Vote callback: {}".format(option))
        if self.active_dialogs:
            for dialog in self.active_dialogs:
                if type(dialog) == ChoiceDialog and option in dialog.choice.options:
                    dialog.choice.options[option].votes += 1
                    play_sound(audioFile)
                    break
                if type(dialog) == PoemDialog:
                    print("Appending {}".format(option))
                    dialog.poem.words.append(option)
                    play_sound(audioFile)
                    break

    def add_user(self, user_id, voted):
        self.users.append(user_id)
        if self.active_dialogs and type(self.active_dialogs[0]) == ChoiceDialog:
            curr_choice = self.active_dialogs[0].choice
            print("Curr uuid: {} | Voted uuid: {}".format(self.active_dialogs[0].uuid, voted))
            if self.active_dialogs[0].uuid != voted:
                send_choice = Choice(curr_choice.prompt, curr_choice.options, room=user_id)
                self.socketIO.emit("show_choice", send_choice.make_json_data(self.active_dialogs[0]))


    def remove_user(self, user_id):
        self.users.remove(user_id)

 
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
        stop_music()
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

    def on_user_joined(self, data):
        print("User joined: {}, {}".format(data["id"], data["voted"]))
        self.player.add_user(data["id"], data["voted"])

    def on_user_left(self, data):
        print("User left: {}".format(data["id"]))
        self.player.remove_user(data["id"])

    def on_users(self, data):
        print("Users received: {}".format(data))
        self.player.users = data

def listen_to_server(player, socketIO):
    try:
        listener = SocketIOListener(player, socketIO)
        socketIO.on('connect', listener.on_connect)
        socketIO.on('disconnect', listener.on_disconnect)
        socketIO.on('reconnect', listener.on_reconnect)
        socketIO.on('cast_vote', listener.on_cast_vote)
        socketIO.on('user_joined', listener.on_user_joined)
        socketIO.on('user_left', listener.on_user_left)
        socketIO.on('users', listener.on_users)
        socketIO.emit('join', {'is_movie_player': True})
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

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('filename')
    args = parser.parse_args()


    # Initialize objects
    world = World(args.filename)
    socketIO = SocketIO(SERVER_URL)
    player = Player(world, socketIO)
    #socketIO = None
    # Start listener thread
    if socketIO:
        thread = threading.Thread(target=listen_to_server, args=[player, socketIO], daemon=True);
        thread.start()

    # Run main loop
    GLib.MainLoop().run()
