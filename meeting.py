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

import os, sys, re
import time, stat
import supybot.utils as utils

from imp import reload
from . import writers
from . import items

reload(writers)
reload(items)

__version__ = "0.3.0"

class Config(object):
    #
    # Throw any overrides into meetingLocalConfig.py in this directory:
    #
    # Where to store files on disk
    # Example:   logFileDir = '/home/richard/meetbot/'
    logFileDir = '/var/www/mootbot/'
    # The links to the logfiles are given this prefix
    # Example:   logUrlPrefix = 'http://rkd.zgib.net/meetbot/'
    logUrlPrefix = ''
    # Give the pattern to save files into here.  Use %(channel)s for
    # channel.  This will be sent through strftime for substituting it
    # times, howover, for strftime codes you must use doubled percent
    # signs (%%).  This will be joined with the directories above.
    filenamePattern = '%(channel)s/%%Y/%(channel)s.%%F-%%H.%%M'
    # Where to say to go for more information about MeetBot
    MeetBotInfoURL = 'https://wiki.debian.org/MeetBot'
    # This is used with the #restrict command to remove permissions from files.
    RestrictPerm = stat.S_IRWXO|stat.S_IRWXG  # g,o perm zeroed
    # RestrictPerm = stat.S_IRWXU|stat.S_IRWXO|stat.S_IRWXG  #u,g,o perm zeroed
    # used to detect #link :
    UrlProtocols = ('http:', 'https:', 'irc:', 'ftp:', 'mailto:', 'ssh:')
    # regular expression for parsing commands.  First group is the cmd name,
    # second group is the rest of the line.
    command_RE = re.compile(r'^#(\w+)(?:\s+(.*?)|)\s*$')
    # The channels which won't have date/time appended to the filename.
    specialChannels = ("#meetbot-test", "#meetbot-test2")
    specialChannelFilenamePattern = '%(channel)s/%(channel)s'
    # HTML irc log highlighting style.  `pygmentize -L styles` to list.
    pygmentizeStyle = 'friendly'
    # Timezone setting.  You can use friendly names like 'US/Eastern', etc.
    # Check /usr/share/zoneinfo/ .  Or `man timezone`: this is the contents
    # of the TZ environment variable.
    timeZone = 'UTC'
    # These are the start and end meeting messages, respectively.
    # Some replacements are done before they are used, using the
    # %(name)s syntax.  Note that since one replacement is done below,
    # you have to use doubled percent signs.  Also, it gets split by
    # '\n' and each part between newlines get said in a separate IRC
    # message.
    startMeetingMessage = ("Meeting started at %(starttime)s %(timeZone)s.  "
              "The chair is %(chair)s.  Information about MeetBot at "
              "%(MeetBotInfoURL)s")
    endMeetingMessage = ("Meeting ended at %(endtime)s %(timeZone)s.  "
                         "Minutes at %(urlBasename)s.moin.txt")
    endMeetingNotification = ("Meeting in %(channel)s has just ended")
    endMeetingNotificationList = ["jose"]

    #TODO: endMeetingMessage should get filenames from the writers

    #should the bot talk in the channel
    beNoisy = True
    # Input/output codecs.
    input_codec = 'utf-8'
    output_codec = 'utf-8'
    # Functions to do the i/o conversion.
    def enc(self, text):
        if sys.version_info < (3,0):
            return text.encode(self.output_codec, 'replace')
        return text
    def dec(self, text):
        if sys.version_info < (3,0):
            return text.decode(self.input_codec, 'replace')
        return text
    # Write out select logfiles
    update_realtime = True
    # CSS configs:
    cssFile_log      = 'default'
    cssEmbed_log     = True
    cssFile_minutes  = 'default'
    cssEmbed_minutes = True
    # Include full log in MoinMoin output
    moinFullLogs = True

    # This tells which writers write out which to extensions.
    writer_map = {
        '.log.html': writers.HTMLlog,
        '.1.html': writers.HTML,
        '.html': writers.HTML2,
        '.rst': writers.ReST,
        '.txt': writers.Text,
        '.rst.html': writers.HTMLfromReST,
        '.moin.txt': writers.Moin,
        '.mw.txt': writers.MediaWiki,
        }

    def __init__(self, M, writeRawLog=False, safeMode=False,
                 extraConfig={}):
        self.M = M
        self.writers = {}
        # Update config values with anything we may have
        for k, v in list(extraConfig.items()):
            setattr(self, k, v)

        if hasattr(self, "init_hook"):
            self.init_hook()
        if writeRawLog:
            self.writers['.log.txt'] = writers.TextLog(self.M)
        for extension, writer in list(self.writer_map.items()):
            self.writers[extension] = writer(self.M)
        self.safeMode = safeMode

    def filename(self, url=False):
        # provide a way to override the filename.  If it is
        # overridden, it must be a full path (and the URL-part may not
        # work.):
        if getattr(self.M, '_filename', None):
            return self.M._filename
        # names useful for pathname formatting.
        # Certain test channels always get the same name - don't need
        # file prolifiration for them
        if self.M.channel in self.specialChannels:
            pattern = self.specialChannelFilenamePattern
        else:
            pattern = self.filenamePattern
        channel = self.M.channel.strip('# ').lower().replace('/', '')
        network = self.M.network.strip(' ').lower().replace('/', '')
        if self.M._meetingname:
            meetingname = self.M._meetingname.replace('/', '')
        else:
            meetingname = channel
        path = pattern % {'channel':channel, 'network':network,
                          'meetingname':meetingname}
        path = time.strftime(path, self.M.starttime)
        # If we want the URL name, append URL prefix and return
        if url:
            return os.path.join(self.logUrlPrefix, path)
        path = os.path.join(self.logFileDir, path)
        # make directory if it doesn't exist...
        dirname = os.path.dirname(path)
        if not url and dirname and not os.access(dirname, os.F_OK):
            os.makedirs(dirname)
        return path

    @property
    def basename(self):
        return os.path.basename(self.M.config.filename())

    def save(self, realtime_update=False):
        """Write all output files.

        If `realtime_update` is true, then this isn't a complete save,
        it will only update those writers with the update_realtime
        attribute true.  (default update_realtime=False for this method)"""
        if realtime_update and not hasattr(self.M, 'starttime'):
            return
        rawname = self.filename()
        # We want to write the rawlog (.log.txt) first in case the
        # other methods break.  That way, we have saved enough to
        # replay.
        writer_names = list(self.writers.keys())
        results = {}
        if '.log.txt' in writer_names:
            writer_names.remove('.log.txt')
            writer_names.insert(0, '.log.txt')
        for extension in writer_names:
            writer = self.writers[extension]
            # Why this?  If this is a realtime (step-by-step) update,
            # then we only want to update those writers which say they
            # should be updated step-by-step.
            if (realtime_update and
                ( not getattr(writer, 'update_realtime', False) or
                  getattr(self, '_filename', None) )
                ):
                continue
            # Parse embedded arguments
            if '|' in extension:
                extension, args = extension.split('|', 1)
                args = args.split('|')
                args = dict([a.split('=', 1) for a in args])
            else:
                args = {}

            text = writer.format(extension, **args)
            results[extension] = text
            # If the writer returns a string or unicode object, then
            # we should write it to a filename with that extension.
            # If it doesn't, then it's assumed that the write took
            # care of writing (or publishing or emailing or wikifying)
            # it itself.
            if isinstance(text, str) or \
                    (sys.version_info < (3,0) and isinstance(text, unicode)):
                # Have a way to override saving, so no disk files are written.
                if getattr(self, "dontSave", False):
                    continue
                self.writeToFile(self.enc(text), rawname+extension)
        if hasattr(self, 'save_hook'):
            self.save_hook(realtime_update=realtime_update)
        return results

    def writeToFile(self, string, filename):
        """Write a given string to a file."""
        # The reason we have this method just for this is to proxy
        # through the _restrictPermissions logic.
        f = open(filename, 'w')
        if self.M._restrictlogs:
            self.restrictPermissions(f)
        f.write(string)
        f.close()

    def restrictPermissions(self, f):
        """Remove the permissions given in the variable RestrictPerm."""
        f.flush()
        newmode = os.stat(f.name).st_mode & (~self.RestrictPerm)
        os.chmod(f.name, newmode)


# Set the timezone, using the variable above
os.environ['TZ'] = Config.timeZone
time.tzset()

# load custom local configurations
try:
    import __main__
    if getattr(__main__, 'running_tests', False): raise ImportError
    if 'MEETBOT_RUNNING_TESTS' in os.environ: raise ImportError

    from . import meetingLocalConfig
    meetingLocalConfig = reload(meetingLocalConfig)
    if hasattr(meetingLocalConfig, 'Config'):
        Config = type('Config', (meetingLocalConfig.Config, Config), {})
except ImportError:
    pass


class MeetingCommands(object):
    # Command definitions
    # generic parameters to these functions:
    #  nick=
    #  line=    <the payload of the line>
    #  linenum= <the line number, 1-based index (for logfile)>
    #  time_=   <time it was said>
    # Commands for chairs
    def do_replay(self, line, **kwargs):
        url = line
        self.reply("Looking for meetings in: " + url)
        htmlSource = utils.web.getUrl(url)
        print(htmlSource)

    def do_startmeeting(self, line, time_, **kwargs):
        """Begin a meeting."""
        self.starttime = time_
        repl = self.replacements()
        message = self.config.startMeetingMessage % repl
        for messageline in message.split('\n'):
            self.reply(messageline)
        self.do_private_commands(self.owner)
        for chair in self.chairs:
            self.do_private_commands(chair)
        self.do_commands()
        if line:
            self.do_meetingtopic(line=line, time_=time_, **kwargs)

    def do_endmeeting(self, nick, line, time_, **kwargs):
        """End the meeting."""
        if not self.isChair(nick): return
        #close any open votes
        if self.activeVote:
            endVoteKwargs = {"linenum": kwargs.get("linenum", "0"),
                 "time_": time.localtime()}
            self.do_endvote(nick=nick, line=line, **endVoteKwargs)
        if self.oldtopic:
            self.topic(self.oldtopic)
        self.endtime = time_
        self.config.save()
        repl = self.replacements()
        message = self.config.endMeetingMessage % repl
        for messageline in message.split('\n'):
            self.reply(messageline)
        self._meetingIsOver = True
        for nickToPM in self.config.endMeetingNotificationList:
            self.privateReply(nickToPM, self.config.endMeetingNotification % repl)

    def do_topic(self, nick, line, **kwargs):
        """Set a new topic in the channel."""
        if not self.isChair(nick): return
        self.currenttopic = line
        m = items.Topic(nick=nick, line=line, **kwargs)
        self.additem(m)
        self.settopic()

    def do_subtopic(self, nick, **kwargs):
        """This is like a topic but less so."""
        if not self.isChair(nick): return
        m = items.Subtopic(nick=nick, **kwargs)
        self.additem(m)
    do_progress = do_subtopic

    def do_meetingtopic(self, nick, line, **kwargs):
        """Set a meeting topic (included in all topics)."""
        if not self.isChair(nick): return
        if not line or line.lower() in ('none', 'unset'):
            self._meetingTopic = None
        else:
            self._meetingTopic = line
        self.settopic()

    def do_save(self, nick, time_, **kwargs):
        """Add a chair to the meeting."""
        if not self.isChair(nick): return
        self.endtime = time_
        self.config.save()

    def do_done(self, nick, **kwargs):
        """Add aggreement to the minutes - chairs only."""
        if not self.isChair(nick): return
        m = items.Done(nick=nick, **kwargs)
        self.additem(m)

    def do_agreed(self, nick, **kwargs):
        """Add aggreement to the minutes - chairs only."""
        if not self.isChair(nick): return
        m = items.Agreed(nick=nick, **kwargs)
        self.additem(m)
        if self.config.beNoisy:
            self.reply("AGREED: " + m.line)
    do_agree = do_agreed

    def do_accepted(self, nick, **kwargs):
        """Add aggreement to the minutes - chairs only."""
        if not self.isChair(nick): return
        m = items.Accepted(nick=nick, **kwargs)
        self.additem(m)
    do_accept = do_accepted

    def do_rejected(self, nick, **kwargs):
        """Add aggreement to the minutes - chairs only."""
        if not self.isChair(nick): return
        m = items.Rejected(nick=nick, **kwargs)
        self.additem(m)
    do_reject = do_rejected

    def do_chair(self, nick, line, **kwargs):
        """Add a chair to the meeting."""
        if not self.isChair(nick): return
        for chair in re.split('[, ]+', line):
            if not chair: continue
            if chair not in self.chairs:
                if self._channelNicks and \
                        self.config.enc(chair) not in self._channelNicks():
                    self.reply("Warning: '%s' not in channel" % chair)
                self.addnick(chair, lines=0)
                self.chairs[chair] = True
                self.do_private_commands(chair)
        self.reply("Current chairs: " + ', '.join(sorted(set(list(self.chairs.keys()) + [self.owner]))))

    def do_unchair(self, nick, line, **kwargs):
        """Remove a chair from the meeting (founder cannot be removed)."""
        if not self.isChair(nick): return
        for chair in re.split('[, ]+', line):
            if not chair: continue
            if chair in self.chairs:
                del self.chairs[chair]
        self.reply("Current chairs: " + ', '.join(sorted(set(list(self.chairs.keys()) + [self.owner]))))

    def do_undo(self, nick, **kwargs):
        """Remove the last item from the minutes."""
        if not self.isChair(nick): return
        if not self.minutes: return
        self.reply("Removing item from minutes: " + str(self.minutes[-1].itemtype))
        del self.minutes[-1]

    def do_restrictlogs(self, nick, **kwargs):
        """When saved, remove permissions from the files."""
        if not self.isChair(nick): return
        self._restrictlogs = True
        self.reply("Restricting permissions on minutes: -%s on next #save" % \
                   oct(RestrictPerm))

    def do_lurk(self, nick, **kwargs):
        """Don't interact in the channel."""
        if not self.isChair(nick): return
        self._lurk = True

    def do_unlurk(self, nick, **kwargs):
        """Do interact in the channel."""
        if not self.isChair(nick): return
        self._lurk = False

    def do_meetingname(self, nick, line, **kwargs):
        """Set the variable (meetingname) which can be used in save.

        If this isn't set, it defaults to the channel name."""
        if not self.isChair(nick): return
        meetingname = "_".join(line.lower().split())
        self._meetingname = meetingname
        self.reply("Meeting name set to: " + meetingname)

    def do_vote(self, nick, line, **kwargs):
        """Start a voting process."""
        if not self.isChair(nick): return
        if self.activeVote:
            self.reply("Voting still open on: " + self.activeVote)
            return
        self.activeVote = line
        self.currentVote = {}
        self.publicVoters[self.activeVote] = []
        #Need the line number for linking to the html output
        self.currentVoteStartLine = len(self.lines)
        #need to set up a structure to hold vote results
        #people can vote by saying +1, -1 or +0
        #if voters have been specified then only they can vote
        #there can be multiple votes called in a meeting
        self.reply("Please vote on: " + self.activeVote)
        self.reply(("Public votes can be registered by saying +1, -1 or +0 in channel "
            "(for private voting, private message me with 'vote +1|-1|+0 #channelname')"))

    def do_votesrequired(self, nick, line, **kwargs):
        """Set the number of votes required to pass a motion -
        useful for council votes where 3 of 5 people need to +1 for example."""
        if not self.isChair(nick): return
        try:
            self.votesrequired = int(line)
        except ValueError:
            self.votesrequired = 0
        self.reply("Votes now need %d to be passed" % self.votesrequired)

    def do_endvote(self, nick, line, **kwargs):
        """This vote is over, record the results."""
        if not self.isChair(nick): return
        if not self.activeVote:
            self.reply("No vote in progress")
            return

        self.reply("Voting ended on: " + self.activeVote)
        #should probably just store the summary of the results
        vfor = 0
        vagainst = 0
        vabstain = 0
        for v in list(self.currentVote.values()):
            if re.match(r'\+1\b', v):
                vfor += 1
            elif re.match(r'-1\b', v):
                vagainst += 1
            elif re.match(r'[+-]?0\b', v):
                vabstain += 1

        self.reply("Votes for: %d, Votes against: %d, Abstentions: %d" % (vfor, vagainst, vabstain))
        if vfor - vagainst >= self.votesrequired:
            self.reply("Motion carried")
            voteResult = "Carried"
            motion = "Motion carried"
        elif vfor - vagainst < self.votesrequired:
            self.reply("Motion denied")
            voteResult = "Denied"
            motion = "Motion denied"
        elif not self.votesrequired:
            self.reply("Deadlock, casting vote may be used")
            voteResult = "Deadlock"
            motion = "Motion deadlocked"
        #store the results
        voteSummary = "%s (For: %d, Against: %d, Abstained: %d)" % (motion, vfor, vagainst, vabstain)
        self.votes[self.activeVote] = (voteSummary, self.currentVoteStartLine)

        """Add informational item to the minutes."""
        voteResultLog = "%s (%s)" % (self.activeVote, voteResult)
        m = items.Vote(nick=nick, line=voteResultLog, **kwargs)
        self.additem(m)

        #allow another vote to be called
        self.activeVote = ""
        self.currentVote = {}
        self.currentVoteStartLine = 0

    def do_voters(self, nick, line, **kwargs):
        if not self.isChair(nick): return
        """Provide a list of authorised voters."""
        #possibly should provide a means to change voters to everyone
        for voter in re.split('[, ]+', line):
            if not voter: continue
            if voter in ('everyone', 'everybody', 'all'):
                #clear the voter list
                self.voters = {}
                self.reply("Everyone can now vote")
                return
            if voter not in self.voters:
                if self._channelNicks and \
                        self.config.enc(voter) not in self._channelNicks():
                    self.reply("Warning: '%s' not in channel" % voter)
                self.addnick(voter, lines=0)
                self.voters[voter] = True
        self.reply("Current voters: " + ', '.join(sorted(set(list(self.voters.keys()) + [self.owner]))))

    def do_private_commands(self, nick, **kwargs):
        commands = sorted(["#"+x[3:] for x in dir(self) if x[:3] == "do_"])
        message = "Available commands: " + ', '.join(commands)
        self.privateReply(nick, message)

    # Commands for anyone
    def do_action(self, **kwargs):
        """Add action item to the minutes.

        The line is searched for nicks, and a per-person action item
        list is compiled after the meeting.  Only nicks which have
        been seen during the meeting will have an action item list
        made for them, but you can use the #nick command to cause a
        nick to be seen."""
        m = items.Action(**kwargs)
        self.additem(m)
        if self.config.beNoisy:
            self.reply("ACTION: " + m.line)
    def do_info(self, **kwargs):
        """Add informational item to the minutes."""
        m = items.Info(**kwargs)
        self.additem(m)
    def do_idea(self, **kwargs):
        """Add informational item to the minutes."""
        m = items.Idea(**kwargs)
        self.additem(m)
    def do_help(self, **kwargs):
        """Add call for help to the minutes."""
        m = items.Help(**kwargs)
        self.additem(m)
    do_halp = do_help
    def do_nick(self, nick, line, **kwargs):
        """Make meetbot aware of a nick which hasn't said anything.

        To see where this can be used, see #action command."""
        nicks = re.split('[, ]+', line)
        for nick in nicks:
            if not nick: continue
            self.addnick(nick, lines=0)
    def do_link(self, **kwargs):
        """Add informational item to the minutes."""
        m = items.Link(**kwargs)
        self.additem(m)
    def do_commands(self, **kwargs):
        commands = sorted(["action", "info", "idea", "nick", "link", "commands"])
        self.reply("Available commands: " + ', '.join(commands))


class Meeting(MeetingCommands, object):
    _lurk = False
    _restrictlogs = False
    def __init__(self, channel, owner, oldtopic=None,
                 filename=None, writeRawLog=False,
                 setTopic=None, sendReply=None, sendPrivateReply=None,
                 getRegistryValue=None,
                 safeMode=False, channelNicks=None,
                 extraConfig={}, network='nonetwork'):
        self.config = Config(self, writeRawLog=writeRawLog, safeMode=safeMode,
                            extraConfig=extraConfig)
        if getRegistryValue is not None:
            self._registryValue = getRegistryValue
        if sendReply is not None:
            self._sendReply = sendReply
        if sendPrivateReply is not None:
            self._sendPrivateReply = sendPrivateReply
        if setTopic is not None:
            self._setTopic = setTopic
        self.owner = owner
        self.channel = channel
        self.network = network
        self.currenttopic = ""
        if oldtopic:
            self.oldtopic = self.config.dec(oldtopic)
        else:
            self.oldtopic = None
        self.lines = []
        self.minutes = []
        self.attendees = {}
        self.chairs = {}
        self.voters = {}
        self.publicVoters = {}
        self.votes = {}
        self.votesrequired = 0
        self.activeVote = ""
        self._writeRawLog = writeRawLog
        self._meetingTopic = None
        self._meetingname = ""
        self._meetingIsOver = False
        self._channelNicks = channelNicks
        if filename:
            self._filename = filename

    # These commands are callbacks to manipulate the IRC protocol.
    # set self._sendReply and self._setTopic to an callback to do these things.
    def reply(self, x):
        """Send a reply to the channel."""
        if hasattr(self, '_sendReply') and not self._lurk:
            self._sendReply(self.config.enc(x))
        else:
            print("REPLY:", self.config.enc(x))
    def privateReply(self, nick, x):
        """Send a reply to nick."""
        if hasattr(self, '_sendPrivateReply') and not self._lurk:
            self._sendPrivateReply(self.config.enc(nick), self.config.enc(x))
    def topic(self, x):
        """Set the topic in the channel."""
        if hasattr(self, '_setTopic') and not self._lurk:
            self._setTopic(self.config.enc(x))
        else:
            print("TOPIC:", self.config.enc(x))
    def settopic(self):
        """The actual code to set the topic."""
        if self._meetingTopic:
            if "meeting" in self._meetingTopic.lower():
                topic = '%s | %s | Current topic: %s' % (self.oldtopic, self._meetingTopic, self.currenttopic)
            else:
                topic = '%s | %s Meeting | Current topic: %s' % (self.oldtopic, self._meetingTopic, self.currenttopic)
        else:
            topic = self.currenttopic
        self.topic(topic)
    def addnick(self, nick, lines=1):
        """This person has spoken, lines=<how many lines>"""
        self.attendees[nick] = self.attendees.get(nick, 0) + lines
    def isChair(self, nick):
        """Is the nick a chair?"""
        return (nick == self.owner or nick in self.chairs or self.isop)
    def isop(self, nick):
        return self.isop
    def save(self, **kwargs):
        return self.config.save(**kwargs)

    # Primary entry point for new lines in the log
    def addline(self, nick, line, isop=False, time_=None):
        """This is the way to add lines to the Meeting object."""
        if not time_: time_ = time.localtime()
        linenum = self.addrawline(nick, line, time_)
        nick = self.config.dec(nick)
        line = self.config.dec(line)
        self.isop = isop
        # Handle any commands given in the line
        matchobj = self.config.command_RE.match(line)
        if matchobj:
            command, line = matchobj.groups('')
            command = command.lower()
            # to define new commands, define a method do_commandname
            if hasattr(self, "do_"+command):
                getattr(self, "do_"+command)(nick=nick, line=line,
                                             linenum=linenum, time_=time_)
        else:
            # Detect URLs automatically
            if line.split('//')[0] in self.config.UrlProtocols:
                self.do_link(nick=nick, line=line,
                             linenum=linenum, time_=time_)
        self.save(realtime_update=True)
        if re.match(r'([+-]1|[+-]?0)\b', line):
            self.doCastVote(nick, line, time_)

    def doCastVote(self, nick, line, time_=None, private=False):
            """If a vote is under way and the nick is a registered voter
            and has not already voted in this vote, add the voter name and record the vote.

            If the voter has already voted, should it reject the second vote,
            or allow them to change their vote?"""
            if not self.voters or nick in self.voters:
                if self.activeVote:
                    self.currentVote[nick] = line
                    if not private:
                        self.publicVoters[self.activeVote].append(nick)
                        self.reply("%s received from %s" % (line, nick))

            #if the vote was in a private message - how do we do that??
            #self.reply(line + " received from a private vote")
            #we do record the voter name in the voting structure even if private, so they can't vote twice

    def addrawline(self, nick, line, time_=None):
        """This adds a line to the log, bypassing command execution."""
        nick = self.config.dec(nick)
        line = self.config.dec(line)
        self.addnick(nick)
        line = line.strip('\x01') # \x01 is present in ACTIONs
        # Setting a custom time is useful when replaying logs,
        # otherwise use our current time:
        if not time_: time_ = time.localtime()

        # Handle the logging of the line
        if line[:6] == 'ACTION':
            logline = "%s * %s %s" % (time.strftime("%H:%M", time_),
                                nick, line[7:].lstrip())
        else:
            logline = "%s <%s> %s" % (time.strftime("%H:%M", time_),
                                nick, line)
        self.lines.append(logline)
        linenum = len(self.lines)
        return linenum

    def additem(self, m):
        """Add an item to the meeting minutes list."""
        self.minutes.append(m)

    def replacements(self):
        repl = {}
        repl['channel'] = self.channel
        repl['network'] = self.network
        repl['MeetBotInfoURL'] = self.config.MeetBotInfoURL
        repl['timeZone'] = self.config.timeZone
        repl['starttime'] = repl['endtime'] = "None"
        if getattr(self, "starttime", None):
            repl['starttime'] = time.strftime("%H:%M:%S", self.starttime)
        if getattr(self, "endtime", None):
            repl['endtime'] = time.strftime("%H:%M:%S", self.endtime)
        repl['__version__'] = __version__
        repl['chair'] = self.owner
        repl['urlBasename'] = self.config.filename(url=True)
        return repl


def parse_time(time_):
    try: return time.strptime(time_, "%H:%M:%S")
    except ValueError: pass
    try: return time.strptime(time_, "%H:%M")
    except ValueError: pass
logline_re = re.compile(r'^\[?([0-9: ]*?)\]? *<[@%&+ ]?([^>]+)> *(.*?) *$')
loglineAction_re = re.compile(r'^\[?([0-9: ]*?)\]? *\* *([^ ]+) *(.*?) *$')


def process_meeting(contents, channel, filename,
                    extraConfig = {},
                    dontSave=False,
                    safeMode=True):
    M = Meeting(channel=channel, owner=None,
                filename=filename, writeRawLog=False, safeMode=safeMode,
                extraConfig=extraConfig)
    if dontSave:
        M.config.dontSave = True
    # process all lines
    for line in contents.split('\n'):
        # match regular spoken lines:
        m = logline_re.match(line)
        if m:
            time_ = parse_time(m.group(1))
            nick = m.group(2)
            line = m.group(3)
            if not M.owner:
                M.owner = nick; M.chairs = {nick:True}
            M.addline(nick, line, time_=time_)
        # match /me lines
        m = loglineAction_re.match(line)
        if m:
            time_ = parse_time(m.group(1))
            nick = m.group(2)
            line = m.group(3)
            M.addline(nick, "ACTION "+line, time_=time_)
    return M


def replay_meeting(channel,
                   extraConfig = {},
                   dontSave=False,
                   safeMode=True):
    M = Meeting(channel=channel, owner=None,
                writeRawLog=False, safeMode=safeMode,
                extraConfig=extraConfig)


# None of this is very well refined.
if __name__ == '__main__':
    if sys.argv[1] == 'replay':
        fname = sys.argv[2]
        m = re.match('(.*)\.log\.txt', fname)
        if m:
            filename = m.group(1)
        else:
            filename = os.path.splitext(fname)[0]
        print('Saving to:', filename)
        channel = '#'+os.path.basename(sys.argv[2]).split('.')[0]

        M = Meeting(channel=channel, owner=None,
                    filename=filename, writeRawLog=False)
        f = open(sys.argv[2])
        for line in f:
            # match regular spoken lines:
            m = logline_re.match(line)
            if m:
                time_ = parse_time(m.group(1))
                nick = m.group(2)
                line = m.group(3)
                if not M.owner:
                    M.owner = nick; M.chairs = {nick:True}
                M.addline(nick, line, time_=time_)
            # match /me lines
            m = loglineAction_re.match(line)
            if m:
                time_ = parse_time(m.group(1))
                nick = m.group(2)
                line = m.group(3)
                M.addline(nick, "ACTION "+line, time_=time_)
        f.close()
        #M.save() # should be done by #endmeeting in the logs!
    else:
        print("Command '%s' not found" % sys.argv[1])
