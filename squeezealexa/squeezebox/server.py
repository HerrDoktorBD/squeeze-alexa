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

from __future__ import print_function

import re
import time

from squeezealexa.utils import with_example, PY2, print_d
if PY2:
    import urllib
else:
    import urllib.request as urllib


class SqueezeboxException(Exception):
    """Errors communicating with the Squeezebox"""


class SqueezeboxPlayerSettings(dict):
    """Encapsulates player settings"""

    def __init__(self, player_id=None):
        super(SqueezeboxPlayerSettings, self).__init__()
        if player_id:
            self['playerid'] = player_id

    @property
    def id(self):
        return self['playerid']

    def __getattr__(self, key):
        return self.get(key, None)

    def __str__(self):
        try:
            return "{name} [{short}]".format(short=self['playerid'][-5:],
                                             **self)
        except KeyError:
            return "Unidentified Squeezebox player: %r" % self


class Server(object):
    """Encapsulates access to a Squeezebox player via a Squeezecenter server"""

    _TIMEOUT = 10
    _MAX_FAILURES = 3
    _MAX_CACHE_SECS = 60  # 600

    def __init__(self, ssl_wrap, user=None, password=None,
                 cur_player_id=None, debug=False):

        self.ssl_wrap = ssl_wrap
        self._debug = debug
        self.user = user
        self.password = password
        if user and password:
            self.log_in()
            print_d("Authenticated with %s!" % self)
        self.players = {}
        self.refresh_status()

        keys = list(self.players)  # returns keys in a list
        self.cur_player_id = cur_player_id or keys[0]
        print_d("Default player is now %s " % self.cur_player_id[-5:])

        self.__genres = []
        self.__playlists = []
        self._created_time = time.time()

    @property
    def player_names(self):
        return {p.get("name", "unknown") for p in self.players.values()}

    def is_stale(self):
        return (time.time() - self._created_time) > self._MAX_CACHE_SECS

    def log_in(self):
        result = self.__a_request("login %s %s" % (self.user, self.password))
        if result != "%s ******" % self.user:
            raise SqueezeboxException(
                "Couldn't log in to squeezebox: response was '%s'" % result)

    def __a_request(self, line, raw=False, wait=True):
        reply = self._request([line], raw=raw, wait=wait)
        if reply and len(reply):
            return reply[0]
        if self.user and self.password:
            print_d("Command failed. Trying to re-log in.")
            self.log_in()
            reply = self._request([line], raw=raw, wait=wait)
            if reply and len(reply):
                return reply[0]
        raise SqueezeboxException("Unprocessable command or login error")

    @staticmethod
    def _unquote(response):
        return ' '.join(urllib.unquote(s) for s in response.split(' '))

    def _request(self, lines, raw=False, wait=True):
        """
        Send multiple pipelined requests to the server, if connected,
        and return their responses,
        assuming order is maintained (which seems safe).

        :type lines list[str]
        :rtype list[str]
        """
        if not self.ssl_wrap.is_connected:
            return []
        if not (lines and len(lines)):
            return []
        lines = [l.rstrip() for l in lines]

        first_word = lines[0].split()[0]
        if not (self.ssl_wrap.is_connected or first_word == 'login'):
            print_d("Can't do '%s' - not connected" % first_word, self)
            return

        if self._debug:
            print_d("sent <<<< " + "\n..<< ".join(lines))

        request = "\n".join(lines) + "\n"
        raw_response = self.ssl_wrap.communicate(request, wait=wait)
        if not wait:
            return []
        if not raw_response:
            raise SqueezeboxException(
                "No further response from %s. Login problem?" % self)

        raw_response = raw_response.rstrip("\n")
        response = raw_response if raw else self._unquote(raw_response)

        if self._debug:
            print_d("rec >>>> " + "\n..>> ".join(response.splitlines()))

        def start_point(text):

            if first_word == 'login':
                return 6

            delta = -1 if text.endswith('?') else 1

            start = len(self._unquote(text) if raw else text) + delta
            return start

        resp_lines = response.splitlines()
        if len(lines) != len(resp_lines):
            raise ValueError("Response problem: %s != %s"
                             % (lines, resp_lines))

        output = [resp_line[start_point(line):]
                  for line, resp_line in zip(lines, resp_lines)]
        return output

    @staticmethod
    def __pairs_from(response):
        """Split and unescape a response"""

        # print_d("__pairs_from, response: %s" % response)

        def demunge(string):
            s = urllib.unquote(string)
            return tuple(s.split(':', 1))

        # output = filter(lambda t: len(t) == 2,
        #                 map(demunge, response.split(' ')))
        demunged = map(demunge, response.split(' '))
        output = [d for d in demunged if len(d) == 2]
        # print_d("output: %s" % output)
        return output

    @staticmethod
    def __pairs_from2(response):
        """
        Split and unescape a response

        input:
            :10382150 artist:Olafur Arnalds
            id:10388296 artist:Ólafur Arnalds
            id:10380560 artist:Ólafur Arnalds And Nils Frahm
            id:10380558 artist:Ólafur Arnalds & Nils Frahm
            count:4

        output:
            {'10388296': '\xc3\x93lafur Arnalds',
             '10380558': '\xc3\x93lafur Arnalds & Nils Frahm',
             '10380560': '\xc3\x93lafur Arnalds And Nils Frahm',
              None: 'Olafur Arnalds'}

        input:
            albums 0 255 artist_id%3A10378560 tags%3Aly
            id%3A7129733 album%3ABlackfield year%3A2005
            id%3A7129734 album%3ABlackfield%20II year%3A2007
            id%3A7129736 album%3ABlackfield%20IV year%3A2013
            id%3A7129737 album%3ABlackfield%20V year%3A2017
            id%3A7129735 album%3AWelcome%20to%20My%20DNA year%3A2011
            count%3A5

        output:
            [('id', '7129733'), ('album', 'Blackfield'), ('year', '2005'),
             ('id', '7129734'), ('album', 'Blackfield II'), ('year', '2007'),
             ('id', '7129736'), ('album', 'Blackfield IV'), ('year', '2013'),
             ('id', '7129737'), ('album', 'Blackfield V'), ('year', '2017'),
             ('id', '7129735'), ('album', 'Welcome to My DNA'), ('year',
                                                                      '2011'),
             ('count', '5')]

        input:
            artists 0 255 search:blackfield
            id:10378560 artist:Blackfield
            count:1

        output:
           [('id', '10378560'), ('artist', 'Blackfield'),
            ('count', '1')]
        """
        # print_d("__pairs_from2, response: %s" % response)

        def demunge(string):
            s = urllib.unquote(string)

            return tuple(s.split(':', 1))

        words = "|".join(["id", "album", "artist", "count", "year"])
        pattern = r"(^|\W)({kwds})(?=\W|$)".format(kwds=words)
        d = re.sub(pattern, r"_\2", response)[1:]

        # print_d("__pairs_from2, d: %s" % d)

        output = filter(lambda t: len(t) == 2,
                        map(demunge, d.split('_')))
        # print_d("__pairs_from2, output: %s" % output)
        return output

    def refresh_status(self):
        """Updates the list of the Squeezebox players available and other
         server metadata."""

        print_d("Refreshing server and player statuses...")
        pairs = self.__pairs_from(
            self.__a_request("serverstatus 0 99", raw=True))
        self.players = {}
        player_id = None
        for key, val in pairs:
            if key == "playerid":
                player_id = val
                self.players[player_id] = SqueezeboxPlayerSettings(player_id)
            elif player_id:
                # Don't worry, playerid is *always* the first entry...
                self.players[player_id][key] = val
        if self._debug:
            print_d("Found %d player(s): %s" %
                    (len(self.players), self.players))
        try:
            assert (int(dict(pairs)['player count']) == len(self.players))
        except Exception as e:
            raise SqueezeboxException("Player count broken (%r). Data: %s"
                                      % (e, pairs))

    def player_request(self, line, player_id=None, raw=False, wait=True):
        """Makes a single request to a particular player (or the current)"""

        try:
            player_id = (player_id or
                         self.cur_player_id or
                         list(self.players.values())[0]["playerid"])

            return self._request(["%s %s" % (player_id, line)],
                                 raw=raw, wait=wait)[0]
        except IndexError:
            return None

    def play(self, player_id=None):
        """Plays the current song"""

        self.player_request("play", player_id=player_id)

    def play_random_mix(self, genre_list, player_id=None):
        """Uses the (standard) Random Mix plugin"""

        gs = genre_list or []
        commands = ["randomplaygenreselectall 0"]
        commands += ["randomplaychoosegenre %s 1" % urllib.quote(g)
                     for g in gs]
        commands += ["playlist clear", "randomplay tracks"]
        pid = player_id or self.cur_player_id
        return self._request(["%s %s" % (pid, com) for com in commands])

    def play_genres(self, genre_list, player_id=None):
        gs = genre_list or []
        commands = (["playlist clear", "playlist shuffle 1"] +
                    ["playlist addalbum %s * *" % urllib.quote(genre)
                     for genre in gs if genre] +
                    ["play 2"])
        pid = player_id or self.cur_player_id
        return self._request(["%s %s" % (pid, com) for com in commands])

    def is_stopped(self, player_id=None):
        """Returns whether the player is in any sort of non-playing mode"""

        response = self.player_request("mode ?", player_id=player_id)
        return "play" != response

    def get_current(self, player_id=None):
        return self.get_status(player_id)

    def get_track_details(self, player_id=None):
        # keys = ["genre", "artist", "current_title"]
        keys = ["current_title", "album", "artist"]
        pid = player_id or self.cur_player_id

        response = self._request(["%s %s ?" % (pid, s)
                                  for s in keys])
        # print_d(response)
        # response: ['Lit', 'Kiasmos (HDTracks 24-44.1)', 'Kiasmos']
        return dict(zip(keys, response))

    @property
    def genres(self):
        if not self.__genres:
            response = self.__a_request("genres 0 255", raw=True)
            print_d(response)
            self.__genres = [v for k, v in self.__pairs_from(response)
                             if k == 'genre']
            print_d(with_example("Loaded %d LMS genres", self.__genres))
        return self.__genres

    @property
    def playlists(self):
        if not self.__playlists:
            resp = self.__a_request("playlists 0 255", raw=True)
            self.__playlists = [v for k, v in self.__pairs_from(resp)
                                if k == 'playlist']
            print_d(with_example("Loaded %d LMS playlists", self.__playlists))
        return self.__playlists

    def get_status(self, player_id=None):
        """ask the server for a status"""
        response = self.player_request("status - 2", player_id=player_id,
                                       raw=True)
        if "rescan" in response:
            return "Scanning"
        return dict(self.__pairs_from(response))

    def next(self, player_id=None):
        self.player_request("playlist jump +1", player_id=player_id)

    def previous(self, player_id=None):
        self.player_request("playlist jump -1", player_id=player_id)

    def playlist_play(self, path, player_id=None):
        """Play song / playlist immediately"""
        self.player_request("playlist play %s" % (urllib.quote(path)),
                            player_id=player_id)

    def playlist_clear(self):
        self.player_request("playlist clear", wait=False)

    def playlist_resume(self, name, resume, wipe=False):
        cmd = ("playlist resume %s noplay:%d wipePlaylist:%d"
               % (urllib.quote(name), int(not resume), int(wipe)))
        self.player_request(cmd, wait=False)

    def change_song(self, path):
        """Queue up a song"""
        self.player_request("playlist clear")
        self.player_request("playlist insert %s" % (urllib.quote(path)))

    def change_volume(self, delta, player_id=None):
        if not delta:
            return
        cmd = "mixer volume %s%.1f" % ('+' if delta > 0 else '', float(delta))
        self.player_request(cmd, player_id=player_id)

    def get_milliseconds(self):
        secs = self.player_request("time ?") or 0
        return float(secs) * 1000.0

    def pause(self, player_id=None):
        self.player_request("pause 1", player_id=player_id)

    def resume(self, player_id=None, fade_in_secs=1):
        self.player_request("pause 0 %d" % fade_in_secs, player_id=player_id)

    def stop(self, player_id=None):
        self.player_request("stop", player_id=player_id)

    def set_shuffle(self, on=True, player_id=None):
        self.player_request("playlist shuffle %d" % int(bool(on) * 2),
                            player_id=player_id)

    def set_repeat(self, on=True, player_id=None):
        self.player_request("playlist repeat %d" % int(bool(on)),
                            player_id=player_id)

    def set_power(self, on=True, player_id=None):
        self.player_request("power %d" % int(bool(on)), player_id=player_id)

    def set_all_power(self, on=True):
        value = int(bool(on))
        self._request(["%s power %d" % (p, value)
                       for p in self.players.keys()])

    def __str__(self):
        return "Squeezebox server at %s" % self.ssl_wrap

    def get_artists_with_search_term(self, search_term):
        """
        ask the server for artists matching search_term
        e.g. artists 0 255 search:blackfield
        """

        # if isinstance(search_term, unicode):
        #    print_d("unicode search_term")
        #    search_term = str(search_term)

        # print_d("search_term: %s" % search_term)
        # q_search_term = urllib.quote(search_term)
        # print_d("quoted search_term: %s" % q_search_term)

        cmd = ("artists 0 255 search:%s" % search_term)
        response = self.player_request(cmd)

        if "rescan" in response:
            return "Scanning"

        return self.__pairs_from2(response)

    def get_albums_with_search_term(self, search_term):
        """
        ask the server for albums matching search_term
        e.g. albums 0 255 search:last samurai
        """

        cmd = ("albums 0 255 search:%s tags:lay" % search_term)
        response = self.player_request(cmd)
        if "rescan" in response:
            return "Scanning"

        return self.__pairs_from2(response)

    def get_albums_with_artist_id(self, artist_id):
        """
        ask the server for albums belonging to artist_id
        e.g. albums 0 255 artist_id:10378560 tags:ly
        """

        cmd = ("albums 0 255 artist_id:%s tags:ly" % artist_id)
        response = self.player_request(cmd)
        if "rescan" in response:
            return "Scanning"

        return self.__pairs_from2(response)

    def play_album_with_id(self, album_id, player_id=None):
        """
        ask the server to play the album identified by album_id
        """
        commands = (["playlist shuffle 0",
                     "playlistcontrol cmd:load album_id:%s" % album_id])
        pid = player_id or self.cur_player_id

        return self._request(["%s %s" % (pid, com) for com in commands])

    def is_scanning(self):
        """
        ask the server if it's currently scanning the library
        """
        response = self.player_request("rescan ?")
        if "rescan" in response:
            return "Scanning"

        return None

    def rescan(self):
        """
        ask the server to rescan the library
        """
        response = self.player_request("rescan ?")
        if "rescan" in response:
            return "Scanning"

        return self.__a_request("rescan") or 0

    def get_info_total(self, name):
        """ask the server for the total number of items of name"""

        return self.__a_request("info total %s ?" % name) or 0
