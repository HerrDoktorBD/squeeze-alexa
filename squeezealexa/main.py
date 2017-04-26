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

import collections
import random
import time

from fuzzywuzzy import process, fuzz
from squeezealexa.alexa.handlers import AlexaHandler, IntentHandler
from squeezealexa.alexa.intents import *
from squeezealexa.alexa.response import audio_response, speech_response, \
    _build_response
from squeezealexa.alexa.utterances import Utterances
from squeezealexa.settings import *
from squeezealexa.squeezebox.server import Server, print_d
from squeezealexa.ssl_wrap import SslSocketWrapper
from squeezealexa.utils import english_join, sanitise_text, strip_accents, recover_key, remove_stop_words


class MinConfidences(object):
    PLAYER = 85
    GENRE = 85
    MULTI_GENRE = 90
    PLAYLIST = 60


MAX_GUESSES_PER_SLOT = 2
AUDIO_TIMEOUT_SECS = 60 * 15

handler = IntentHandler()


class SqueezeAlexa(AlexaHandler):
    _audio_touched = 0
    _server = None
    """The server instance
    :type Server"""

    def __init__(self, server=None, app_id=None):
        super(SqueezeAlexa, self).__init__(app_id)
        if server:
            print_d("Overriding class server for testing")
            SqueezeAlexa._server = server

    def handle(self, event, context):
        request = event['request']
        req_type = request['type']
        if req_type.startswith('AudioPlayer'):
            print_d("Ignoring %s callback %s"
                    % (request['type'], request['requestId']))
            self.touch_audio()
            return _build_response({})
        return super(SqueezeAlexa, self).handle(event, context)

    def on_session_started(self, request, session):
        print_d("Starting new session {0} for request {1}"
                .format(session['sessionId'], request['requestId']))

    def on_launch(self, launch_request, session):

        print_d("Entering interactive mode for sessionId=%s"
                % session['sessionId'])
        speech_output = "Squeezebox is online. Please try some commands."
        reprompt_text = "Try resume, pause, next, previous " \
                        "or ask Squeezebox to turn it up or down"
        return speech_response("Welcome", speech_output, reprompt_text,
                               end=False)

    @classmethod
    def get_server(cls):
        """
        :return a Server instance
        :rtype Server
        """
        if not cls._server or cls._server.is_stale():
            sslw = SslSocketWrapper(hostname=SERVER_HOSTNAME,
                                    port=SERVER_SSL_PORT,
                                    ca_file=CA_FILE_PATH,
                                    cert_file=CERT_FILE_PATH,
                                    verify_hostname=VERIFY_SERVER_HOSTNAME)
            cls._server = Server(sslw,
                                 user=SERVER_USERNAME,
                                 password=SERVER_PASSWORD,
                                 cur_player_id=DEFAULT_PLAYER,
                                 debug=DEBUG_LMS)
            print_d("Created %r" % cls._server)
        else:
            print_d("Reusing cached %r" % cls._server)
        return cls._server

    def on_intent(self, intent_request, session):
        intent = intent_request['intent']
        intent_name = intent['name']
        pid = self.player_id_from(intent)
        print_d("Received %s: %s (for player %s)" % (intent_name, intent, pid))

        intent_handler = handler.for_name(intent_name)
        if intent_handler:
            return intent_handler(self, intent, session, pid=pid)

        return self.smart_response(
            speech="Sorry, I don't know how to process \"%s\"" % intent_name,
            text="Unknown intent: '%s'" % intent_name)

    def on_early_reponse(self, name):
        return self.smart_response(text=name, speech=name)

    @handler.handle(Audio.RESUME)
    def on_resume(self, intent, session, pid=None):
        self.get_server().resume(player_id=pid)
        return audio_response()

    @handler.handle(Audio.PAUSE)
    def on_pause(self, intent, session, pid=None):
        self.get_server().pause(player_id=pid)
        return audio_response()

    @handler.handle(Audio.PREVIOUS)
    def on_previous(self, intent, session, pid=None):
        self.get_server().previous(player_id=pid)
        return self.smart_response(speech="Rewind!")

    @handler.handle(Audio.NEXT)
    def on_next(self, intent, session, pid=None):
        self.get_server().next(player_id=pid)
        return self.smart_response(speech="OK")

    @handler.handle(Custom.CURRENT)
    def on_current(self, intent, session, pid=None):
        details = self.get_server().get_track_details()
        title = details['current_title']
        album = details['album']
        artist = details['artist']
        if title:
            desc = "Currently playing: \"%s\"" % title
            if album:
                desc += (", from %s" % album)
            if artist:
                desc += (", by %s" % artist)
            heading = "Now playing: \"%s\"" % title
        else:
            desc = "Nothing is playing right now."
            heading = None
        return self.smart_response(text=heading, speech=desc)

    @handler.handle(Custom.INC_VOL)
    def on_inc_vol(self, intent, session, pid=None):
        self.get_server().change_volume(+12.5, player_id=pid)
        return self.smart_response(text="Increase Volume",
                                   speech="Pumped it up.")

    @handler.handle(Custom.DEC_VOL)
    def on_dec_vol(self, intent, session, pid=None):
        self.get_server().change_volume(-12.5, player_id=pid)
        return self.smart_response(text="Decrease Volume",
                                   speech="OK, quieter now.")

    @handler.handle(Custom.SELECT_PLAYER)
    def on_select_player(self, intent, session, pid=None):
        srv = self.get_server()
        srv.refresh_status()

        # Do it again, yes, but not defaulting this time.
        pid = self.player_id_from(intent, defaulting=False)
        if pid:
            player = srv.players[pid]
            srv.cur_player_id = player.id
            return speech_response(
                "Selected player %s" % player,
                "Selected %s" % player.name,
                store={"player_id": pid})
        else:
            speech = ("I only found these players: %s. "
                      "Could you try again?"
                      % english_join(srv.player_names))
            reprompt = ("You can select a player by saying "
                        "\"%s\" and then the player name."
                        % Utterances.SELECT_PLAYER)
            try:
                title = ("No player called \"%s\""
                         % intent['slots']['Player']['value'])
            except KeyError:
                title = "Didn't recognise a player name"
            return speech_response(title, speech, reprompt_text=reprompt,
                                   end=False)

    @handler.handle(Audio.SHUFFLE_ON)
    @handler.handle(CustomAudio.SHUFFLE_ON)
    def on_shuffle_on(self, intent, session, pid=None):
        self.get_server().set_shuffle(True, player_id=pid)
        return self.smart_response(text="Shuffle on",
                                   speech="Shuffle is now on")

    @handler.handle(Audio.SHUFFLE_OFF)
    @handler.handle(CustomAudio.SHUFFLE_OFF)
    def on_shuffle_off(self, intent, session, pid=None):
        self.get_server().set_shuffle(False, player_id=pid)
        return self.smart_response(text="Shuffle off",
                                   speech="Shuffle is now off")

    @handler.handle(Audio.LOOP_ON)
    @handler.handle(CustomAudio.LOOP_ON)
    def on_loop_on(self, intent, session, pid=None):
        self.get_server().set_repeat(True, player_id=pid)
        return self.smart_response(text="Repeat on",
                                   speech="Repeat is now on")

    @handler.handle(Audio.LOOP_OFF)
    @handler.handle(CustomAudio.LOOP_OFF)
    def on_loop_off(self, intent, session, pid=None):
        self.get_server().set_repeat(False, player_id=pid)
        return self.smart_response(text="Repeat Off",
                                   speech="Repeat is now off")

    @handler.handle(Power.PLAYER_OFF)
    def on_player_off(self, intent, session, pid=None):
        if not pid:
            return self.on_all_off(intent, session)
        server = self.get_server()
        server.set_power(on=False, player_id=pid)
        player = server.players[pid]
        return self.smart_response(title="Switched %s off" % player.name,
                                   text="Switched %s off" % player,
                                   speech="%s is now off" % player.name)

    @handler.handle(Power.PLAYER_ON)
    def on_player_on(self, intent, session, pid=None):
        if not pid:
            return self.on_all_on(intent, session)
        server = self.get_server()
        server.set_power(on=True, player_id=pid)
        player = server.players[pid]
        speech = "%s is now on" % player.name
        if server.cur_player_id != pid:
            speech += ", and is selected."
        server.cur_player_id = pid
        return self.smart_response(title="Switched %s on" % player.name,
                                   text="Switched %s on" % player,
                                   speech=speech)

    @handler.handle(Power.ALL_OFF)
    def on_all_off(self, intent, session, pid=None):
        self.get_server().set_all_power(on=False)
        return self.smart_response(text="Players all off", speech="Silence")

    @handler.handle(Power.ALL_ON)
    def on_all_on(self, intent, session, pid=None):
        self.get_server().set_all_power(on=True)
        return self.smart_response(text="All On", speech="Ready")

    @handler.handle(Play.PLAYLIST)
    def on_play_playlist(self, intent, session, pid=None):
        server = self.get_server()
        try:
            slot = intent['slots']['Playlist']['value']
            print_d("Extracted playlist slot: %s" % slot)
        except KeyError:
            print_d("Couldn't process playlist from: %s" % intent)
            if not server.playlists:
                return speech_response(text="There are no playlists")
            return speech_response(
                text="Didn't hear a playlist there. "
                     "You could try the \"%s\" playlist?"
                     % (random.choice(server.playlists)))
        else:
            if not server.playlists:
                return speech_response(text="No Squeezebox playlists found")
            result = process.extractOne(slot, server.playlists)
            print_d("%s was the best guess for '%s' from %s"
                    % (result, slot, server.playlists))
            if result and int(result[1]) >= MinConfidences.PLAYLIST:
                pl = result[0]
                server.playlist_play(pl, player_id=pid)
                name = sanitise_text(pl)
                return self.smart_response(
                    speech="Playing \"%s\" playlist" % name,
                    text="Playing \"%s\" playlist" % name)
            return speech_response(
                text="Couldn't find a playlist matching \"%s\"."
                     "How about the \"%s\" playlist?"
                     % (slot, random.choice(server.playlists)))

    @handler.handle(Play.RANDOM_MIX)
    def on_play_random_mix(self, intent, session, pid=None):
        server = self.get_server()
        try:
            slots = [v.get('value') for k, v in intent['slots'].items()
                     if k.endswith('Genre')]
            print_d("Extracted genre slots: %s" % slots)
        except KeyError:
            print_d("Couldn't process genres from: %s" % intent)
            pass
        else:
            lms_genres = self._genres_from_slots(slots, server.genres)
            if lms_genres:
                server.play_genres(lms_genres)
                gs = english_join(sanitise_text(g) for g in lms_genres)
                return self.smart_response(text="Playing mix of %s" % gs,
                                           speech="Playing mix of %s" % gs)
            else:
                genres_text = english_join(slots, "or")
                return self.smart_response(
                    text="Don't understand requested genres %s" % genres_text,
                    speech="Can't find genres: %s" % genres_text)
        raise ValueError("Don't understand intent '%s'" % intent)

    @staticmethod
    def _genres_from_slots(slots, genres):
        def genres_from(g):
            if not g:
                return set()
            res = process.extract(g, genres)[:MAX_GUESSES_PER_SLOT]
            print_d("Raw genre results: %s" % res)
            return {g for g, c in res
                    if g and int(c) >= MinConfidences.MULTI_GENRE}

        # Grr where's my foldl
        results = set()
        for slot in slots:
            results |= genres_from(slot)
        return results

    @handler.handle(General.HELP)
    def on_help(self, intent, session, pid=None):
        return self.on_launch(intent, session)

    @handler.handle(General.CANCEL)
    @handler.handle(General.STOP)
    def on_stop(self, intent, session, pid=None):
        return self.on_session_ended(intent, session)

    def player_id_from(self, intent, defaulting=True):

        server = self.get_server()

        try:
            player_name = intent['slots']['Player']['value']
        except KeyError:
            pass
        else:
            by_name = {s.name: s for s in server.players.values()}
            result = process.extractOne(player_name, by_name.keys())

            print_d("{0} was the best guess for '{1}' from {2}"
                    .format(result, player_name, by_name.keys()))

            if result and int(result[1]) >=  MinConfidences.PLAYER:
                return by_name.get(result[0]).id

        return server.cur_player_id if defaulting else None

    def on_session_ended(self, session_ended_request, session):
        print_d("on_session_ended requestId=%s, sessionId=%s" %
                (session_ended_request['requestId'], session['sessionId']))
        speech_output = "Hasta la vista, baby."
        return speech_response("Session Ended", speech_output, end=True)

    @classmethod
    def touch_audio(cls, ts=None):
        cls._audio_touched = ts or time.time()

    @property
    def audio_enabled(self):
        return (time.time() - self._audio_touched) < AUDIO_TIMEOUT_SECS

    def smart_response(self, title=None, text=None, speech=None):
        if self.audio_enabled:
            return speech_response(title=title or text, text=speech)
        return audio_response(speech=speech, text=text, title=title)

    def on_info(self, name):
        """
        call the server's get_info_total function
        with one of {album, artist, genre, song}
        to get the total number of that item
        """
        details = self.get_server().get_info_total(name)
        if details:
            desc = "There are %s %s" % (details, name)
            heading = "Number of %s" % name
        else:
            desc = "There are no %s." % name
            heading = None

        return self.smart_response(text=heading, speech=desc)

    @handler.handle(Info.ALBUM)
    def on_album(self, intent, session, pid=None):
        return self.on_info("albums")

    @handler.handle(Info.ARTIST)
    def on_artist(self, intent, session, pid=None):
        return self.on_info("artists")

    @handler.handle(Info.GENRE)
    def on_genre(self, intent, session, pid=None):
        return self.on_info("genres")

    @handler.handle(Info.SONG)
    def on_song(self, intent, session, pid=None):
        return self.on_info("songs")

    @handler.handle(ServerStatus.INFO)
    def on_scanning(self, intent, session, pid=None):
        heading = "Scanning Status"
        response = self.get_server().is_scanning()
        if response is "Scanning":
            desc = "The server is currently scanning."
        else:
            desc = "Currently, the server is not scanning."
        return self.smart_response(text=heading, speech=desc)

    @handler.handle(ServerStatus.RESCAN)
    def on_rescan(self, intent, session, pid=None):
        heading = "Scanning Status"
        response = self.get_server().rescan()
        if response is "Scanning":
            desc = "The server is currently scanning."
        else:
            desc = "Ok, starting to scan."
        return self.smart_response(text=heading, speech=desc)

    @handler.handle(ServerStatus.STATUS)
    def on_status(self, intent, session, pid=None):

        response = self.get_server().get_status()
        if response is "Scanning":
            response = "The server is currently scanning."

        if 'player_name' not in dict(response):
            return "probably testing"

        print_d("status response = {}".format(response))

        player_name = dict(response)['player_name']
        # print_d("player_name = {}".format(player_name))

        player_connected = "connected" if dict(response)['player_connected'] is "1" else "disconnected"
        # print_d("player_connected = {}".format(player_connected))

        return audio_response(title=player_name,
                              text=player_connected,
                              url=OPERATIONAL_AUDIO_FILE_URL)

    @staticmethod
    def get_items_sorted_by_year(items_dict):
        """
        given a dictionary,
        return another dictionary sorted by year (first key in values)
        """

        if len(items_dict) == 0:
            return None

        # print_d("items_dict: {}".format(items_dict))
        # {album_id: (album_year, album_name, artist_name), etc.}
        # {'7136042': ('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti'),
        #  '7129185': ('2014', 'Going Home (EP)', '\xc3\x81sgeir'),
        #  '7129184': ('2013', 'In the Silence', '\xc3\x81sgeir')}

        # make the values a list
        values_list = items_dict.values()

        # print_d("item_list: {}".format(item_list))
        # [(album_year, album_name, artist_name), etc.]
        # [('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti'),
        #  ('2014', 'Going Home (EP)', '\xc3\x81sgeir'),
        #  ('2013', 'In the Silence', '\xc3\x81sgeir')]

        # sort list by album_year
        values_list.sort(key=lambda x: x[0])

        # print_d("values_list (sorted): {}".format(values_list))
        # [('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti'),
        #  ('2013', 'In the Silence', '\xc3\x81sgeir'),
        #  ('2014', 'Going Home (EP)', '\xc3\x81sgeir')]

        # and back to a dictionary (ordered by insertion order)
        sorted_items = collections.OrderedDict()
        for index, value in enumerate(values_list):
            key = recover_key(items_dict, value)
            sorted_items[key] = value

        # print_d("sorted_items: {}".format(sorted_items))
        # [('7136042', ('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti')),
        #  ('7129184', ('2013', 'In the Silence', '\xc3\x81sgeir')),
        #  ('7129185', ('2014', 'Going Home (EP)', '\xc3\x81sgeir'))])
        return sorted_items

    @staticmethod
    def get_artist_matches(server, wanted_artist):
        """
        given a wanted_artist,
        return top_matching_artists
        """

        # get artists from server matching wanted_artist
        artist_pairs = server.get_artists_with_search_term(wanted_artist)
        if artist_pairs is "Scanning":
            print_d("Sorry, currently scanning. Try again later.")
            return None

        # print_d(artist_pairs)

        # artist count
        # last item is always ('count', '5')
        artist_count = artist_pairs[len(artist_pairs) - 1][1]
        if int(artist_count) == 0:
            print_d("Sorry, no matching artists found.")
            return None

        # print_d("artist count: %s" % artist_count)

        query = strip_accents(wanted_artist).lower()
        # print_d("query: %s" % query)

        is_single_word = len(wanted_artist.split()) == 1
        # if is_single_word:
        #    print_d("wanted artist is a single word")

        artists = {}

        artist_id = None
        for key, val in artist_pairs:

            if key == "count":
                c = val  # no-op
            elif key == "id":
                artist_id = val
            elif key == "artist":

                q = strip_accents(val).lower()
                if is_single_word and query not in q:
                    # e.g. is 'Zimmer' in 'Alvin Risk & Hans Zimmer'?
                    # e.g. is 'Olafur' in 'Ólafur Arnalds'?
                    print_d("skipping q: {}".format(q))
                    continue

                artist_name = val

                # add artist to the dict
                artists[artist_id] = artist_name
                # print_d("artist added, id: {0}, artist: {1}"
                #        .format(artist_id, artist_name))

        artist_choices = artists.values()
        # print_d("artist_choices: %s" % artist_choices)

        ###########################
        # use FuzzyWuzzy to find best_artist_match
        # best_artist_match = process.extractOne(wanted_artist,
        #                                        artist_choices)[0]
        matches = process.extractBests(query,
                                       artist_choices,
                                       limit=255,
                                       score_cutoff=75)
        if len(matches) == 0:
            print_d("Sorry, no matches found.")
            return None

        # print_d("matches: {}".format(matches))
        ###########################

        matching_artists = {}
        for m in matches:
            artist_id = recover_key(artists, m[0])
            # print_d("artist_id: {0}, artist_name: {1}".format(artist_id, m[0]))
            # 10388130
            matching_artists[artist_id] = artists[artist_id]

        # print_d("matching_artists = {}".format(matching_artists))
        return matching_artists

    @staticmethod
    def get_albums_by_artist(self, server, wanted_artist):
        """
        given a wanted_artist,
        return sorted_albums
        """

        print_d("wanted_artist: {}".format(wanted_artist))
        matching_artists = self.get_artist_matches(server, wanted_artist)

        if matching_artists is None:
            return None
        if len(matching_artists) == 0:
            return None

        print_d("matching_artists: {}".format(matching_artists))

        # accumulate albums by all artists
        albums = {}
        for artist_id in matching_artists.keys():

            # print_d("artist_id: %s" % artist_id)

            album_pairs = server.get_albums_with_artist_id(artist_id)
            # print_d("album_pairs: {}".format(album_pairs))

            # album count for this artist
            # last item is always ('count', '5')
            this_artist_album_count = int(album_pairs[len(album_pairs) - 1][1])

            artist_name = matching_artists[artist_id]
            # print_d("album count: {0} for {1}"
            #        .format(this_artist_album_count, artist_name))

            if this_artist_album_count > 0:
                album_id = None
                album_name = None

                for key, val in album_pairs:

                    if key == "count":
                        c = val  # no-op
                    elif key == "id":
                        album_id = val
                    elif key == "album":
                        album_name = val
                    else:  # key == "year"
                        album_year = val

                        # add album to the dict
                        albums[album_id] = (album_year, album_name, artist_name)
                        # print_d("album added, id: {0}, name: {1}, artist: {2}"
                        #        .format(album_id, album_name, artist_name))

        # print_d("albums: {}".format(albums))

        # sort albums by year
        sorted_albums = self.get_items_sorted_by_year(albums)

        # print_d("sorted_albums: {}".format(sorted_albums))
        # [('7136042', ('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti')),
        #  ('7129184', ('2013', 'In the Silence', '\xc3\x81sgeir')),
        #  ('7129185', ('2014', 'Going Home (EP)', '\xc3\x81sgeir'))])

        return sorted_albums

    @staticmethod
    def get_matched_album(self, server, wanted_album):
        """
        given a wanted_album and a wanted_artist,
        return album_id, album_name, album_year
        """

        album_pairs = server.get_albums_with_search_term(wanted_album)
        if album_pairs is "Scanning":
            return None

        album_count = int(album_pairs[len(album_pairs) - 1][1])
        # print_d("album count: {0}".format(album_count))
        if album_count == 0:
            return None

        print_d("album_pairs: {}".format(album_pairs))

        album_year = None
        albums = {}
        simple_albums = {}
        album_choices = []

        for key, val in album_pairs:

            if key == "count":
                c = val  # no-op
            elif key == "id":
                album_id = val
            elif key == "album":
                album_name = val
            elif key == "year":
                album_year = val
            else:
                artist_name = val

                # add album to the dict
                albums[album_id] = album_name, album_year, artist_name

                simple_album_name = remove_stop_words(album_name)

                simple_albums[album_id] = simple_album_name
                album_choices.append(simple_album_name)

                # print_d("album added, id: {0} album: {1}"
                #         .format(album_id, album_name))

        # print_d("album_choices: %s" % album_choices)
        # print_d("albums: {}".format(albums))
        # print_d("simple_albums: {}".format(simple_albums))

        ###########################
        # use FuzzyWuzzy to find matches
        matches = process.extractBests(wanted_album,
                                       album_choices,
                                       score_cutoff=75)
        if len(matches) == 0:
            return None

        # print_d("matches: {}".format(matches))

        album_match = None

        # get the match with the best ratio
        sort_ratio = 0
        for m in matches:

            sr = fuzz.token_sort_ratio(wanted_album, m[0])
            # pr = fuzz.partial_ratio(wanted_album, m[0])
            # set_ratio = fuzz.token_set_ratio(wanted_album, m[0])

            # print_d("sort_ratio: {0}, partial_ratio: {1}, set_ratio: {2}"
            #        .format(sr, pr, set_ratio))

            if sr > sort_ratio:
                sort_ratio = sr
                album_match = m[0]

        ###########################
        # album_match = process.extractOne(wanted_album,
        #                                 album_choices,
        #                                 scorer=fuzz.token_set_ratio,
        #                                 score_cutoff=75)
        # print_d("(extractOne) album_match: {}".format(album_match))
        ###########################

        if album_match is None:
            return None

        # print_d("(extractBests) album_match: {}".format(album_match))
        # print_d("found an album!")

        # album_id = recover_key(simple_albums, album_match[0])
        album_id = recover_key(simple_albums, album_match)
        # print_d("album_id: {}".format(album_id))

        album_name = albums[album_id][0]
        # print_d("album_name: {}".format(album_name))

        album_year = albums[album_id][1]
        # print_d("album_year: {}".format(album_year))

        artist_name = albums[album_id][2]
        # print_d("artist_name: {}".format(artist_name))

        return album_id, album_year, album_name, artist_name

    @staticmethod
    def get_matched_album_by_artist(self, server, wanted_album, wanted_artist):
        """
        given a wanted_album and a wanted_artist,
        return album_id, album_name, album_year, artist_name
        """

        artist_matches = self.get_artist_matches(server, wanted_artist)

        if artist_matches is None:
            return None
        if len(artist_matches) == 0:
            return None

        # print_d("artist_matches: {}".format(artist_matches))

        query = wanted_album

        album_match = None

        album_id = None
        album_name = None
        album_year = None

        artist_id = None

        albums = {}

        # loop through albums from each artist by artist_id
        for artist_id in artist_matches.keys():

            # print_d("artist_id: %s" % artist_id)

            album_pairs = server.get_albums_with_artist_id(artist_id)
            # print_d("album_pairs count: {}".format(album_pairs))

            # album count for this artist
            # last item is always ('count', '5')
            this_artist_album_count = int(album_pairs[len(album_pairs) - 1][1])
            # print_d("album count: {0} for {1}"
            #         .format(this_artist_album_count, artists[k]))

            if this_artist_album_count > 0:

                albums.clear()
                album_id = None
                album_match = None

                for key, val in album_pairs:

                    if key == "count":
                        c = val  # no-op
                    elif key == "id":
                        album_id = val
                    elif key == "album":
                        album_name = val
                    else:  # key == "year"
                        album_year = val

                        # add album to the dict
                        albums[album_id] = (album_year, album_name)
                        # print_d("album added, id: {0} album: {1}"
                        #        .format(album_id, album_name))

                # we're done with this artist_id
                # inspect albums now

                album_choices = albums.values()
                # print_d("album_choices: {}".format(album_choices))

                ###########################
                # use FuzzyWuzzy to find matches
                matches = process.extractBests(wanted_album,
                                               album_choices,
                                               score_cutoff=75)
                if len(matches) == 0:
                    continue

                # print_d("matches: {}".format(matches))
                # [(u'for now i am winter', 95),
                #  (u'for now i am winter hdtracks 24 44 1', 95),
                #  (u'island songs hdtracks 24 96', 48),
                #  (u'another happy day', 42),
                #  (u'gimme shelter', 41)]

                # default is the first match
                # best_album_match = matches[0][0]  # u'for now i am winter'

                # get the match with the best ratio
                sort_ratio = 0
                for m in matches:

                    sr = fuzz.token_sort_ratio(query, m[0])
                    pr = fuzz.partial_ratio(query, m[0])
                    set_ratio = fuzz.token_set_ratio(query, m[0])

                    # print_d("sort_ratio: {0}, partial_ratio: {1}, set_ratio: {2}"
                    #        .format(sr, pr, set_ratio))

                    if sr > sort_ratio:
                        sort_ratio = sr
                        album_match = m[0]
                        ###########################

            # end of: if this_artist_album_count > 0

            if album_match is not None:
                # print_d("found an album!")

                album_id = recover_key(albums, album_match)
                album_year = album_match[0]
                album_name = album_match[1]

                break

        # end of: for k in top_matching_artists.keys()

        artist_name = artist_matches[artist_id]

        # print_d("album_id: {}".format(album_id))
        # print_d("album_year: {}".format(album_year))
        # print_d("album_name: {}".format(album_name))
        # print_d("artist_name: {}".format(artist_name))

        return album_id, album_year, album_name, artist_name

    def get_one_album_by_artist(self, server, intent, wanted_artist):
        """
        given an artist and depending on the intent
            # 1. random album
            # 2. first album
            # 3. latest album
        return album_id, album_name, album_year, artist_name
        """

        sorted_albums = self.get_albums_by_artist(self, server, wanted_artist)

        # [('7136042', ('2012', 'D\xc3\xbdr\xc3\xb0 \xc3\xad dau\xc3\xb0a\xc3\xbe\xc3\xb6gn', '\xc3\x81sgeir Trausti')),
        #  ('7129184', ('2013', 'In the Silence', '\xc3\x81sgeir')),
        #  ('7129185', ('2014', 'Going Home (EP)', '\xc3\x81sgeir'))])

        if sorted_albums is None:
            return None

        album_count = len(sorted_albums)
        # print_d(album_count)
        if album_count == 0:
            return None

        intent_name = intent[u'name']
        # print_d(intent_name)
        if intent_name == u'PlayFirstAlbumByArtistIntent':
            # first album
            i = 0
        elif intent_name == u'PlayLatestAlbumByArtistIntent':
            # latest album
            i = album_count - 1
        else:
            # random album
            from random import randrange
            i = randrange(0, album_count)
        # print_d(i)

        # python 2.x
        album = sorted_albums.items()[i]  # -> (key, value) tuple of ith element
        # print_d("album: {}".format(album))
        # album: ('7129185', ('2014', 'Going Home (EP)', '\xc3\x81sgeir'))

        album_id = album[0]
        # print_d("album_id: {}".format(album_id))

        album_year = album[1][0]
        # print_d("album_year: {}".format(album_year))

        album_name = album[1][1]
        # print_d("album_name: {}".format(album_name))

        artist_name = album[1][2]
        # print_d("artist_name: {}".format(artist_name))

        return album_id, album_year, album_name, artist_name
        # ('7129185', '2014', 'Going Home (EP)', '\xc3\x81sgeir')

    @staticmethod
    def get_item_from_slot(intent, name):
        """get an item from a slot"""

        item = intent['slots'][name]['value']
        if isinstance(item, unicode):
            # print_d("unicode %s" % name)
            item = str(item)
        # album = unicodedata.normalize('NFKD', al) \
        #     .encode('ascii', 'ignore')
        if item is not None:
            print_d("Extracted '{0}' from slot '{1}'".format(item, name))
        return item

    @handler.handle(AlbumInfoByArtist.INFO)
    def on_album_info_by_artist(self, intent, session, pid=None):
        """get the number of albums by an artist"""

        server = self.get_server()
        s_error = ""

        artist_slot = None

        try:
            s_error = "Couldn't process artist: %s." % artist_slot

            # get the artist name from the slot
            artist_slot = self.get_item_from_slot(intent, 'Artist')

            # manipulate utterance to conform to Last, First standard
            artist_slot = self.process_artist_slot(artist_slot)

        except KeyError:
            print_d(s_error)
            pass

        else:
            albums = self.get_albums_by_artist(self, server, artist_slot)

            # print_d("albums: {}".format(albums))
            # albums: OrderedDict(
            #  [('7136173', ('2010', 'Break Off', 'SBTRKT; SAMPHA')),
            #   ('7134031', ('2017', 'Process', 'Sampha'))])

            if albums is None:
                return self.smart_response(speech=s_error)

            # great, we found some albums
            album_count = len(albums)

            # get the artist name from a best match of all artists

            first_album = albums.items()[album_count - 1]
            artist_name = first_album[1][2]

            heading = "Number of albums by %s" % artist_name
            if album_count == 1:
                desc = "There is 1 album by {}" \
                    .format(artist_name)
            else:
                desc = "There are {0} albums by {1}" \
                    .format(album_count, artist_name)
            return self.smart_response(text=heading, speech=desc)

        s_bad = "artist: %s" % artist_slot

        return self.smart_response(
            text="Don't understand requested %s" % s_bad,
            speech="Can't find %s" % s_bad)

    @handler.handle(AlbumByArtist.RANDOM)
    @handler.handle(AlbumByArtist.FIRST)
    @handler.handle(AlbumByArtist.LATEST)
    @handler.handle(AlbumByArtist.PLAY)
    @handler.handle(PlayAlbum.PLAY)
    def on_play_album(self, intent, session, pid=None):
        """play an album"""

        server = self.get_server()

        s_error = ""
        intent_name = None
        album_slot = None
        artist_slot = None

        try:
            # slots = [v.get('value') for k, v in intent['slots'].items()]
            # print_d("Extracted slots: %s" % slots)

            # print_d("intent: '{}'".format(intent))

            intent_name = intent[u'name']
            if intent_name == u'PlayAlbumByArtistIntent' or intent_name == u'PlayAlbumIntent':

                s_error = "Couldn't process album: {0} and/or artist: {1}" \
                    .format(album_slot, artist_slot)

                # get the album name from the slot
                album_slot = self.get_item_from_slot(intent, 'Album')

                # remove stop words
                album_slot = remove_stop_words(album_slot)

                # manipulate utterance to change some inputs
                album_slot = self.process_album_slot(album_slot)

                # print_d("album_slot: '{}'".format(album_slot))
            else:
                s_error = "Couldn't process artist: %s." % artist_slot

            if intent_name != u'PlayAlbumIntent':
                # get the artist name from the slot
                artist_slot = self.get_item_from_slot(intent, 'Artist')

                # manipulate utterance to conform to Last, First standard
                artist_slot = self.process_artist_slot(artist_slot)

                # print_d("artist_slot: '{}'".format(artist_slot))

        except KeyError:
            print_d(s_error)
            pass

        else:
            # print_d("{}: '{}'".format(intent_name, album))

            if intent_name == u'PlayAlbumByArtistIntent':
                found_album = self.get_matched_album_by_artist(self, server, album_slot, artist_slot)

            elif intent_name == u'PlayAlbumIntent':
                found_album = self.get_matched_album(self, server, album_slot)

            else:
                found_album = self.get_one_album_by_artist(server, intent, artist_slot)

            if found_album is None:

                if intent_name == u'PlayAlbumIntent':
                    # no albums were found, try searching for artists

                    print_d("trying random album by artist")
                    artist_slot = album_slot

                    found_album = self.get_one_album_by_artist(server, intent, artist_slot)

                    if found_album is None:
                        # fine, nothing matches artist or album, bail out
                        return self.smart_response(speech=s_error)
                else:
                    return self.smart_response(speech=s_error)

            # great, we found stuff to play

            # print_d("album: {}".format(album))
            # ('7129185', '2014', 'Going Home (EP)', '\xc3\x81sgeir')
            # ('7131945', 'Last of the Mohicans, The', '1992', 'Jones, Trevor; Edelman, Randy')

            album_id = found_album[0]
            album_year = found_album[1]
            album_name = found_album[2]
            artist_name = found_album[3]

            # do it (play album)
            server.play_album_with_id(album_id)

            s = "OK, playing '{0}', by '{1}', from {2}" \
                .format(album_name,
                        artist_name,
                        album_year)
            return self.smart_response(speech=s)

            # heading = "Number of albums by %s" % best_artist_match
            # if album_count == 1:
            #    desc = "There is 1 album by {0}"\
            #            .format(best_artist_match)
            # else:
            #    desc = "There are {0} albums by {1}" \
            #            .format(album_count, best_artist_match)
            # return self.smart_response(text=heading, speech=desc)

        if intent_name == u'PlayAlbumByArtistIntent':
            s_bad = "album: {0} and/or artist: {1}".format(album_slot, artist_slot)
        else:
            s_bad = "artist: %s" % artist_slot

        return self.smart_response(
            text="Don't understand requested %s" % s_bad,
            speech="Can't find %s" % s_bad)

    @staticmethod
    def process_artist_slot(artist_utterance):
        """
        swaps an artist's first and last names, if applicable
        "Olafur Arnalds" becomes "Olafur, Arnalds" 
        :param artist_utterance: 
        :return: artist_utterance:
        """

        # don't swap special cases
        if any(x in artist_utterance.lower() for x in [
            "acoustic cafe",
            "agent fresco",
            "anderson ponty band",
            "boney m",
            "buddha bar",
            "cafe del mar",
            "camaron de la isla",
            "crosby, stills and nash",
            "crosby, stills & nash",
            "daft punk",
            "dancing fantasy",
            "death cab for cutie",
            "dire straits",
            "earth, wind & fire",
            "electric light orchestra",
            "emerson, lake & palmer",
            "gare du nord",
            "jethro tull",
            "junkie xl",
            "king crimson",
            "kings of convenience",
            "led zeppelin",
            "level 42",
            "mumford & sons",
            "pink floyd",
            "putumayo presents"
            "roxy music",
            "seru giran",
            "sigur ros",
            "simply red",
            "stars of the lid",
            "st. germain",
            "sui generis",
            "taj mahal",
            "talking heads",
            "tame impala",
            "tape five",
            "vancouver sleep clinic",
            "various artists",
            "weather report"
        ]):
            return artist_utterance

        words = artist_utterance.split()
        if len(words) > 1 and ',' not in artist_utterance:
            # "Olafur Arnalds" becomes "Arnalds, Olafur"
            artist_utterance = words[1] + ", " + words[0]
            print_d("artist_utterance now: '%s'" % artist_utterance)

        return artist_utterance
        pass

    @staticmethod
    def process_album_slot(album_utterance):
        """replace specific keywords frok utterance"""

        if "season" in album_utterance.lower():
            album_utterance = album_utterance.replace("season", "s")  # old, new
            print_d("album_utterance now: '%s'" % album_utterance)

        return album_utterance
        pass
