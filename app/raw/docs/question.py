#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Document wrappers for LegCo questions (and replies)
"""
import logging
import lxml
from lxml import etree
import lxml.html
from lxml.html.clean import clean_html, Cleaner
import re
from lxml.html import HTMLParser
import urllib2
from urllib2 import HTTPError
from ..scraper.settings import USER_AGENT

logger = logging.getLogger('legcowatch-docs')

class CouncilQuestion(object):
    """
    Object representing the Council Question document (actually the reply as well).  
    Some can be used to check against RawCouncilQuestion object
    This class parses the document source, and has potential to give out below elements:
    
    Urgent or not
    Question_number
    Subject
    Date_of_meeting
    Time_of_reply
    Asker
    Replier(s)
    Question_content
    Reply_content
    """
    def __init__(self, uid, date, urgent, oral, src, link,*args, **kwargs):
        logger.debug(u'** Parsing question {}'.format(uid))
        self.uid = uid
        if uid[-1] == 'e':
            self.english = True
        else:
            self.english = False
        self.src =src
        self.date = date
        self.urgent = urgent
        self.oral = oral
        self.link = link
        
        self.tree = None
        self.tree_content = None
        self.question_title = None
        #self.question_number =None
        self.question_content = None
        self.asker = None
        self.reply_content = None
        self.repliers = None
        self._load()
        self._parse()
        
    def __repr__(self):
        return u'<CouncilQuestion: {}>'.format(self.uid)
    
    def _load(self):
        """
        Load the ElementTree from the source
        """
        #q_object = raw.models.raw.RawCouncilQuestion.objects.get_by_uid(self.uid)
        ## Some questions does not have a reply page/reply is in hansard
        #if q_object.full_local_filename():
        #    with open(q_object.full_local_filename()) as f:
        #        htm = f.read() # htm is an str object
        
        # Get rid of '\xa0'
        #zero_width_joiners = u'\u200d'
        #self.src = self.src.replace(zero_width_joiners, u'')
        
        htm = self.src
        
        ## seems that the page used 'hkscs'(香港增補字符集) as charset
        """
        #get encoding
        try:
            req = urllib2.Request(self.link, headers={ 'User-Agent': USER_AGENT })
            html = urllib2.urlopen(req).read()
        except HTTPError:
            logger.warn('Cannot get open reply link for question {]'.format(self.uid))
        
        if html:
            content_type_re = ur'(?s).*content-type" content="(?P<content>.*?)"'
            content_type = re.match(content_type_re,html).group('content')
            charset = content_type.split('=')[1]
            print('Encoding detected: {}'.format(charset))
        else:
            logger.warn('Cannot get charset from reply link. Guess instead.')
            charset = 'utf-8' if self.english else 'BIG5' # sometimes not working for Chinese
        """
        #TESEING
        #htm=html
        #ENDTESTING
        
        
        # Use the lxml cleaner
        if htm:
            # Assume 香港增補字符集hkscs is used
            htm = htm.decode('hkscs')
            cleaner = Cleaner()
            parser = HTMLParser(encoding='utf-8')
            # Finally, load the cleaned string to an ElementTree
            self.tree = cleaner.clean_html(lxml.html.fromstring(htm, parser=parser))
            self.src = htm
        else:
            self.tree = None
        
    def _parse(self):
        #only the pressrelease part is needed
        try:
            main_tree = self.tree.xpath('id("pressrelease")')[0]
        except IndexError:
            logger.warn(u'HTML of question {} does not have a "pressrelease" field'.format(self.uid))
        # break the main tree into 2 parts: title and main body
        #1. title string, no newlines
        #e.g. 'LCQ17: Babies born in Hong Kong to mainland women'
        title_str = main_tree.text.strip()
        #2. main body, including question header, question content and reply
        #e.g. 'Following is a question by the Hon Yeung Sum and a written reply...'
        main_body = main_tree.xpath('p[1]')[0]
        main_body_str = main_body.text_content() # do not strip, keep the format
        
        #=========================================================================#
        #TODO: there are a lot of different encodings of colons, e.g.
        #(:,：,︰) - with unicodes \u3A, \uFF1A, \uFE30 respectively (may be more)
        #and can have with whitespace ahead of them (not need to care for behind)
        #sometimes the colon is missing...
        #Find a way to handle them concisely!
        #Currently, ur'\s?(:|：|︰)' is used to deal with them - but be cautious! 
        #=========================================================================#
        
        # Parse the title
        #title_re_e = ur'LC(.*)?Q(?P<number>\d*)?:\s*(?P<subject>.+)' #e.g. 'LCQ17: Babies born in Hong Kong to mainland women'
        #title_re_c = ur'立法會(急切質詢)?(?P<number>\S*題)?：\s*(?P<subject>.+)' #e.g. '立法會五題：旅發局浮薪程式'
        
        # Simpler, no question number
        #note that the complete title is available in html header
        title_re_e = ur'(?s).+\s?(:|：|︰)\s*(?P<subject>.+)' 
        title_re_c = ur'(?s).+\s?(:|：|︰)\s*(?P<subject>.+)'
        #notice the difference of colon (half- and full-width) in the above regex
        print(u'Title str: {}'.format(title_str))
        match_pattern = title_re_e if self.english else title_re_c
        match_title = re.match(match_pattern, title_str)
        if match_title:
            self.question_title = match_title.group('subject')
            print(u'Title: {}'.format(self.question_title))
            # We choose not to deal with numbers, since they are better handled by scraper
            #if match_title['number']:
            #    self.question_number = match_title.group('number')
            #else:
            #    self.question_number = '0'
        else:
            logger.warn('Cannot match title for question {}'.format(self.uid))
            
        # Parse the main body - 3 parts
        #1. header of question, including date, asker and replier(s)
        header_re_e = ur'(?P<header>.+)Question(s?)\s?(:|：|︰)'
        header_re_c = ur'(?P<header>.+)問題\s?(:|：|︰)'
        match_pattern = header_re_e if self.english else header_re_c
        match_header = re.match(match_pattern, main_body_str.strip()) #strip here make it easier - get rid of newline
        header_str = None
        if match_header:
            header_str = match_header.group('header')
            print(u'header str:{}'.format(header_str))
        else:
            logger.warn('Cannot match header for question {}'.format(self.uid))
        
        #retrieve asker and replier(s) from header
        if header_str: #no need to try if no header
            #more complicated, need to pick regex based on urgent or not
            #there are two formats, need to separately match the 2 cases
            if self.urgent:
                asker_re_e1 = ur'(?s)(.*) by (?P<asker>.+) under (.*) reply by (?P<repliers>.+), (in|at) the Legislative Council'
                asker_re_e2 = ur'(?s)(.*) reply by (?P<repliers>.+), to a question by (?P<asker>.+) under (.*) (in|at) the Legislative Council'
                asker_re_c1 = ur'(?s)(.*)以下(為|是)今日（(?P<date>.+)）在立法會會議上(?P<asker>.+)根據(.*)(和|及)(?P<repliers>.+)的(.*?)(答|回)覆'
                asker_re_c2 = ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會會議上根據(.*)(和|及)(?P<repliers>.+)的(.*?)(答|回)覆'
            else:
                asker_re_e1 = ur'(?s)(.*) by (?P<asker>.+) and (.*?) reply by (?P<repliers>.+), (in|at) the Legislative Council'
                asker_re_e2 = ur'(?s)(.*) reply by (?P<repliers>.+), to a question by (?P<asker>.+) (on .*?)?(in|at) the Legislative Council'
                asker_re_c1 = ur'(?s)(.*)以下(為|是)今日（(?P<date>.+)）在立法會會議上(?P<asker>.+)(就.*?)?的提問(和|及)(?P<repliers>.+)的(.*?)答覆'
                asker_re_c2 = ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會會議上就(?P<asker>.+)的提問(.*?)(答|回)覆'
                
            match_pattern = asker_re_e1 if self.english else asker_re_c1       
            match_asker = re.match(match_pattern, header_str)
            if match_asker:
                print(u'1st branch')
                #print(match_asker.groups())
                self.asker = match_asker.group('asker')
                self.repliers = match_asker.group('repliers')
                #print(u'Asker:{} - Repliers:{}'.format(self.asker,self.repliers))
            else:
                match_pattern = asker_re_e2 if self.english else asker_re_c2
                match_asker = re.match(match_pattern, header_str)
                if match_asker:
                    print(u'2nd branch')
                    self.asker = match_asker.group('asker')
                    self.repliers = match_asker.group('repliers')
                else:
                    logger.warn('Cannot match asker and repliers for question {}'.format(self.uid))
        
        #2. content of question
        body = self.src.strip()
        #body = main_body_str #main_body_str messes up with format of text. Match the src instead.
        
        q_content_re_e = ur'(?s).*Question(s?)\s?(:|：|︰)(?P<q_content>(?s).*)Reply\s?(:|：|︰)?'
        q_content_re_c = ur'(?s).*問題\s?(:|：|︰)(?P<q_content>(?s).*)答覆\s?(:|：|︰)'
        q_content_re_c2 = ur'(?s).*答覆\s?(:|：|︰)?(?P<q_content>(?s).*)答覆\s?(:|：|︰)?' #rare case, missing '問題：' sub-heading, or a colon after '答覆'
        match_pattern = q_content_re_e if self.english else q_content_re_c
        match_q_content = re.match(match_pattern, body)
        if match_q_content:
            #self.question_content = match_q_content.group('q_content')
            pass
        elif self.english==False:
            match_pattern = q_content_re_c2
            match_q_content = re.match(match_pattern, body)
        
        try:
            self.question_content = match_q_content.group('q_content')
        except:
            logger.warn('Cannot match question content for question {}'.format(self.uid))
        
        #3. reply to question
        #reply_content_re_e = ur'(?s).*Reply:(?P<reply_content>(?s).*)Ends'
        #reply_content_re_c = ur'(?s).*答覆(：| :|:)(?P<reply_content>(?s).*)香港時間'
        reply_content_re_e = ur'(?s).*President,(?P<reply_content>(?s).*)Ends'
        reply_content_re_c = ur'(?s).*主席(女士|)\s?(:|：|︰)(?P<reply_content>(?s).*)完'
        match_pattern = reply_content_re_e if self.english else reply_content_re_c
        match_reply = re.match(match_pattern, body)
        if match_reply:
            self.reply_content = match_reply.group('reply_content')
            #self.reply_content = utf2html(self.reply_content)
        else:
            logger.warn('Cannot match reply content for question {}'.format(self.uid))