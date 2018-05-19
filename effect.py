#!/usr/bin/python

import gi
gi.require_version('GES', '1.0')
from gi.repository import GES, Gst, GLib, Gtk, Gdk

# File URL http://download.blender.org/peach/trailer/trailer_400p.ogg

videoFile = "file:///home/david/gdrive/avery_house/rotation_video/player/videos/canyon_short.mp4"
videoFile2 = "file:///home/david/gdrive/avery_house/rotation_video/player/videos/jellyfish.mp4"


class Player():
    def __init__(self):
        Gst.init(None)
        GES.init()

        self.timeline = GES.Timeline.new_audio_video()
        
        self.asset = GES.UriClipAsset.request_sync(videoFile)
        self.asset2 = GES.UriClipAsset.request_sync(videoFile2)
        
        self.layer = GES.Layer()
        self.timeline.add_layer(self.layer)
        #layer.add_clip(GES.Asset.extract(asset))
        #layer.add_clip(GES.Asset.extract(asset2))
        self.layer.add_asset(self.asset, 0, 0, self.asset.get_duration(), self.asset.get_supported_formats())
        
        self.timeline.commit()



        sink = Gst.ElementFactory.make("xvimagesink", "sink")

        self.pipeline = GES.Pipeline()
        self.pipeline.set_mode(GES.PipelineFlags.FULL_PREVIEW)
        self.pipeline.set_timeline(self.timeline)
        self.pipeline.set_state(Gst.State.PLAYING)
        self.pipeline.preview_set_video_sink(sink)


        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_message_cb)

        window = Gtk.Window()

        window.connect("delete-event", self.window_closed)
        window.set_title("Averoid Adventures")

        drawing_area = Gtk.DrawingArea()
        drawing_area.set_double_buffered (True)
        drawing_area.set_name("drawing_area")

        drawing_area.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(255, 255, 255, 255))
        window.override_background_color(Gtk.StateType.NORMAL, Gdk.RGBA(255, 255, 0, 255))

        window.add (drawing_area)





        accel = Gtk.AccelGroup()
        accel.connect(Gdk.keyval_from_name('Q'), 0, 0, self.on_q_pressed)
        accel.connect(Gdk.keyval_from_name('A'), 0, 0, self.on_a_pressed)
        window.add_accel_group(accel)

        window.show_all()
        window.realize()
        #window.fullscreen()

        xid = drawing_area.get_window().get_xid()
        sink.set_window_handle (xid)

        self.pipeline.set_state(Gst.State.PLAYING)
        
        mainLoop = GLib.MainLoop.new(None, False)
        GLib.MainLoop().run()

    def on_a_pressed(self, *args):
        print("ADDING")
        self.layer.add_asset(self.asset2, Gst.CLOCK_TIME_NONE, 0, self.asset2.get_duration(), self.asset2.get_supported_formats())
        self.timeline.commit()

    def on_q_pressed(self, *args):
        quit(self.pipeline)

    def quit(self):
        self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()
        exit(0)

    def window_closed(self, widget, event):
        self.quit()

    def bus_message_cb(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            print("EOS")
            self.quit()
  
Player()
