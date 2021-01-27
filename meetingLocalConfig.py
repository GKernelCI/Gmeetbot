import re
from . import writers

class Config(object):
    logFileDir = '/var/www/meetingology/logs/'
    filenamePattern = '%(channel)s/%%Y/%(channel)s.%%F-%%H.%%M'

    logUrlPrefix = 'https://ubottu.com/meetingology/logs/'
    MeetBotInfoURL = 'https://wiki.ubuntu.com/meetingology'
    moinFullLogs = True
    writer_map = {
        '.log.html': writers.HTMLlog,
        #'.1.html': writers.HTML,
        '.html': writers.HTML2,
        #'.rst': writers.ReST,
        #'.txt': writers.Text,
        #'.rst.html': writers.HTMLfromReST,
        '.moin.txt': writers.Moin,
        #'.mw.txt': writers.MediaWiki,
    }
    command_RE = re.compile(r'^[#\[](\w+)\]?(?:\s+(.*?)|)\s*$')
