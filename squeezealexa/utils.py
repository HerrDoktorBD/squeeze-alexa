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
import random
import re
import string
import unicodedata
import sys

PY2 = sys.version_info[0] == 2
Char = unichr if PY2 else chr
Unicode = unicode if PY2 else str

print_d = print_w = print


def english_join(items, final="and"):
    """Like join, but in English (no Oxford commas...)"""
    items = list(filter(None, items))
    most = ", ".join(items[0:-1])
    sep = " %s " % final.strip()
    return sep.join(filter(None, [most] + items[-1:]))


_SPACIFIES = {i: u' ' for i in range(sys.maxunicode)
              if unicodedata.category(Char(i)).startswith('P')}

_REMOVALS = {ord(i): None for i in ['\'', '!']}

_SANITISE = {'&': ' N ',
             '+': ' N ',
             '$': 's'}


def remove_punctuation(text):
    if not isinstance(text, Unicode):
        text = text.decode('utf-8')
    return text.translate(_REMOVALS).translate(_SPACIFIES)


def sanitise_text(text):
    """Makes a genre / playlist / artist name safer for Alexa output"""
    if not text:
        return ""
    safer = text
    for (bad, good) in _SANITISE.items():
        safer = safer.replace(bad, good)
    no_punc = remove_punctuation(safer)
    return re.sub(r'\s{2,}', ' ', no_punc)


def with_example(template, lst):
    msg = template % len(lst)
    if lst:
        msg += " (e.g. \"%s\")" % random.choice(lst)
    return msg


def strip_accents(text):
    """
    Strip accents from input String.

    :param text: The input string.
    :type text: String.

    :returns: The processed String.
    :rtype: String.
    """
    try:
        text = unicode(text, 'utf-8')
    except NameError:  # unicode is a default on python 3
        pass
    text = unicodedata.normalize('NFD', text)
    text = text.encode('ascii', 'ignore')
    text = text.decode("utf-8")
    return str(text)


def recover_key(my_dict, value):
    """recover the key from the dictionary value"""
    for a_key in my_dict.keys():
        if my_dict[a_key] == value:
            return a_key
    return None


def sanitize_4(user_input, stop_words):
    """sanitize using standard list comprehension"""
    return [w for w in user_input if w.lower() not in stop_words]


def remove_stop_words(original_s):
    """remove punctuation"""
    s2 = original_s.translate(None, string.punctuation)
    # print_d("s2 (no punct): '%s'" % s2)

    # split
    user_input = s2.split(" ")
    stop_words = ["a", "an", "the", "on", "in",
                  "of", "at", "by", "to", "for", "from"]

    # sanitize
    s1 = sanitize_4(user_input, stop_words)

    # rejoin
    s3 = " ".join(s1)
    # print_d("(sanitize_4): '%s'" % s3)

    return s3
    pass
