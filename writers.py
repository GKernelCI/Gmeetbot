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

import os, re, time
import textwrap

from . import __version__

# Data sanitizing for various output methods
def html(text):
    """Escape bad sequences (in HTML) in user-generated lines."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
rstReplaceRE = re.compile('_( |-|$)')
def rst(text):
    """Escapes bad sequences in reST"""
    return rstReplaceRE.sub(r'\_\1', text)
def text(text):
    """Escapes bad sequences in text (not implemented yet)"""
    return text
def mw(text):
    """Escapes bad sequences in MediaWiki markup (not implemented yet)"""
    return text
def moin(text):
    """Escapes bad sequences in Moin Moin wiki markup (not implemented yet)"""
    return text


# wraping functions (for RST)
class TextWrapper(textwrap.TextWrapper):
    wordsep_re = re.compile(r'(\s+)')

def wrapList(item, indent=0):
    return TextWrapper(width=72, initial_indent=' '*indent,
                       subsequent_indent=' '*(indent+2),
                       break_long_words=False).fill(item)

def indentItem(item, indent=0):
    return ' '*indent + item

def replaceWRAP(item):
    re_wrap = re.compile(r'sWRAPs(.*)eWRAPe', re.DOTALL)
    def repl(m):
        return TextWrapper(width=72, break_long_words=False).fill(m.group(1))
    return re_wrap.sub(repl, item)


class _BaseWriter(object):
    def __init__(self, M, **kwargs):
        self.M = M

    def format(self, extension=None):
        """Override this method to implement the formatting.

        For file output writers, the method should return a unicode
        object containing the contents of the file to write.

        The argument 'extension' is the key from `writer_map`.  For
        file writers, this can (and should) be ignored.  For non-file
        outputs, this can be used to This can be used to pass data,
        """
        raise NotImplementedError

    @property
    def pagetitle(self):
        if self.M._meetingTopic:
            title = "%s: %s" % (self.M.channel, self.M._meetingTopic)
            if "meeting" not in self.M._meetingTopic.lower():
                title += ' meeting'
            return title
        return "%s meeting" % self.M.channel

    def replacements(self):
        return {'pageTitle':self.pagetitle,
                'owner':self.M.owner,
                'starttime':time.strftime("%H:%M:%S", self.M.starttime),
                'starttimeshort':time.strftime("%H:%M", self.M.starttime),
                'startdate':time.strftime("%d %b", self.M.starttime),
                'endtime':time.strftime("%H:%M:%S", self.M.endtime),
                'endtimeshort':time.strftime("%H:%M", self.M.endtime),
                'timeZone':self.M.config.timeZone,
                'fullLogs':self.M.config.basename+'.log.html',
                'fullLogsFullURL':self.M.config.filename(url=True)+'.log.html',
                'MeetBotInfoURL':self.M.config.MeetBotInfoURL,
                'MeetBotVersion':__version__,
             }

    def iterNickCounts(self):
        nicks = [ (n,c) for (n,c) in list(self.M.attendees.items()) ]
        nicks.sort(key=lambda x: x[1], reverse=True)
        return nicks

    def iterActionItemsNick(self):
        for nick in sorted(list(self.M.attendees.keys()), key=lambda x: x.lower()):
            def nickitems():
                for m in self.M.minutes:
                    # The hack below is needed because of pickling problems
                    if m.itemtype != "ACTION": continue
                    if not re.match(r'.*\b%s\b.*' % re.escape(nick), m.line, re.I):
                        continue
                    m.assigned = True
                    yield m
            yield nick, nickitems()
    def iterActionItemsUnassigned(self):
        for m in self.M.minutes:
            if m.itemtype != "ACTION": continue
            if getattr(m, 'assigned', False): continue
            yield m

    def get_template(self, escape=lambda s: s):
        M = self.M
        repl = self.replacements()

        MeetingItems = [ ]
        # We can have initial items with NO initial topic.  This
        # messes up the templating, so, have this null topic as a
        # stopgap measure.
        nextTopic = {'topic':{'itemtype':'TOPIC', 'topic':'Prologue',
                              'nick':'',
                              'time':'', 'link':'', 'anchor':''},
                     'items':[]}
        haveTopic = False
        for m in M.minutes:
            if m.itemtype == "TOPIC":
                if nextTopic['topic']['nick'] or nextTopic['items']:
                    MeetingItems.append(nextTopic)
                nextTopic = {'topic':m.template(M, escape), 'items':[]}
                haveTopic = True
            else:
                nextTopic['items'].append(m.template(M, escape))
        MeetingItems.append(nextTopic)
        repl['MeetingItems'] = MeetingItems
        # Format of MeetingItems:
        # [ {'topic': {item_dict},
        #    'items': [item_dict, item_object, item_object, ...]
        #    },
        #   { 'topic':...
        #     'items':...
        #    },
        #   ....
        # ]
        #
        # an item_dict has:
        # item_dict = {'itemtype': TOPIC, ACTION, IDEA, or so on...
        #              'line': the actual line that was said
        #              'nick': nick of who said the line
        #              'time': 10:53:15, for example, the time
        #              'link': ${link}#${anchor} is the URL to link to.
        #                      (page name, and bookmark)
        #              'anchor': see above
        #              'topic': if itemtype is TOPIC, 'line' is not given,
        #                      instead we have 'topic'
        #              'url':  if itemtype is LINK, the line should be created
        #                      by "${link} ${line}", where 'link' is the URL
        #                      to link to, and 'line' is the rest of the line
        #                      (that isn't a URL)
        #              'url_quoteescaped': 'url' but with " escaped for use in
        #                                  <a href="$url_quoteescaped">
        ActionItems = [ ]
        for m in M.minutes:
            if m.itemtype != "ACTION": continue
            ActionItems.append(escape(m.line))
        repl['ActionItems'] = ActionItems
        # Format of ActionItems: It's just a very simple list of lines.
        # [line, line, line, ...]
        # line = (string of what it is)

        ActionItemsPerson = [ ]
        numberAssigned = 0
        for nick, items in self.iterActionItemsNick():
            thisNick = {'nick':escape(nick), 'items':[]}
            for m in items:
                numberAssigned += 1
                thisNick['items'].append(escape(m.line))
            if len(thisNick['items']) > 0:
                ActionItemsPerson.append(thisNick)
        # Work on the unassigned nicks.
        thisNick = {'nick':'UNASSIGNED', 'items':[]}
        for m in self.iterActionItemsUnassigned():
            thisNick['items'].append(escape(m.line))
        if len(thisNick['items']) > 1:
            ActionItemsPerson.append(thisNick)
        #if numberAssigned == 0:
        #    ActionItemsPerson = None
        repl['ActionItemsPerson'] = ActionItemsPerson
        # Format of ActionItemsPerson
        # ActionItemsPerson =
        #  [ {'nick':nick_of_person,
        #     'items': [item1, item2, item3, ...],
        #    },
        #   ...,
        #   ...,
        #    {'nick':'UNASSIGNED',
        #     'items': [item1, item2, item3, ...],
        #    }
        #  ]

        PeoplePresent = []
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append({'nick':escape(nick),
                                  'count':count})
        repl['PeoplePresent'] = PeoplePresent
        # Format of PeoplePresent
        # [{'nick':the_nick, 'count':count_of_lines_said},
        #  ...,
        #  ...,
        # ]

        return repl

    def get_template2(self, escape=lambda s: s):
        # let's make the data structure easier to use in the template
        repl = self.get_template(escape=escape)
        repl = {
        'time':           { 'start': repl['starttime'], 'end': repl['endtime'], 'timezone': repl['timeZone'] },
        'meeting':        { 'title': repl['pageTitle'], 'owner': repl['owner'], 'logs': repl['fullLogs'], 'logsFullURL': repl['fullLogsFullURL'] },
        'attendees':      [ person for person in repl['PeoplePresent'] ],
        'agenda':         [ { 'topic': item['topic'], 'notes': item['items'] } for item in repl['MeetingItems'] ],
        'actions':        [ action for action in repl['ActionItems'] ],
        'actions_person': [ { 'nick': attendee['nick'], 'actions': attendee['items'] } for attendee in repl['ActionItemsPerson'] ],
        'meetbot':        { 'version': repl['MeetBotVersion'], 'url': repl['MeetBotInfoURL'] },
        }
        return repl


class Template(_BaseWriter):
    """Format a notes file using the genshi templating engine

    Send an argument template=<filename> to specify which template to
    use.  If `template` begins in '+', then it is relative to the
    MeetBot source directory.  Included templates are:
      +template.html
      +template.txt

    Some examples of using these options are:
      writer_map['.txt|template=+template.html'] = writers.Template
      writer_map['.txt|template=/home/you/template.txt] = writers.Template

    If a template ends in .txt, parse with a text-based genshi
    templater.  Otherwise, parse with a HTML-based genshi templater.
    """
    def format(self, extension=None, template='+template.html'):
        repl = self.get_template2()

        # If `template` begins in '+', then it in relative to the
        # MeetBot source directory.
        if template[0] == '+':
            template = os.path.join(os.path.dirname(__file__), template[1:])
        # If we don't test here, it might fail in the try: block
        # below, then f.close() will fail and mask the original
        # exception
        if not os.access(template, os.F_OK):
            raise IOError('File not found: %s'%template)

        # Do we want to use a text template or HTML ?
        import genshi.template
        if template[-4:] in ('.txt', '.rst'):
            Template = genshi.template.NewTextTemplate   # plain text
        else:
            Template = genshi.template.MarkupTemplate    # HTML-like

        # Do the actual templating work
        try:
            f = open(template, 'r')
            tmpl = Template(f.read())
            stream = tmpl.generate(**repl)
        finally:
            f.close()

        return stream.render()


class _CSSmanager(object):
    _css_head = textwrap.dedent('''\
        <style type="text/css">
        %s
        </style>
        ''')
    def getCSS(self, name):
        cssfile = getattr(self.M.config, 'cssFile_'+name, '')
        if cssfile.lower() == 'none':
            # special string 'None' means no style at all
            return ''
        elif cssfile in ('', 'default'):
            # default CSS file
            css_fname = os.path.join(os.path.dirname(__file__),
                                     'css-'+name+'-default.css')
        else:
            css_fname = cssfile
        try:
            # Stylesheet specified
            if getattr(self.M.config, 'cssEmbed_'+name, True):
                # external stylesheet
                with open(css_fname) as f:
                    css = f.read()
                return self._css_head%css
            else:
                # linked stylesheet
                css_head = ('''<link rel="stylesheet" type="text/css" '''
                            '''href="%s">'''%cssfile)
                return css_head
        except Exception as exc:
            if not self.M.config.safeMode:
                raise
            import traceback
            traceback.print_exc()
            print("(exception above ignored, continuing)")
            try:
                css_fname = os.path.join(os.path.dirname(__file__),
                                         'css-'+name+'-default.css')
                css = open(css_fname).read()
                return self._css_head%css
            except:
                if not self.M.config.safeMode:
                    raise
                traceback.print_exc()
                return ''


class TextLog(_BaseWriter):
    def format(self, extension=None):
        M = self.M
        """Write raw text logs."""
        return "\n".join(M.lines)
    update_realtime = True


class HTMLlog1(_BaseWriter):
    def format(self, extension=None):
        """Write pretty HTML logs."""
        M = self.M
        # pygments lexing setup:
        # (pygments HTML formatter handles HTML escaping)
        import pygments
        from pygments.lexers import IrcLogsLexer
        from pygments.formatters import HtmlFormatter
        import pygments.token as token
        from pygments.lexer import bygroups
        # Don't do any encoding in this function with pygments.
        # That's only right before the i/o functions in the Config
        # object.
        formatter = HtmlFormatter(lineanchors='l',
                                  full=True, style=M.config.pygmentizeStyle,
                                  outencoding=self.M.config.output_codec)
        Lexer = IrcLogsLexer
        Lexer.tokens['msg'][1:1] = \
           [ # match:   #topic commands
            (r"(\#topic[ \t\f\v]*)(.*\n)",
             bygroups(token.Keyword, token.Generic.Heading), '#pop'),
             # match:   #command   (others)
            (r"(\#[^\s]+[ \t\f\v]*)(.*\n)",
             bygroups(token.Keyword, token.Generic.Strong), '#pop'),
           ]
        lexer = Lexer()
        #from rkddp.interact import interact ; interact()
        out = pygments.highlight("\n".join(M.lines), lexer, formatter)
        # Hack it to add "pre { white-space: pre-wrap; }", which make
        # it wrap the pygments html logs.  I think that in a newer
        # version of pygmetns, the "prestyles" HTMLFormatter option
        # would do this, but I want to maintain compatibility with
        # lenny.  Thus, I do these substitution hacks to add the
        # format in.  Thanks to a comment on the blog of Francis
        # Giannaros (http://francis.giannaros.org) for the suggestion
        # and instructions for how.
        out,n = re.subn(r"(\n\s*pre\s*\{[^}]+;\s*)(\})",
                        r"\1\n      white-space: pre-wrap;\2",
                        out, count=1)
        if n == 0:
            out = re.sub(r"(\n\s*</style>)",
                         r"\npre { white-space: pre-wrap; }\1",
                         out, count=1)
        return out


class HTMLlog2(_BaseWriter, _CSSmanager):
    def format(self, extension=None):
        """Write pretty HTML logs."""
        M = self.M
        lines = [ ]
        line_re = re.compile(r"""\s*
            (?P<time> \[?[0-9:\s]*\]?)\s*
            (?P<nick>\s+<[@+\s]?[^>]+>)\s*
            (?P<line>.*)
        """, re.VERBOSE)
        action_re = re.compile(r"""\s*
            (?P<time> \[?[0-9:\s]*\]?)\s*
            (?P<nick>\*\s+[@+\s]?[^\s]+)\s*
            (?P<line>.*)
        """,re.VERBOSE)
        command_re = re.compile(r"(#[^\s]+[ \t\f\v]*)(.*)")
        command_topic_re = re.compile(r"(#topic[ \t\f\v]*)(.*)")
        hilight_re = re.compile(r"([^\s]+:)( .*)")
        lineNumber = 0
        for l in M.lines:
            lineNumber += 1  # starts from 1
            # is it a regular line?
            m = line_re.match(l)
            if m:
                line = m.group('line')
                # Match #topic
                m2 = command_topic_re.match(line)
                if m2:
                    outline = ('<span class="topic">%s</span>'
                               '<span class="topicline">%s</span>' %
                               (html(m2.group(1)), html(m2.group(2))))
                # Match other #commands
                if not m2:
                    m2 = command_re.match(line)
                    if m2:
                        outline = ('<span class="cmd">%s</span>'
                                   '<span class="cmdline">%s</span>' %
                                   (html(m2.group(1)), html(m2.group(2))))
                # match hilights
                if not m2:
                    m2 = hilight_re.match(line)
                    if m2:
                        outline = ('<span class="hi">%s</span>' '%s' %
                                   (html(m2.group(1)), html(m2.group(2))))
                if not m2:
                    outline = html(line)
                lines.append('<a href="#l-%(lineno)s" name="l-%(lineno)s">'
                             '<span class="tm">%(time)s</span></a>'
                             '<span class="nk">%(nick)s</span> '
                             '%(line)s'%{'lineno':lineNumber,
                                         'time':html(m.group('time')),
                                         'nick':html(m.group('nick')),
                                         'line':outline,
                                         })
                continue
            m = action_re.match(l)
            # is it a action line?
            if m:
                lines.append('<a name="l-%(lineno)s"></a>'
                             '<span class="tm">%(time)s</span>'
                             '<span class="nka">%(nick)s</span> '
                             '<span class="ac">%(line)s</span>'%
                               {'lineno':lineNumber,
                                'time':html(m.group('time')),
                                'nick':html(m.group('nick')),
                                'line':html(m.group('line')),
                                })
                continue
            print(l)
            print(m.groups())
            print("**error**", l)

        css = self.getCSS(name='log')
        return html_template%{'pageTitle':"%s log"%html(M.channel),
                              #'body':"<br>\n".join(lines),
                              'body':"<pre>"+("\n".join(lines))+"</pre>",
                              'headExtra':css,
                              }

HTMLlog = HTMLlog2


html_template = textwrap.dedent('''\
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html>
    <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>%(pageTitle)s</title>
    %(headExtra)s
    </head>

    <body>
    %(body)s
    </body>
    </html>
    ''')


class HTML1(_BaseWriter):
    body = textwrap.dedent('''\
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
    <html>
    <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <title>%(pageTitle)s</title>
    </head>
    <body>
    <h1>%(pageTitle)s</h1>
    Meeting started by %(owner)s at %(starttime)s %(timeZone)s
    (<a href="%(fullLogs)s">full logs</a>)
    <br><br>

    <table border=1>
    %(MeetingItems)s
    </table>
    <br><br>

    Meeting ended at %(endtime)s %(timeZone)s
    (<a href="%(fullLogs)s">full logs</a>)
    <br><br>

    <b>Action items</b>
    <ol>
    %(ActionItems)s
    </ol>
    <br><br>

    <b>Action items, by person</b>
    <ol>
    %(ActionItemsPerson)s
    </ol>
    <br><br>

    <b>People present (lines said)</b>
    <ol>
    %(PeoplePresent)s
    </ol>
    <br><br>

    Generated by <a href="%(MeetBotInfoURL)s">MeetBot</a> %(MeetBotVersion)s
    </body>
    </html>
    ''')

    def format(self, extension=None):
        """Write the minutes summary."""
        M = self.M

        # Add all minute items to the table
        MeetingItems = [ ]
        for m in M.minutes:
            MeetingItems.append(m.html(M))
        MeetingItems = "\n".join(MeetingItems)

        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            ActionItems.append(wrapList("<li>%s</li>" % html(m.line), 2))
        if not ActionItems:
            ActionItems.append(indentItem("<li>(None)</li>", 2))
        ActionItems = "\n".join(ActionItems)

        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        for nick, items in self.iterActionItemsNick():
            headerPrinted = False
            for m in items:
                if not headerPrinted:
                    ActionItemsPerson.append(indentItem('<li>%s<ol type="a">' % html(nick), 2))
                    headerPrinted = True
                ActionItemsPerson.append(wrapList("<li>%s</li>" % html(m.line), 4))
            if headerPrinted:
                ActionItemsPerson.append(indentItem("</ol></li>", 2))
        if not ActionItemsPerson:
            ActionItemsPerson.append(indentItem("<li>(None)</li>", 2))
        else:
            # Unassigned items
            Unassigned = [ ]
            for m in self.iterActionItemsUnassigned():
                Unassigned.append(wrapList("<li>%s</li>" % html(m.line), 4))
            if Unassigned:
                Unassigned.insert(0, indentItem("<li><b>UNASSIGNED</b><ol>", 2))
                Unassigned.append(indentItem('</ol></li>', 2))
                ActionItemsPerson.extend(Unassigned)
        ActionItemsPerson = "\n".join(ActionItemsPerson)

        # People Attending
        PeoplePresent = [ ]
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append(indentItem('<li>%s (%d)</li>' % (html(nick), count), 2))
        PeoplePresent = "\n".join(PeoplePresent)

        # Actual formatting and replacement
        repl = self.replacements()
        repl.update({'MeetingItems':MeetingItems,
                     'ActionItems':ActionItems,
                     'ActionItemsPerson':ActionItemsPerson,
                     'PeoplePresent':PeoplePresent,
                     })
        body = self.body
        body = body%repl
        body = replaceWRAP(body)

        return body


class HTML2(_BaseWriter, _CSSmanager):
    """HTML formatter without tables."""
    def meetingItems(self):
        """Return the main 'Meeting minutes' block."""
        M = self.M

        # Add all minute items to the table
        MeetingItems = [ ]
        MeetingItems.append(self.heading('Meeting summary'))
        MeetingItems.append("<ol>")

        haveTopic = False
        haveSubtopic = False
        inSublist = False
        inSubsublist = False
        for m in M.minutes:
            item = "<li>"+m.html2(M)
            if m.itemtype == "TOPIC":
                if inSublist:
                    MeetingItems.append(indentItem("</ol>", 4))
                    inSublist = False
                if haveSubtopic:
                    if inSubsublist:
                        MeetingItems.append(indentItem("</ol>", 8))
                        inSubsublist = False
                    MeetingItems.append(indentItem("</li>", 6))
                    haveSubtopic = False
                if haveTopic:
                    MeetingItems.append(indentItem("</li><br>", 2))
                item = wrapList(item, 2)
                haveTopic = True
            elif m.itemtype == "SUBTOPIC":
                if not inSublist:
                    if not haveTopic:
                        MeetingItems.append(indentItem("<li>", 2))
                        haveTopic = True
                    MeetingItems.append(indentItem('<ol type="a">', 4))
                    inSublist = True
                item = wrapList(item, 6)
                haveSubtopic = True
            else:
                if not inSublist:
                    if not haveTopic:
                        MeetingItems.append(indentItem("<li>", 2))
                        haveTopic = True
                    MeetingItems.append(indentItem('<ol type="a">', 4))
                    inSublist = True
                if haveSubtopic:
                    if not inSubsublist:
                        MeetingItems.append(indentItem('<ol type="i">', 8))
                        inSubsublist = True
                    item = wrapList(item, 10)+"</li>"
                elif haveTopic: item = wrapList(item, 6)+"</li>"
                else:           item = wrapList(item, 2)+"</li>"
            MeetingItems.append(item)

        if haveSubtopic:
            if inSubsublist:
                MeetingItems.append(indentItem("</ol>", 8))
            MeetingItems.append(indentItem("</li>", 6))
        if inSublist:
            MeetingItems.append(indentItem("</ol>", 4))
        if haveTopic:
            MeetingItems.append(indentItem("</li>", 2))

        MeetingItems.append("</ol>")
        MeetingItems = "\n".join(MeetingItems)
        return MeetingItems

    def votes(self):
        M = self.M
        # Votes
        Votes = [ ]
        # reversed to show the oldest first
        for v, (vsum, vline) in list(M.votes.items()):
            voteLink = "%(fullLogs)s" % self.replacements()
            Votes.append(wrapList("<li><a href='%s#%d'>%s</a>" % (voteLink, vline, html(v)), 2))
            # differentiate denied votes somehow, strikethrough perhaps?
            Votes.append(wrapList("<ul><li>%s" % html(vsum), 4))
            if M.publicVoters[v]:
                publicVoters = ', '.join(M.publicVoters[v])
                Votes.append(wrapList("<ul><li>Voters: %s</li></ul>" % html(publicVoters), 6))
        if not Votes:
            return None
        Votes.insert(0, '<ol>')
        Votes.insert(0, self.heading('Vote results'))
        Votes.append(indentItem('</li></ul>', 4))
        Votes.append(indentItem('</li>', 2))
        Votes.append('</ol>')
        Votes = "\n".join(Votes)
        return Votes

    def actionItems(self):
        """Return the 'Action items' block."""
        M = self.M
        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            ActionItems.append(wrapList("<li>%s</li>" % html(m.line), 2))
        if not ActionItems:
            return None
        ActionItems.insert(0, '<ol>')
        ActionItems.insert(0, self.heading('Action items'))
        ActionItems.append('</ol>')
        ActionItems = "\n".join(ActionItems)
        return ActionItems

    def actionItemsPerson(self):
        """Return the 'Action items, by person' block."""
        M = self.M
        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        for nick, items in self.iterActionItemsNick():
            headerPrinted = False
            for m in items:
                if not headerPrinted:
                    ActionItemsPerson.append(indentItem('<li>%s<ol type="a">' % html(nick), 2))
                    headerPrinted = True
                ActionItemsPerson.append(wrapList("<li>%s</li>" % html(m.line), 4))
            if headerPrinted:
                ActionItemsPerson.append(indentItem('</ol></li>', 2))
        if not ActionItemsPerson:
            return None

        # Unassigned items
        Unassigned = [ ]
        for m in self.iterActionItemsUnassigned():
            Unassigned.append(wrapList("<li>%s</li>" % html(m.line), 4))
        if Unassigned:
            Unassigned.insert(0, indentItem("<li><b>UNASSIGNED</b><ol>", 2))
            Unassigned.append(indentItem('</ol></li>', 2))
            ActionItemsPerson.extend(Unassigned)

        ActionItemsPerson.insert(0, '<ol>')
        ActionItemsPerson.insert(0, self.heading('Action items, by person'))
        ActionItemsPerson.append('</ol>')
        ActionItemsPerson = "\n".join(ActionItemsPerson)
        return ActionItemsPerson

    def doneItems(self):
        M = self.M
        # Done Items
        DoneItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "DONE": continue
            #already escaped
            DoneItems.append(wrapList("<li>%s</li>" % html(m.line), 2))
        if not DoneItems:
            return None
        DoneItems.insert(0, '<ol>')
        DoneItems.insert(0, self.heading('Done items'))
        DoneItems.append('</ol>')
        DoneItems = "\n".join(DoneItems)
        return DoneItems

    def peoplePresent(self):
        """Return the 'People present' block."""
        # People Attending
        PeoplePresent = []
        PeoplePresent.append(self.heading('People present (lines said)'))
        PeoplePresent.append('<ol>')
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append(indentItem('<li>%s (%d)</li>' % (html(nick), count), 2))
        PeoplePresent.append('</ol>')
        PeoplePresent = "\n".join(PeoplePresent)
        return PeoplePresent

    def heading(self, name):
        return '<h3>%s</h3>' % name

    def format(self, extension=None):
        """Write the minutes summary."""
        M = self.M

        repl = self.replacements()

        body = [ ]
        body.append(textwrap.dedent("""\
            <h1>%(pageTitle)s</h1>
            <span class="details">
            Meeting started by %(owner)s at %(starttime)s %(timeZone)s
            (<a href="%(fullLogs)s">full logs</a>)</span>"""%repl))
        body.append(self.meetingItems())
        body.append(textwrap.dedent("""\
            <span class="details">
            Meeting ended at %(endtime)s %(timeZone)s
            (<a href="%(fullLogs)s">full logs</a>)</span>"""%repl))
        body.append(self.actionItems())
        body.append(self.actionItemsPerson())
        body.append(self.peoplePresent())
        body.append("""<span class="details">"""
                    """Generated by <a href="%(MeetBotInfoURL)s">MeetBot</a> """
                    """%(MeetBotVersion)s</span>"""%repl)
        body = [ b for b in body if b is not None ]
        body = "\n<br><br>\n\n\n\n".join(body)
        body = replaceWRAP(body)

        css = self.getCSS(name='minutes')
        repl.update({'body': body,
                     'headExtra': css,
                     })
        html = html_template % repl

        return html

HTML = HTML2


class ReST(_BaseWriter):
    body = textwrap.dedent("""\
    %(titleBlock)s
    %(pageTitle)s
    %(titleBlock)s


    sWRAPsMeeting started by %(owner)s at %(starttime)s %(timeZone)s
    (`full logs`_)eWRAPe

    .. _`full logs`: %(fullLogs)s




    Meeting summary
    ---------------
    %(MeetingItems)s

    Meeting ended at %(endtime)s %(timeZone)s (`full logs`_)

    .. _`full logs`: %(fullLogs)s




    Action items
    ------------
    %(ActionItems)s




    Action items, by person
    -----------------------
    %(ActionItemsPerson)s




    People present (lines said)
    ---------------------------
    %(PeoplePresent)s




    Generated by `MeetBot`_ %(MeetBotVersion)s

    .. _`MeetBot`: %(MeetBotInfoURL)s
    """)

    def format(self, extension=None):
        """Return a ReStructured Text minutes summary."""
        M = self.M
        # Agenda items
        MeetingItems = [ ]
        M.rst_urls = [ ]
        M.rst_refs = { }
        haveTopic = False
        for m in M.minutes:
            item = "* "+m.rst(M)
            if m.itemtype == "TOPIC":
                if haveTopic:
                    MeetingItems.append("")
                item = wrapList(item, 0)
                haveTopic = True
            else:
                if haveTopic: item = wrapList(item, 2)
                else:         item = wrapList(item, 0)
            MeetingItems.append(item)
        MeetingItems = "\n\n".join(MeetingItems)
        MeetingURLs = "\n".join(M.rst_urls)
        del M.rst_urls, M.rst_refs
        MeetingItems += "\n\n"+MeetingURLs

        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            #already escaped
            ActionItems.append(wrapList("* %s"%rst(m.line), 0))
        if not ActionItems:
            ActionItems.append("* (None)")
        ActionItems = "\n\n".join(ActionItems)

        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        for nick in sorted(list(M.attendees.keys()), key=lambda x: x.lower()):
            headerPrinted = False
            for m in M.minutes:
                # The hack below is needed because of pickling problems
                if m.itemtype != "ACTION": continue
                if not re.match(r'.*\b%s\b.*' % re.escape(nick), m.line, re.I):
                    continue
                if not headerPrinted:
                    ActionItemsPerson.append("* %s"%rst(nick))
                    headerPrinted = True
                ActionItemsPerson.append(wrapList("* %s"%rst(m.line), 2))
                m.assigned = True
        if not ActionItemsPerson:
            ActionItemsPerson.append("* (None)")
        else:
            # Unassigned items
            Unassigned = [ ]
            for m in M.minutes:
                if m.itemtype != "ACTION": continue
                if getattr(m, 'assigned', False): continue
                Unassigned.append(wrapList("* %s"%rst(m.line), 2))
            if Unassigned:
                Unassigned.insert(0, "* **UNASSIGNED**")
                ActionItemsPerson.extend(Unassigned)
        ActionItemsPerson = "\n\n".join(ActionItemsPerson)

        # People Attending
        PeoplePresent = [ ]
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append('* %s (%d)'%(rst(nick), count))
        PeoplePresent = "\n\n".join(PeoplePresent)

        # Actual formatting and replacement
        repl = self.replacements()
        repl.update({'titleBlock':('='*len(repl['pageTitle'])),
                     'MeetingItems':MeetingItems,
                     'ActionItems':ActionItems,
                     'ActionItemsPerson':ActionItemsPerson,
                     'PeoplePresent':PeoplePresent,
                     })
        body = self.body
        body = body%repl
        body = replaceWRAP(body)
        return body


class HTMLfromReST(_BaseWriter):
    def format(self, extension=None):
        M = self.M
        import docutils.core
        rst = ReST(M).format(extension)
        rstToHTML = docutils.core.publish_string(rst, writer_name='html',
                             settings_overrides={'file_insertion_enabled': 0,
                                                 'raw_enabled': 0,
                                'output_encoding':self.M.config.output_codec})
        return rstToHTML


class Text(_BaseWriter):
    def meetingItems(self):
        M = self.M
        # Agenda items
        MeetingItems = [ ]
        MeetingItems.append(self.heading('Meeting summary'))
        haveTopic = False
        for m in M.minutes:
            item = "* "+m.text(M)
            if m.itemtype == "TOPIC":
                if haveTopic:
                    MeetingItems.append("")
                item = wrapList(item, 0)
                haveTopic = True
            else:
                if haveTopic: item = wrapList(item, 2)
                else:         item = wrapList(item, 0)
            MeetingItems.append(item)
        MeetingItems = "\n".join(MeetingItems)
        return MeetingItems

    def actionItems(self):
        M = self.M
        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            #already escaped
            ActionItems.append(wrapList("* %s"%text(m.line), 0))
        if not ActionItems:
            return None
        ActionItems.insert(0, self.heading('Action items'))
        ActionItems = "\n".join(ActionItems)
        return ActionItems

    def actionItemsPerson(self):
        M = self.M
        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        for nick in sorted(list(M.attendees.keys()), key=lambda x: x.lower()):
            headerPrinted = False
            for m in M.minutes:
                # The hack below is needed because of pickling problems
                if m.itemtype != "ACTION": continue
                if not re.match(r'.*\b%s\b.*' % re.escape(nick), m.line, re.I):
                    continue
                if not headerPrinted:
                    ActionItemsPerson.append("* %s"%text(nick))
                    headerPrinted = True
                ActionItemsPerson.append(wrapList("* %s"%text(m.line), 2))
                m.assigned = True
        if not ActionItemsPerson:
            return None

        # Unassigned items
        Unassigned = [ ]
        for m in M.minutes:
            if m.itemtype != "ACTION": continue
            if getattr(m, 'assigned', False): continue
            Unassigned.append(wrapList("* %s"%text(m.line), 2))
        if Unassigned:
            Unassigned.insert(0, "* **UNASSIGNED**")
            ActionItemsPerson.extend(Unassigned)

        ActionItemsPerson.insert(0, self.heading('Action items, by person'))
        ActionItemsPerson = "\n".join(ActionItemsPerson)
        return ActionItemsPerson

    def peoplePresent(self):
        M = self.M
        # People Attending
        PeoplePresent = [ ]
        PeoplePresent.append(self.heading('People present (lines said)'))
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append('* %s (%d)'%(text(nick), count))
        PeoplePresent = "\n".join(PeoplePresent)
        return PeoplePresent

    def heading(self, name):
        return '%s\n%s\n'%(name, '-'*len(name))

    def format(self, extension=None):
        """Return a plain text minutes summary."""
        M = self.M

        # Actual formatting and replacement
        repl = self.replacements()
        repl.update({'titleBlock':('='*len(repl['pageTitle'])),
                     })

        body = [ ]
        body.append(textwrap.dedent("""\
            %(titleBlock)s
            %(pageTitle)s
            %(titleBlock)s


            sWRAPsMeeting started by %(owner)s at %(starttime)s
            %(timeZone)s.  The full logs are available at
            %(fullLogsFullURL)seWRAPe"""%repl))
        body.append(self.meetingItems())
        body.append(textwrap.dedent("""\
            Meeting ended at %(endtime)s %(timeZone)s."""%repl))
        body.append(self.actionItems())
        body.append(self.actionItemsPerson())
        body.append(self.peoplePresent())
        body.append(textwrap.dedent("""\
            Generated by MeetBot %(MeetBotVersion)s (%(MeetBotInfoURL)s)"""%repl))
        body = [ b for b in body if b is not None ]
        body = "\n\n\n\n".join(body)
        body = replaceWRAP(body)

        return body


class MediaWiki(_BaseWriter):
    """Outputs MediaWiki formats."""
    def meetingItems(self):
        M = self.M
        # Agenda items
        MeetingItems = [ ]
        MeetingItems.append(self.heading('Meeting summary'))
        haveTopic = False
        for m in M.minutes:
            item = "* "+m.mw(M)
            if m.itemtype == "TOPIC":
                if haveTopic:
                    MeetingItems.append("")
                haveTopic = True
            else:
                if haveTopic: item = "*"+item
            MeetingItems.append(item)
        MeetingItems = "\n".join(MeetingItems)
        return MeetingItems

    def actionItems(self):
        M = self.M
        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            #already escaped
            ActionItems.append("* %s"%mw(m.line))
        if not ActionItems:
            return None
        ActionItems.insert(0, self.heading('Action items'))
        ActionItems = "\n".join(ActionItems)
        return ActionItems

    def actionItemsPerson(self):
        M = self.M
        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        numberAssigned = 0
        for nick in sorted(list(M.attendees.keys()), key=lambda x: x.lower()):
            headerPrinted = False
            for m in M.minutes:
                # The hack below is needed because of pickling problems
                if m.itemtype != "ACTION": continue
                if not re.match(r'.*\b%s\b.*' % re.escape(nick), m.line, re.I):
                    continue
                if not headerPrinted:
                    ActionItemsPerson.append("* %s"%mw(nick))
                    headerPrinted = True
                ActionItemsPerson.append("** %s"%mw(m.line))
                numberAssigned += 1
                m.assigned = True
        if not ActionItemsPerson:
            return None

        # Unassigned items
        Unassigned = [ ]
        for m in M.minutes:
            if m.itemtype != "ACTION": continue
            if getattr(m, 'assigned', False): continue
            Unassigned.append("** %s"%mw(m.line))
        if Unassigned:
            Unassigned.insert(0, "* **UNASSIGNED**")
            ActionItemsPerson.extend(Unassigned)

        ActionItemsPerson.insert(0, self.heading('Action items, by person'))
        ActionItemsPerson = "\n".join(ActionItemsPerson)
        return ActionItemsPerson

    def peoplePresent(self):
        M = self.M
        # People Attending
        PeoplePresent = [ ]
        PeoplePresent.append(self.heading('People present (lines said)'))
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append('* %s (%d)'%(mw(nick), count))
        PeoplePresent = "\n".join(PeoplePresent)
        return PeoplePresent

    def heading(self, name, level=1):
        return '%s %s %s\n'%('='*(level+1), name, '='*(level+1))


    body_start = textwrap.dedent("""\
            %(pageTitleHeading)s

            sWRAPsMeeting started by %(owner)s at %(starttime)s
            %(timeZone)s.  The full logs are available at
            %(fullLogsFullURL)seWRAPe""")
    def format(self, extension=None):
        """Return a MediaWiki formatted minutes summary."""
        M = self.M

        # Actual formatting and replacement
        repl = self.replacements()
        repl.update({'titleBlock':('='*len(repl['pageTitle'])),
                     'pageTitleHeading':self.heading(repl['pageTitle'],level=0)
                     })

        body = [ ]
        body.append(self.body_start%repl)
        body.append(self.meetingItems())
        body.append(textwrap.dedent("""\
            Meeting ended at %(endtime)s %(timeZone)s."""%repl))
        body.append(self.actionItems())
        body.append(self.actionItemsPerson())
        body.append(self.peoplePresent())
        body.append(textwrap.dedent("""\
            Generated by MeetBot %(MeetBotVersion)s (%(MeetBotInfoURL)s)"""%repl))
        body = [ b for b in body if b is not None ]
        body = "\n\n\n\n".join(body)
        body = replaceWRAP(body)

        return body


class PmWiki(MediaWiki, object):
    def heading(self, name, level=1):
        return '%s %s\n'%('!'*(level+1), name)
    def replacements(self):
        #repl = super(PmWiki, self).replacements(self) # fails, type checking
        repl = MediaWiki.replacements.__func__(self)
        repl['pageTitleHeading'] = self.heading(repl['pageTitle'],level=0)
        return repl


class Moin(_BaseWriter):
    """Outputs MoinMoin formats."""
    def meetingItems(self):
        M = self.M
        # Agenda items
        MeetingItems = [ ]
        MeetingItems.append(self.heading('Meeting summary'))
        haveTopic = False
        haveSubtopic = False
        for m in M.minutes:
            item = m.moin(M)
            if m.itemtype == "TOPIC":
                if haveSubtopic:
                    haveSubtopic = False
                if haveTopic:
                    MeetingItems.append("")
                haveTopic = True
            elif m.itemtype == "SUBTOPIC":
                item = " * "+item
                haveSubtopic = True
            else:
                if not haveTopic:
                    haveTopic = True
                if haveSubtopic: item = "  * "+item
                else:            item = " * "+item
            MeetingItems.append(item)
        MeetingItems = "\n".join(MeetingItems)
        return MeetingItems

    def fullLog(self):
        M = self.M
        Lines = [ ]
        Lines.append(self.heading('Full log'))
        for l in M.lines:
            Lines.append(' '+l)
        Lines = "\n\n".join(Lines)
        return Lines

    def votes(self):
        M = self.M
        # Votes
        Votes = [ ]
        # reversed to show the oldest first
        for v, (vsum, vline) in list(M.votes.items()):
            voteLink = "%(fullLogsFullURL)s" % self.replacements()
            Votes.append(" * [[%s#%d|%s]]" % (voteLink, vline, v))
            # differentiate denied votes somehow, strikethrough perhaps?
            Votes.append("  * " + vsum)
            if M.publicVoters[v]:
                publicVoters = ', '.join(M.publicVoters[v])
                Votes.append("   * Voters: " + publicVoters)
        if not Votes:
            return None
        Votes.insert(0, self.heading('Vote results'))
        Votes = "\n".join(Votes)
        return Votes

    def actionItems(self):
        M = self.M
        # Action Items
        ActionItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "ACTION": continue
            #already escaped
            ActionItems.append(" * %s"%moin(m.line))
        if not ActionItems:
            return None
        ActionItems.insert(0, self.heading('Action items'))
        ActionItems = "\n".join(ActionItems)
        return ActionItems

    def actionItemsPerson(self):
        M = self.M
        # Action Items, by person (This could be made lots more efficient)
        ActionItemsPerson = [ ]
        for nick in sorted(list(M.attendees.keys()), key=lambda x: x.lower()):
            headerPrinted = False
            for m in M.minutes:
                # The hack below is needed because of pickling problems
                if m.itemtype != "ACTION": continue
                if not re.match(r'.*\b%s\b.*' % re.escape(nick), m.line, re.I):
                    continue
                if not headerPrinted:
                    ActionItemsPerson.append(" * %s"%moin(nick))
                    headerPrinted = True
                ActionItemsPerson.append("  * %s"%moin(m.line))
                m.assigned = True
        if not ActionItemsPerson:
            return None

        # Unassigned items
        Unassigned = [ ]
        for m in M.minutes:
            if m.itemtype != "ACTION": continue
            if getattr(m, 'assigned', False): continue
            Unassigned.append("  * %s"%moin(m.line))
        if Unassigned:
            Unassigned.insert(0, " * **UNASSIGNED**")
            ActionItemsPerson.extend(Unassigned)

        ActionItemsPerson.insert(0, self.heading('Action items, by person'))
        ActionItemsPerson = "\n".join(ActionItemsPerson)
        return ActionItemsPerson

    def doneItems(self):
        M = self.M
        # Done Items
        DoneItems = [ ]
        for m in M.minutes:
            # The hack below is needed because of pickling problems
            if m.itemtype != "DONE": continue
            #already escaped
            DoneItems.append(" * %s"%moin(m.line))
        if not DoneItems:
            return None
        DoneItems.insert(0, self.heading('Done items'))
        DoneItems = "\n".join(DoneItems)
        return DoneItems

    def peoplePresent(self):
        M = self.M
        # People Attending
        PeoplePresent = [ ]
        PeoplePresent.append(self.heading('People present (lines said)'))
        # sort by number of lines spoken
        for nick, count in self.iterNickCounts():
            PeoplePresent.append(' * %s (%d)'%(moin(nick), count))
        PeoplePresent = "\n".join(PeoplePresent)
        return PeoplePresent

    def heading(self, name, level=1):
        return '%s %s %s\n'%('='*(level+1), name, '='*(level+1))


    body_start = textwrap.dedent("""\
            == Meeting information ==

             * %(pageTitleHeading)s, started by %(owner)s, %(startdate)s at %(starttimeshort)s &mdash; %(endtimeshort)s %(timeZone)s.
             * Full logs at %(fullLogsFullURL)s""")
    def format(self, extension=None):
        """Return a MoinMoin formatted minutes summary."""
        M = self.M

        # Actual formatting and replacement
        repl = self.replacements()
        repl.update({'titleBlock':('='*len(repl['pageTitle'])),
                     'pageTitleHeading':(repl['pageTitle'])
                     })

        body = [ ]
        body.append(self.body_start%repl)
        body.append(self.meetingItems())
        body.append(self.votes())
        body.append(self.actionItemsPerson())
        body.append(self.doneItems())
        body.append(self.peoplePresent())
        if M.config.moinFullLogs:
            body.append(self.fullLog())
        body.append(textwrap.dedent("""\
            Generated by MeetBot %(MeetBotVersion)s (%(MeetBotInfoURL)s)"""%repl))
        body = [ b for b in body if b is not None ]
        body = "\n\n\n\n".join(body)
        body = replaceWRAP(body)

        return body
