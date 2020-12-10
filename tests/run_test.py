import os, sys
#import re
import tempfile
import unittest

os.environ['MEETBOT_RUNNING_TESTS'] = '1'
from .. import meeting
from .. import writers

running_tests = True

def process_meeting(contents, extraConfig={}):
    return meeting.process_meeting(contents=contents,
                                channel="#none",  filename='/dev/null',
                                dontSave=True, safeMode=False,
                                extraConfig=extraConfig)


class MeetBotTest(unittest.TestCase):
    def test_replay(self):
        """Replay of a meeting, using __meeting__.
        """
        sys.argv[1:] = ["replay", "test-script-1.log.txt"]
        sys.path.insert(0, "..")
        try:
            exec(compile(open("../meeting.py").read(), "../meeting.py", 'exec'), {})
        finally:
            del sys.path[0]

    def test_supybottests(self):
        """Test by sending input to Supybot, check responses.

        Uses the external supybot-test command.  Unfortunantly, that
        doesn't have a useful status code, so I need to parse the
        output.
        """
        os.symlink("..", "MeetBot")
        try:
            output = os.popen("supybot-test ./MeetBot 2>&1").read()
            print(output)
            assert 'FAILED' not in output, "Supybot-based tests failed."
            assert '\nOK\n'     in output, "Supybot-based tests failed."
        finally:
            os.unlink("MeetBot")

    trivial_contents = """
    10:10:10 <x> #startmeeting
    10:10:10 <x> blah
    10:10:10 <x> #endmeeting
    """

    full_writer_map = {
        '.log.txt':     writers.TextLog,
        '.log.1.html':  writers.HTMLlog1,
        '.log.html':    writers.HTMLlog2,
        '.1.html':      writers.HTML1,
        '.html':        writers.HTML2,
        '.rst':         writers.ReST,
        '.rst.html':    writers.HTMLfromReST,
        '.txt':         writers.Text,
        '.mw':          writers.MediaWiki,
        '.pmw':         writers.PmWiki,
        '.tmp.txt|template=+template.txt':   writers.Template,
        '.tmp.html|template=+template.html': writers.Template,
        }

    def M_trivial(self, contents=None, extraConfig={}):
        if contents is None:
            contents = self.trivial_contents
        return process_meeting(contents=contents,
                               extraConfig=extraConfig)

    def test_script_1(self):
        process_meeting(contents=file('test-script-1.log.txt').read(),
                        extraConfig={'writer_map':self.full_writer_map})
    #def test_script_3(self):
    #   process_meeting(contents=file('test-script-3.log.txt').read(),
    #                   extraConfig={'writer_map':self.full_writer_map})

    all_commands_test_contents = """
    10:10:10 <x> #startmeeting
    10:10:10 <x> #topic h6k4orkac
    10:10:10 <x> #info blaoulrao
    10:10:10 <x> #idea alrkkcao4
    10:10:10 <x> #help ntoircoa5
    10:10:10 <x> #link http://bnatorkcao.net kroacaonteu
    10:10:10 <x> http://jrotjkor.net krotroun
    10:10:10 <x> #action xrceoukrc
    10:10:10 <x> #nick okbtrokr

    # Should not appear in non-log output
    10:10:10 <x> #idea ckmorkont
    10:10:10 <x> #undo

    # Assert that chairs can change the topic, and non-chairs can't.
    10:10:10 <x> #chair y
    10:10:10 <y> #topic topic_doeschange
    10:10:10 <z> #topic topic_doesntchange
    10:10:10 <x> #unchair y
    10:10:10 <y> #topic topic_doesnt2change

    10:10:10 <x> #endmeeting
    """
    def test_contents_test2(self):
        """Ensure that certain input lines do appear in the output.

        This test ensures that the input to certain commands does
        appear in the output.
        """
        M = process_meeting(contents=self.all_commands_test_contents,
                            extraConfig={'writer_map':self.full_writer_map})
        results = M.save()
        for name, output in list(results.items()):
            self.assertTrue('h6k4orkac' in output, "Topic failed for %s"%name)
            self.assertTrue('blaoulrao' in output, "Info failed for %s"%name)
            self.assertTrue('alrkkcao4' in output, "Idea failed for %s"%name)
            self.assertTrue('ntoircoa5' in output, "Help failed for %s"%name)
            self.assertTrue('http://bnatorkcao.net' in output,
                                                  "Link(1) failed for %s"%name)
            self.assertTrue('kroacaonteu' in output, "Link(2) failed for %s"%name)
            self.assertTrue('http://jrotjkor.net' in output,
                                        "Link detection(1) failed for %s"%name)
            self.assertTrue('krotroun' in output,
                                        "Link detection(2) failed for %s"%name)
            self.assertTrue('xrceoukrc' in output, "Action failed for %s"%name)
            self.assertTrue('okbtrokr' in output, "Nick failed for %s"%name)

            # Things which should only appear or not appear in the
            # notes (not the logs):
            if 'log' not in name:
                self.assertTrue( 'ckmorkont' not in output,
                              "Undo failed for %s"%name)
                self.assertTrue('topic_doeschange' in output,
                             "Chair changing topic failed for %s"%name)
                self.assertTrue('topic_doesntchange' not in output,
                             "Non-chair not changing topic failed for %s"%name)
                self.assertTrue('topic_doesnt2change' not in output,
                            "Un-chaired was able to chang topic for %s"%name)

    #def test_contents_test(self):
    #    contents = open('test-script-3.log.txt').read()
    #    M = process_meeting(contents=file('test-script-3.log.txt').read(),
    #                        extraConfig={'writer_map':self.full_writer_map})
    #    results = M.save()
    #    for line in contents.split('\n'):
    #        m = re.search(r'#(\w+)\s+(.*)', line)
    #        if not m:
    #            continue
    #        type_ = m.group(1)
    #        text = m.group(2)
    #        text = re.sub('[^\w]+', '', text).lower()
    #
    #        m2 = re.search(t2, re.sub(r'[^\w\n]', '', results['.txt']))
    #        import fitz.interactnow
    #        print m.groups()

    def t_css(self):
        """Runs all CSS-related tests."""
        self.test_css_embed()
        self.test_css_noembed()
        self.test_css_file_embed()
        self.test_css_file()
        self.test_css_none()
    def test_css_embed(self):
        extraConfig={ }
        results = self.M_trivial(extraConfig={}).save()
        self.assertTrue('<link rel="stylesheet" ' not in results['.html'])
        self.assertTrue('body {'                      in results['.html'])
        self.assertTrue('<link rel="stylesheet" ' not in results['.log.html'])
        self.assertTrue('body {'                      in results['.log.html'])
    def test_css_noembed(self):
        extraConfig={'cssEmbed_minutes':False,
                     'cssEmbed_log':False,}
        M = self.M_trivial(extraConfig=extraConfig)
        results = M.save()
        self.assertTrue('<link rel="stylesheet" '     in results['.html'])
        self.assertTrue('body {'                  not in results['.html'])
        self.assertTrue('<link rel="stylesheet" '     in results['.log.html'])
        self.assertTrue('body {'                  not in results['.log.html'])
    def test_css_file(self):
        tmpf = tempfile.NamedTemporaryFile()
        magic_string = '546uorck6o45tuo6'
        tmpf.write(magic_string)
        tmpf.flush()
        extraConfig={'cssFile_minutes':  tmpf.name,
                     'cssFile_log':      tmpf.name,}
        M = self.M_trivial(extraConfig=extraConfig)
        results = M.save()
        self.assertTrue('<link rel="stylesheet" ' not in results['.html'])
        self.assertTrue(magic_string                  in results['.html'])
        self.assertTrue('<link rel="stylesheet" ' not in results['.log.html'])
        self.assertTrue(magic_string                  in results['.log.html'])
    def test_css_file_embed(self):
        tmpf = tempfile.NamedTemporaryFile()
        magic_string = '546uorck6o45tuo6'
        tmpf.write(magic_string)
        tmpf.flush()
        extraConfig={'cssFile_minutes':  tmpf.name,
                     'cssFile_log':      tmpf.name,
                     'cssEmbed_minutes': False,
                     'cssEmbed_log':     False,}
        M = self.M_trivial(extraConfig=extraConfig)
        results = M.save()
        self.assertTrue('<link rel="stylesheet" '     in results['.html'])
        self.assertTrue(tmpf.name                     in results['.html'])
        self.assertTrue('<link rel="stylesheet" '     in results['.log.html'])
        self.assertTrue(tmpf.name                     in results['.log.html'])
    def test_css_none(self):
        tmpf = tempfile.NamedTemporaryFile()
        magic_string = '546uorck6o45tuo6'
        tmpf.write(magic_string)
        tmpf.flush()
        extraConfig={'cssFile_minutes':  'none',
                     'cssFile_log':      'none',}
        M = self.M_trivial(extraConfig=extraConfig)
        results = M.save()
        self.assertTrue('<link rel="stylesheet" ' not in results['.html'])
        self.assertTrue('<style type="text/css" ' not in results['.html'])
        self.assertTrue('<link rel="stylesheet" ' not in results['.log.html'])
        self.assertTrue('<style type="text/css" ' not in results['.log.html'])

    def test_filenamevars(self):
        def getM(fnamepattern):
            M = meeting.Meeting(channel='somechannel',
                                network='somenetwork',
                                owner='nobody',
                     extraConfig={'filenamePattern':fnamepattern})
            M.addline('nobody', '#startmeeting')
            return M
        # Test the %(channel)s and %(network)s commands in Supybot.
        M = getM('%(channel)s-%(network)s')
        assert M.config.filename().endswith('somechannel-somenetwork'), \
               "Filename not as expected: "+M.config.filename()
        # Test dates in filenames
        M = getM('%(channel)s-%%F')
        import time
        assert M.config.filename().endswith(time.strftime('somechannel-%F')),\
               "Filename not as expected: "+M.config.filename()
        # Test #meetingname in filenames
        M = getM('%(channel)s-%(meetingname)s')
        M.addline('nobody', '#meetingname blah1234')
        assert M.config.filename().endswith('somechannel-blah1234'),\
               "Filename not as expected: "+M.config.filename()


if __name__ == '__main__':
    os.chdir(os.path.join(os.path.dirname(__file__), '.'))
    if len(sys.argv) <= 1:
        unittest.main()
    else:
        for testname in sys.argv[1:]:
            print(testname)
            if hasattr(MeetBotTest, testname):
                MeetBotTest(methodName=testname).debug()
            else:
                MeetBotTest(methodName='test_'+testname).debug()
