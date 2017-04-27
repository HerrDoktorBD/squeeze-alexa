squeeze-alexa
=============

[![Join the chat at https://gitter.im/squeeze-alexa/Lobby](https://badges.gitter.im/squeeze-alexa/Lobby.svg)](https://gitter.im/squeeze-alexa/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)
[![Build Status](https://travis-ci.org/HerrDoktorBD/squeeze-alexa.svg?branch=master)](https://travis-ci.org/HerrDoktorBD/squeeze-alexa)
[![Coverage Status](https://coveralls.io/repos/github/HerrDoktorBD/squeeze-alexa/badge.svg?branch=master)](https://coveralls.io/github/HerrDoktorBD/squeeze-alexa?branch=master)

`squeeze-alexa` is an Amazon Alexa Skill integrating with the Logitech Media Server ("squeezebox"). See the original [announcement blog post](http://declension.net/posts/2016-11-30-alexa-meets-squeezebox/), and the [follow-up with videos](http://declension.net/posts/2017-01-03-squeeze-alexa-demos/).

This is still in beta, so feedback and help with documenting welcome - please just raise an issue first.

Have a look at this 2-min video for a live demo:[![ScreenShot](https://raw.githubusercontent.com/HerrDoktorBD/squeeze-alexa/demo.png)](https://youtu.be/D5MuxX0EqQU)

### Aims

 * Intuitive voice control over common music scenarios
 * Low latency (given that it's a cloud service), i.e. fast at reacting to your commands.
 * Decent security (hopefully)
 * Extensive support for choosing songs by (multiple) genres, and now playlists (BETA)
 * Helpful, conversational responses / interaction.

### Things it is not

 * Full coverage of all LMS features, plugins or use cases - but it aims to be good at what it does.
 * A public / multi-user skill. This means **you will need Alexa and AWS developer accounts**.
 * A native LMS (Squeezeserver) plugin. So whilst this would be cool, at least there's no need to touch your LMS.
 * Easy to set up :scream:

### Controlling your music

These should all work (usually) in the current version:

#### Playback
 * _Alexa, tell Squeezebox to play / pause_ (or just _Alexa, play / pause!_)
 * _Alexa, tell Squeezebox next / previous_ (or just _Alexa, next / previous!_)
 * _Alexa, tell Squeezebox to turn shuffle on / off_ (or just _Alexa, Shuffle On/Off_)

#### Control
 * _Alexa, tell Squeezebox to select the Bedroom player_
 * _Alexa, tell Squeezebox to turn it down in the Living Room_
 * _Alexa, ask Squeezebox to pump it up!_ (defaults to selected)
 * _Alexa, tell Squeezebox to turn everything off_

#### Selecting Music
 * _Alexa, tell Squeezebox to play some Blues and some Jazz_
 * _Alexa, tell Squeezebox to play a mix of Jungle, Dubstep and Hip-Hop_
 * _Alexa, ask Squeezebox to play my Sunday Morning playlist_
 * _Alexa, tell Squeezebox to play the Bad-Ass Metal playlist!_

#### Specific Artists and/or Albums
 * _Alexa, ask Squeezebox to play process by Sampha_
 * _Alexa, ask Squeezebox to play some cafe del mar_
 * _Alexa, ask Squeezebox to play cafe del mar_
 * _Alexa, ask Squeezebox to play asgeir_
 * _Alexa, ask Squeezebox to play some klaus schulze_
 * _Alexa, ask Squeezebox to play the latest by olafur arnalds_
 * _Alexa, ask Squeezebox to play the first blackfield_
 * _Alexa, ask Squeezebox to play game of thrones season 1_
 * _Alexa, ask Squeezebox to play person of interest season 2_
 * _Alexa, ask Squeezebox to play for now i am winter hdtracks_
 * _Alexa, ask Squeezebox to play the last album by blackfield_
 * _Alexa, ask Squeezebox to play the first album by blackfield_
 * _Alexa, ask Squeezebox to play Mylo Xyloto by Coldplay_
 * _Alexa, ask Squeezebox to play some Coldplay_
 * _Alexa, ask Squeezebox to play Pink FLoyd_
 * _Alexa, ask Squeezebox to play any Pink FLoyd_
 * _Alexa, ask Squeezebox play the dark side of the moon_
 * _Alexa, ask Squeezebox to play viva la vida by coldplay_

#### Feedback
 * _Alexa, ask Squeezebox what's playing \[in the Kitchen\]_
 * _Alexa, ask Squeezebox if the server is scanning_
 * _Alexa, ask Squeezebox what is the server status_
 * _Alexa, ask Squeezebox for a server status_

#### Statistics
 * _Alexa, ask Squeezebox how many genres_
 * _Alexa, ask Squeezebox how many songs are there_
 * _Alexa, ask Squeezebox how many artists_
 * _Alexa, ask Squeezebox how many albums do i have_

Most commands can take a player name, or will remember the default / last player if not specified.


I want!
-------
See the [HOWTO](docs/HOWTO.md) for the full details of installing and configuring your own squeeze-alexa instance, or [TROUBLESHOOTING](docs/TROUBLESHOOTING.md) if you're getting stuck.
