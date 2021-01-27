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

import sys, re, types
import supybot.conf as conf
import supybot.registry as registry

from importlib import reload
from . import meeting
from . import writers

reload(meeting)
reload(writers)

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('MeetBot', True)


MeetBot = conf.registerPlugin('MeetBot')
use_supybot_config = conf.registerGlobalValue(MeetBot, 'enableSupybotBasedConfig',
    registry.Boolean(False, """Enable configuration via the Supybot config
                            mechanism."""))


class WriterMap(registry.SpaceSeparatedListOfStrings):
    """List of output formats to write.  This is a space-separated
    list of 'WriterName:.ext' pairs.  WriterName must be from the
    writers.py module, '.ext' must be an extension starting with a dot.
    """
    def set(self, s):
        s = s.split()
        writer_map = { }
        for writer in s:
            writer, ext = writer.split(':')
            if not hasattr(writers, writer):
                raise ValueError("Writer name not found: '%s'" % writer)
            if len(ext) < 2 or ext[0] != '.':
                raise ValueError("Extension must start with '.' and have "
                                 "at least one more character.")
            writer_map[ext] = getattr(writers, writer)
        self.setValue(writer_map)
    def setValue(self, v):
        self.value = v
    def __str__(self):
        writer_list = [ ]
        for ext, writer in list(self.value.items()):
            writer_list.append("%s:%s" % (writer.__name__, ext))
        return " ".join(writer_list)


class Regex(registry.String):
    def set(self, s):
        regex = re.compile(r'%s' % s)
        self.setValue(regex)
    def setValue(self, v):
        self.value = v
    def __str__(self):
        return self.value.pattern


class SupybotConfigProxy(object):
    def __init__(self, *args, **kwargs):
        """Do the regular default configuration, and sta"""
        OriginalConfig = self.__OriginalConfig
        self.__C = OriginalConfig(*args, **kwargs)

    def __getattr__(self, attrname):
        """Try to get the value from the Supybot registry.  If it's in
        the registry, return it.  If it's not, then proxy it to th.
        """
        if attrname in settable_attributes:
            value = self.__C.M._registryValue(attrname,
                                              channel=self.__C.M.channel)
            if not (isinstance(value, str) or
                    (sys.version_info < (3,0) and isinstance(value, unicode))):
                return value
            # '.' is used to mean "this is not set, use the default
            # value from the python config class.
            if value != '.':
                value = value.replace('\\n', '\n')
                return value
        # We don't have this value in the registry.  So, proxy it to
        # the normal config object.  This is also the path that all
        # functions take.
        value = getattr(self.__C, attrname)
        # If the value is an instance method, we need to re-bind it to
        # the new config class so that we will get the data values
        # defined in Supybot (otherwise attribute lookups in the
        # method will bypass the Supybot proxy and just use default
        # values).  This will slow things down a little bit, but
        # that's just the cost of doing business.
        if hasattr(value, '__func__'):
            if sys.version_info < (3,0):
                return types.MethodType(value.__func__, self, value.__self__.__class__)
            return types.MethodType(value.__func__, self)
        return value


def is_supybotconfig_enabled(OriginalConfig):
    return (use_supybot_config() and
            not getattr(OriginalConfig, 'dontBotConfig', False))


settable_attributes = [ ]
def setup_config(OriginalConfig):
    # Set all desired variables in the default Config class
    # as Supybot registry variables.
    for attrname in dir(OriginalConfig):
        # Don't configure attributes starting with '_'
        if attrname[0] == '_':
            continue
        attr = getattr(OriginalConfig, attrname)
        # Only configure attributes that can be handled through Supybot.
        if isinstance(attr, str) or \
                (sys.version_info < (3,0) and isinstance(attr, unicode)):
            attr = attr.replace('\n', '\\n')
            attrtype = registry.String
        elif isinstance(attr, bool):
            attrtype = registry.Boolean
        elif isinstance(attr, list):
            attrtype = registry.SpaceSeparatedListOfStrings
        elif attrname == 'writer_map':
            attr = OriginalConfig.writer_map
            attrtype = WriterMap
        elif attrname.endswith('_RE'):
            attrtype = Regex
        else:
            continue
        conf.registerChannelValue(MeetBot, attrname, attrtype(attr, ''))
        settable_attributes.append(attrname)


def get_config_proxy(OriginalConfig):
    # Here is where the real proxying occurs.
    SupybotConfigProxy._SupybotConfigProxy__OriginalConfig = OriginalConfig
    return SupybotConfigProxy


if is_supybotconfig_enabled(meeting.Config):
    setup_config(meeting.Config)


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
