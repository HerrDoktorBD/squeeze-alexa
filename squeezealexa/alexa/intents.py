# -*- coding: utf-8 -*-
#
#   Copyright 2017 Nick Boultbee
#   This file is part of squeeze-alexa.
#
#   squeeze-alexa is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   See LICENSE for full license


class Audio(object):
    (RESUME, PAUSE,
     NEXT, PREVIOUS,
     LOOP_ON, LOOP_OFF,
     SHUFFLE_ON, SHUFFLE_OFF) = ("AMAZON.%sIntent" % s
                                 for s in ["Resume", "Pause",
                                           "Next", "Previous",
                                           "LoopOn", "LoopOff",
                                           "ShuffleOn", "ShuffleOff"])


class Play(object):
    RANDOM_MIX, PLAYLIST = ("Play%sIntent" % s
                            for s in ["RandomMix", "Playlist"])


class CustomAudio(object):
    LOOP_ON, LOOP_OFF, SHUFFLE_ON, SHUFFLE_OFF = ("%sIntent" % s for s in
                                                  ["LoopOn", "LoopOff",
                                                   "ShuffleOn", "ShuffleOff"])


class Power(object):
    (ALL_OFF, ALL_ON,
     PLAYER_OFF, PLAYER_ON) = ("%sIntent" % s
                               for s in ["AllOff", "AllOn",
                                         "TurnOffPlayer", "TurnOnPlayer"])


class General(object):
    HELP, CANCEL, STOP = ("AMAZON.%sIntent" % s
                          for s in ["Help", "Cancel", "Stop"])


class Custom(object):
    HELP, CANCEL, STOP = ("%sIntent" % s
                          for s in ["Help", "Cancel", "Stop"])
    INC_VOL, DEC_VOL = ("%sVolumeIntent" % s for s in ["Increase", "Decrease"])
    CURRENT, SELECT_PLAYER = ("%sIntent" % s
                              for s in ["NowPlaying", "SelectPlayer"])


class ServerStatus(object):
    (STATUS,) = ("%sIntent" % s
                 for s in ["ServerStatus"])
    (INFO,) = ("%sIntent" % s
               for s in ["Scanning"])
    (RESCAN,) = ("%sIntent" % s
                 for s in ["Rescan"])


class Info(object):
    (ALBUM, ARTIST, GENRE, SONG) = ("%sInfoIntent" % s
                                    for s in ["Album", "Artist",
                                              "Genre", "Song"])


class AlbumInfoByArtist(object):
    (INFO,) = ("%sIntent" % s
               for s in ["AlbumInfoByArtist"])


class AlbumByArtist(object):
    (RANDOM, FIRST, LATEST) = ("Play%sAlbumByArtistIntent" % s
                               for s in ["Random", "First", "Latest"])
    (PLAY,) = ("%sIntent" % s
               for s in ["PlayAlbumByArtist"])


class PlayAlbum(object):
    (PLAY,) = ("%sIntent" % s
               for s in ["PlayAlbum"])
