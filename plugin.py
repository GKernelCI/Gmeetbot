###
# Copyright (c) 2009, Richard Darst
# Copyright (c) 2018, Krytarik Raido
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

from supybot.commands import *
import supybot.utils as utils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.log as supylog

import re, time
from . import meeting

# By doing this, we can not lose all of our meetings across plugin
# reloads.  But, of course, you can't change the source too
# drastically if you do that!
try:               meeting_cache
except NameError:  meeting_cache = {}
try:               recent_meetings
except NameError:  recent_meetings = []


class MeetBot(callbacks.Plugin):
    """Add the help for "@plugin help MeetBot" here.
    This should describe *how* to use this plugin."""

    def __init__(self, irc):
        self.__parent = super(MeetBot, self)
        self.__parent.__init__(irc)

    # Instead of using real Supybot commands, I just listen to ALL
    # messages coming in and respond to those beginning with our
    # prefix char.  I found this helpful from a not duplicating logic
    # standpoint (as well as other things).  Ask me if you have more
    # questions.

    # This captures all messages coming into the bot.
    def doPrivmsg(self, irc, msg):
        nick = msg.nick
        channel = msg.channel
        network = irc.network
        payload = msg.args[1].strip()

        # These callbacks are used to send data to the channel
        def _setTopic(x):
            irc.queueMsg(ircmsgs.topic(channel, x))
        def _sendReply(x):
            irc.queueMsg(ircmsgs.privmsg(channel, x))
        def _sendPrivateReply(nick, x):
            irc.queueMsg(ircmsgs.privmsg(nick, x))
        def _channelNicks():
            return irc.state.channels[channel].users

        def isChair(nick):
            """Is the nick a chair?"""
            return (nick == M.owner or nick in M.chairs or
                    nick in irc.state.channels[channel].ops)

        logfile_RE = re.compile(r'^.*/([^.]+)\.([0-9]{4}(-[0-9]{2}){3}(\.[0-9]{2}){1,2})\..*$')
        def parse_time(time_):
            try: return time.strptime(time_, "%Y-%m-%d-%H.%M")
            except ValueError: pass
            try: return time.strptime(time_, "%Y-%m-%d-%H.%M.%S")
            except ValueError: pass

        # The following is for debugging.  It's excellent to get an
        # interactive interperter inside of the live bot.  use
        # code.interact instead of my souped-up version if you aren't
        # on my computer:
        #if payload == 'interact':
        #    from rkddp.interact import interact ; interact()

        # Get our Meeting object, if one exists.  Have to keep track
        # of different servers/channels.
        # (channel, network) tuple is our lookup key.
        Mkey = (channel, network)
        M = meeting_cache.get(Mkey, None)

        # Start meeting if we are requested
        if payload[:13].lower() == '#startmeeting':
            if M:
                irc.error("Can't start another meeting, one is in progress",
                          private=True)
                return
            M = meeting.Meeting(channel=channel, network=network, owner=nick,
                                botIsOp=irc.state.channels[channel].isOp(irc.nick),
                                oldtopic=irc.state.channels[channel].topic,
                                writeRawLog=True, safeMode=True,
                                getRegistryValue=self.registryValue,
                                setTopic=_setTopic, sendReply=_sendReply,
                                sendPrivateReply=_sendPrivateReply,
                                channelNicks=_channelNicks)
            meeting_cache[Mkey] = M
            recent_meetings.append(
                (channel, network, time.ctime()))
            if len(recent_meetings) > 10:
                del recent_meetings[0]
        # Replay meeting
        elif payload[:7].lower() == '#replay':
            if M:
                irc.error("Can't replay logs while a meeting is in progress",
                          private=True)
                return
            M = meeting.Meeting(channel=channel, network=network, owner=None,
                                botIsOp=irc.state.channels[channel].isOp(irc.nick),
                                oldtopic=irc.state.channels[channel].topic,
                                writeRawLog=True, safeMode=True,
                                getRegistryValue=self.registryValue)
            meeting_cache[Mkey] = M
            recent_meetings.append(
                (channel, network, time.ctime()))
            if len(recent_meetings) > 10:
                del recent_meetings[0]
            url = payload[7:].strip().split()[0]
            if url:
                m = logfile_RE.match(url)
                if m:
                    M.channel = "#"+m.group(1)
                    M.starttime = parse_time(m.group(2))
                M.replay(url)
                if not M._meetingIsOver:
                    M._setTopic=_setTopic; M._sendReply=_sendReply
                    M._sendPrivateReply=_sendPrivateReply
                    M._channelNicks=_channelNicks
                else:
                    del meeting_cache[Mkey]
            return
        # End meeting on issues with saving the logs
        elif payload[:11].lower() == '#endmeeting' \
                and M and M._meetingIsOver and isChair(nick):
            M.endmeeting()
            del meeting_cache[Mkey]
        elif payload[:13].lower() == '#abortmeeting' \
                and M and isChair(nick):
            if not M._meetingIsOver:
                M.topic(M.oldtopic)
                M.endtime = time.localtime()
                M._meetingIsOver = True
            del meeting_cache[Mkey]
            irc.reply("Meeting ended without saving its logs")

        # If there is no meeting going on, then we quit
        if not M or M._meetingIsOver: return
        # Add line to our meeting buffer
        isop = (nick in irc.state.channels[channel].ops)
        M.addline(nick, payload, isop)
        # End meeting if requested
        if M._meetingIsOver:
            del meeting_cache[Mkey]

    def vote(self, irc, msg, args):
        """<+1|-1|+0> <channel>

        Vote by private message."""
        nick = msg.nick
        channel = msg.channel
        network = irc.network
        payload = msg.args[1].strip()

        """ substring to remove 'vote ' from payload """
        payload = payload[5:]

        """ private voting system """
        if channel[0] != '#' and re.match(r'([+-]1|[+-]?0)\b', payload):
            for key in list(meeting_cache.keys()):
                if payload.endswith(key[0]):
                    voteMeeting = meeting_cache.get(key, None)
                    if voteMeeting:
                        time_ = time.localtime()
                        private = True
                        voteMeeting.doCastVote(nick, payload, time_, private)
                        irc.reply("Received for vote: " + voteMeeting.activeVote)
                    else:
                        irc.reply("No active meetings in this channel")
    vote = wrap(vote, ["something", "channel"])

    def outFilter(self, irc, msg):
        """Log outgoing messages from Supybot."""
        # Catch Supybot's own outgoing messages to log them.  Run the
        # whole thing in a try: block to prevent all output from
        # getting clobbered.
        try:
            if msg.command in ('PRIVMSG',):
                # Note that we have to get our nick and network parameters
                # in a slightly different way here, compared to doPrivmsg.
                nick = irc.nick
                channel = msg.channel
                payload = msg.args[1].strip()
                Mkey = (channel, irc.network)
                M = meeting_cache.get(Mkey, None)
                if M:
                    M.addrawline(nick, payload)
        except:
            import traceback
            supylog.debug(traceback.print_exc())
            supylog.debug("(above exception in outFilter, ignoring)")
        return msg

    # These are admin commands, for use by the bot owner when there
    # are many channels which may need to be independently managed.

    def listmeetings(self, irc, msg, args):
        """

        List all currently active meetings."""
        reply = ", ".join([str(x) for x in sorted(meeting_cache.keys())])
        if not reply:
            irc.reply("No currently active meetings")
        else:
            irc.reply(reply)
    listmeetings = wrap(listmeetings, ['admin'])

    def savemeetings(self, irc, msg, args):
        """

        Save all currently active meetings."""
        for M in list(meeting_cache.items()):
            if not M._meetingIsOver:
                M.endtime = time.localtime()
            M.config.save()
        irc.reply("Saved %d meetings" % len(list(meeting_cache.items())))
    savemeetings = wrap(savemeetings, ['admin'])

    def addchair(self, irc, msg, args, channel, network, nick):
        """<channel> <network> <nick>

        Add a nick as a chair to the meeting."""
        Mkey = (channel, network)
        M = meeting_cache.get(Mkey, None)
        if not M:
            irc.reply("Meeting on channel %s, network %s not found" % (
                channel, network))
            return
        M.chairs.setdefault(nick, True)
        irc.reply("Chair added: %s on (%s, %s)" % (nick, channel, network))
    addchair = wrap(addchair, ['admin', "channel", "something", "nick"])

    def deletemeeting(self, irc, msg, args, channel, network, save):
        """<channel> <network> <saveit=True>

        Delete a meeting from the cache.  If save is given, save the
        meeting first, defaults to saving."""
        Mkey = (channel, network)
        if Mkey not in meeting_cache:
            irc.reply("Meeting on channel %s, network %s not found" % (
                channel, network))
            return
        if save:
            M = meeting_cache[Mkey]
            if not M._meetingIsOver:
                M.endtime = time.localtime()
            M.config.save()
        del meeting_cache[Mkey]
        irc.reply("Deleted meeting on (%s, %s)" % (channel, network))
    deletemeeting = wrap(deletemeeting, ['admin', "channel", "something",
                               optional("boolean", True)])

    def recent(self, irc, msg, args):
        """

        List recent meetings for admin purposes.
        """
        reply = []
        for channel, network, ctime in recent_meetings:
            Mkey = (channel, network)
            if Mkey in meeting_cache:   state = ", running"
            else:                       state = ""
            reply.append("(%s, %s, %s%s)" % (channel, network, ctime, state))
        if reply:
            irc.reply(" ".join(reply))
        else:
            irc.reply("No recent meetings in internal state")
    recent = wrap(recent, ['admin'])

    def pingall(self, irc, msg, args, message):
        """<text>

        Send a broadcast ping to all users on the channel.

        A message to be sent along with this ping must also be
        supplied for this command to work.
        """
        nick = msg.nick
        channel = msg.channel
        payload = msg.args[1].strip()

        # We require a message to go out with the ping, we don't want
        # to waste people's time:
        if channel[0] != '#':
            irc.reply("Not joined to any channel")
            return
        if not message:
            irc.reply(("You must supply a description with the `pingall` command.  "
                "We don't want to go wasting people's times looking for why they are pinged."))
            return

        # Send announcement message
        irc.queueMsg(ircmsgs.privmsg(channel, message))
        # ping all nicks in lines of about 256
        nickline = ''
        nicks = sorted(irc.state.channels[channel].users,
                       key=lambda x: x.lower())
        for nick in nicks:
            nickline += nick + ' '
            if len(nickline) > 256:
                irc.queueMsg(ircmsgs.privmsg(channel, nickline))
                nickline = ''
        irc.queueMsg(ircmsgs.privmsg(channel, nickline))
        # Send announcement message
        irc.queueMsg(ircmsgs.privmsg(channel, message))
    pingall = wrap(pingall, [optional('text', None)])

#    def __getattr__(self, name):
#        """Proxy between proper Supybot commands and # MeetBot commands.
#
#        This allows you to use MeetBot: <command> <line of the command>
#        instead of the typical #command version.  However, it's disabled
#        by default as there are some possible unresolved issues with it.
#
#        To enable this, you must comment out a line in the main code.
#        It may be enabled in a future version.
#        """
#        # First, proxy to our parent classes (__parent__ set in __init__)
#        try:
#            return self.__parent.__getattr__(name)
#        except AttributeError:
#            pass
#        # Disabled for now.  Uncomment this if you want to use this.
#        raise AttributeError
#
#        if not hasattr(meeting.Meeting, "do_"+name):
#            raise AttributeError
#
#        def wrapped_function(self, irc, msg, args, message):
#            channel = msg.channel
#            payload = msg.args[1].strip()
#
#            #from fitz import interactnow ; reload(interactnow)
#
#            payload = "#%s %s" % (name, message)
#            import copy
#            msg = copy.copy(msg)
#            msg.args = (channel, payload)
#
#            self.doPrivmsg(irc, msg)
#        # Give it the signature we need to be a callable Supybot
#        # command (it does check more than I'd like).  Heavy Wizardry.
#        instancemethod = type(self.__getattr__)
#        wrapped_function = wrap(wrapped_function, [optional('text', '')])
#        return instancemethod(wrapped_function, self, MeetBot)

Class = MeetBot


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
