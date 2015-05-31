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
        htm = self.src
        
        ## seems that the page used 'hkscs'(香港增補字符集) as charset
        """
        #TESTING
        # Use these code to get and test a source from Legco website directly
        try:
            req = urllib2.Request(self.link, headers={ 'User-Agent': USER_AGENT })
            html = urllib2.urlopen(req).read()
        except HTTPError:
            logger.warn('Cannot get open reply link for question {]'.format(self.uid))
            
        #get encoding
        if html:
            content_type_re = ur'(?s).*content-type" content="(?P<content>.*?)"'
            content_type = re.match(content_type_re,html).group('content')
            charset = content_type.split('=')[1]
            print('Encoding detected: {}'.format(charset))
        else:
            logger.warn('Cannot get charset from reply link. Guess instead.')
            charset = 'utf-8' if self.english else 'BIG5' # sometimes not working for Chinese
        
        htm=html
        #ENDTESTING
        """
        
        # Use the lxml cleaner
        if htm:
            #Get rid of undesired characters here
            #use a list of dict to replace them differently (optional)
            list_undesired = [{'\x83\xdc':''},{'\x84P':''},{'\x84h':''},] #occasionally a character '财','绊' etc. is placed between newlines
            #replace different types of colons
            #list_undesired.append({'\xef\xbc\x9a':':'})
            #list_undesired.append({'\xef\xb8\xb0':':'})
            #list_undesired.append({'\xef\xb9\x95':':'})
            #list_undesired.append({'\xa0':' '})
            for item in list_undesired:
                htm=htm.replace(item.keys()[0],item.values()[0])
            
            # Assume 香港增補字符集(big5hkscs) is used
            htm = htm.decode('hkscs',errors='ignore') 
            
            cleaner = Cleaner()
            parser = HTMLParser(encoding='utf-8')
            # Finally, load the cleaned string to an ElementTree
            self.tree = cleaner.clean_html(lxml.html.fromstring(htm, parser=parser))
            self.src = htm
            #print('HTML source prepared.')
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
        #title_str = main_tree.text.strip() #also functional
        title_str =self.tree.text #more robust than the above one
        #print(self.tree.text.encode('utf-8'))

        #2. main body, including question header, question content and reply
        #e.g. 'Following is a question by the Hon Yeung Sum and a written reply...'
        main_body = main_tree.xpath('p[1]')[0]
        main_body_str = main_body.text_content() # do not strip, keep the format
        #print('Main Body String:{}'.format(main_body_str.encode('utf-8')))
        
        #=========================================================================#
        #TODO: there are a lot of different encodings of colons, e.g.
        #(:,：,︰,﹕) - with unicodes \u3A, \uFF1A, \uFE30, \ufe55 respectively (may be more)
        #and can have with whitespace ahead of them (no need to care for behind)
        #sometimes the colon is missing...
        #Find a way to handle them concisely! 
        #e.g. convert all alias to one kind, ':'
        #Currently, ur'\s?:' is used to deal with them - but be cautious! 
        #=========================================================================#
        
        # Parse the title
        #title_re_e = ur'LC(.*)?Q(?P<number>\d*)?:\s*(?P<subject>.+)' #e.g. 'LCQ17: Babies born in Hong Kong to mainland women'
        #title_re_c = ur'立法會(急切質詢)?(?P<number>\S*題)?：\s*(?P<subject>.+)' #e.g. '立法會五題：旅發局浮薪程式'
        
        # Simpler, no question number
        #note that the complete title is available in html header
        title_re_e = ur'(?s).+\s*(:|：|︰|﹕)\s*(?P<subject>.+)' 
        title_re_c = ur'(?s).+\s*(:|：|︰|﹕)\s*(?P<subject>.+)'
        #notice the difference of colon (half- and full-width) in the above regex
        #print(u'Title str: {}'.format(title_str))
        match_pattern = title_re_e if self.english else title_re_c
        match_title = re.match(match_pattern, title_str)
        if match_title:
            self.question_title = match_title.group('subject')
            #print(u'Title: {}'.format(self.question_title))
            ## We choose not to deal with numbers here, since they are better handled by scraper
            #if match_title['number']:
            #    self.question_number = match_title.group('number')
            #else:
            #    self.question_number = '0'
        else:
            logger.warn('Cannot match title for question {}'.format(self.uid))
            
        # Parse the main body - 3 parts
        #1. header of question, including date, asker and replier(s)
        header_re_e = ur'(?P<header>.+)Question(s?)\s?(:|：|︰|﹕)'
        header_re_c = ur'(?P<header>.+)問題\s?(:|：|︰|﹕)'
        # sometimes the phrase "問題:" is absent. Match up to the 1st colon instead.
        # Below should be the most general case. Too general that I prefer not to use.
        header_re_colon = ur'((?P<header>[^(:|：|︰|﹕)]*))' 
        match_pattern = header_re_e if self.english else header_re_c
        match_header = re.match(match_pattern, main_body_str.strip()) #strip here make it easier - get rid of newline
        if match_header is None:
            match_pattern = header_re_colon
            match_header = re.match(match_pattern, main_body_str.strip())
            
        header_str = None
        if match_header:
            header_str = match_header.group('header')
            #print(u'header str:{}'.format(header_str))
        else:
            logger.warn('Cannot match header for question {}'.format(self.uid))
            #print('Error!')
        
        #retrieve asker and replier(s) from header
        if header_str: #no need to try if no header
            #more complicated, need to pick regex based on urgent or not
            #there are two formats, need to separately match the 2 cases
            asker_re_e=[]
            asker_re_c=[]
            if self.urgent:
                asker_re_e.append(ur'(?s)(.*) by (?P<asker>.*?)(\son.*?)? under (.*) (reply|answer)(\son.+)? by (?P<repliers>.+)(in|at) the Legislative Council')
                asker_re_e.append(ur'(?s)(.*) (reply|answer) (by|of) (?P<repliers>.+) to a question by (?P<asker>.*?)(\son.*?)? under (.*) (in|at) the Legislative Council')
                asker_re_e.append(ur'(?s)(.*) (reply|answer) (by|of) (?P<repliers>.+) to (a|an)(\s.*)? question by (?P<asker>.*?)(\son.*?)? under (.*) (in|at) the Legislative Council')
                #sometimes a normal pattern is used for urgent question
                asker_re_e.append(ur'(?s)(.*) by (?P<asker>.*?)(\son.*?)?(and)? (a|an)(.*?) (reply|answer)(\son.+)? by (?P<repliers>.+)(in|at) the Legislative Council')
                
                asker_re_c.append(ur'(?s)(.*)以下(為|是)今日（(?P<date>.+)）在?立法會會議上(?P<asker>.+)根據(.*)質詢(和|及)(?P<repliers>.+)的(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<askers>.+)今日（(?P<date>.+)）在立法會會議上根據(.*)(和|及)(?P<repliers>.+)的(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)立法會(會議)?上(?P<asker>.+)(就.*?)?的提問(和|及)(?P<repliers>.+)的(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會會議上就(?P<asker>.+)提出的急切質詢所作的(答|回)覆')
            else:
                asker_re_e.append(ur'(?s)(.*) by (?P<asker>.*?)(\son.*?)?(and)? (a|an)(.*?) (reply|answer)(\son.+)? by (?P<repliers>.+)(in|at) the Legislative Council')
                asker_re_e.append(ur'(?s)(.*) (reply|answer) (by|of) (?P<repliers>.+) to a question (raised )?by (?P<asker>.*?)(\son.*?)?(in|at) the Legislative Council')
                asker_re_e.append(ur'(?s)(.*) by (?P<asker>.*?)(\son.*?)?(and)? (a|an)(.*?) (reply|answer)(\son.+)? by (?P<repliers>.+), today')
                asker_re_e.append(ur'(?s)(.*) (reply|answer) (by|of) (?P<repliers>.+) to a question(\son.*?)?(raised )?by (?P<asker>.*?)(in|at) the Legislative Council')
                
                asker_re_c.append(ur'(?s)(.*)立法會(會議)?上?(?P<asker>.+)(就.*?)?的提問(和|及)(?P<repliers>.+)的(.{0,5})(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會(會議)?上，?就(?P<asker>.+)的?提問(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)立法會(會議)?上，?(?P<repliers>.+)就(?P<asker>.+)的提問(所作)?的(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會會議上回應(?P<asker>.+)有關(.*?)提問(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)立法會(會議)?上(?P<asker>.+)的提問(，)?(和|及)(?P<repliers>.+)(就.*)的(.*?)(答|回)覆')#quite rare
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）在立法會(會議)?(上|上，)?就(?P<asker>.+)有關(.*)提問(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)以下(為|是)(?P<repliers>.+)今日（(?P<date>.+)）就(?P<asker>.+)有關(.*)提問(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)立法會會議上(?P<asker>.+)(就.*?)?的提問(（.*）)?(和|及)(?P<repliers>.+)的(.*?)(答|回)覆')
                asker_re_c.append(ur'(?s)(.*)立法會(會議)?上?(?P<asker>.+)(就.*?)?的提問(和|及)(?P<repliers>.+)書面(答|回)覆')
            
            header_str = header_str.replace('urder','under')
            header_str = header_str.replace('rely','reply') #ask Legco to fix this, since 'rely' is a legal word
            header_str = header_str.replace('council','Council')
            header_str = header_str.replace('Legilsative','Legislative')
            header_str = header_str.replace('Legisative','Legislative')
            header_str = header_str.replace('Counil','Council')
            header_str = header_str.replace(u'立法會會會',u'立法會會議')
            header_str = header_str.replace(u'立會會議',u'立法會會議')
            header_str = header_str.replace(u'立法會議',u'立法會會議')
            #Very weird string in some cases:\xa0\xa0
            header_str = header_str.replace(u'\xa0\xa0',' ')
            
            match_patterns = asker_re_e if self.english else asker_re_c
            for pattern in match_patterns:
                match_asker = re.match(pattern, header_str)
                if match_asker:
                    self.asker = match_asker.group('asker')
                    self.repliers = match_asker.group('repliers')
                    # Get rid of tailing comma/whitespace+comma/'的'
                    self.repliers = self.repliers.strip()
                    if self.repliers[-1]==',' or self.repliers[-1]==u'的':
                        self.repliers = self.repliers[:-1]
                
        #2. content of question
        body = self.src.strip()
        #print('body str: {}'.format(body.encode('utf-8')))
        #body = main_body_str #main_body_str messes up with format structure. Match the src/htm instead.
        q_content_re_e =[]
        q_content_re_c =[]
        q_content_re_e.append(ur'(?s).*Question(s?)\s?(:|：|︰|﹕)?(?P<q_content>(?s).*)(Reply|Answer)\s?(:|：|︰|﹕)?')
        q_content_re_e.append(ur'(?s).*(:|：|︰|﹕)(?P<q_content>(?s).*)(Reply|Answer)\s?(:|：|︰|﹕)?')
        q_content_re_e.append(ur'(?s).*Question(s?)\s?(:|：|︰|﹕)?(?P<q_content>(?s).*)(Madam)?(President|president)\s?(:|：|︰|﹕|,)?')
        q_content_re_c.append(ur'(?s).*問題\s?(:|：|︰|﹕)(?P<q_content>(?s).*)(答|回)覆\s?(:|：|︰|﹕)')
        q_content_re_c.append(ur'(?s).*(答|回)覆\s?(:|：|︰|﹕)?(?P<q_content>(?s).*)(答|回)覆\s?(:|：|︰|﹕)')
        q_content_re_c.append(ur'(?s).*問題\s?(:|：|︰|﹕)(?P<q_content>(?s).*)(主席|主席女士)\s?(:|：|︰|﹕)')
        q_content_re_c.append(ur'(?s).*問題(?P<q_content>(?s).*)(答|回)覆')#1 case only
        q_content_re_c.append(ur'(?s).*(答|回)覆：(?P<q_content>(?s).*)主席女士')#1 case only
        
        match_patterns = q_content_re_e if self.english else q_content_re_c
        for pattern in match_patterns:
            match_q_content = re.match(pattern, body)
            if match_q_content:
                self.question_content = match_q_content.group('q_content')
                break
        if match_q_content:
            if self.question_content[-6:]=='Madam ':
                self.question_content=self.question_content[:-6]
            #if self.question_content[-11:-13]=='答覆':
            #    self.question_content=self.question_content[:-12]
        else:
            logger.warn('Cannot match question content for question {}'.format(self.uid))
        
        #3. reply to question
        reply_content_re_e = []
        reply_content_re_c = []
        reply_content_re_e.append(ur'(?s).*(President|Madam president)\s?(:|：|︰|﹕|,)(?P<reply_content>(?s).*)Ends')
        reply_content_re_e.append(ur'(?s).*(Reply|Answer)\s?(:|：|︰|﹕|,)(?P<reply_content>(?s).*)Ends')
        reply_content_re_c.append(ur'(?s).*(主席|主席女士)\s?(:|：|︰|﹕|,)(?P<reply_content>(?s).*)完')
        reply_content_re_c.append(ur'(?s).*(答|回)覆\s?(:|：|︰|﹕|,)(?P<reply_content>(?s).*)完')#sometimes '主席|主席女士' was omitted

        match_patterns = reply_content_re_e if self.english else reply_content_re_c
        
        for pattern in match_patterns:
            match_reply = re.match(pattern, body)
            if match_reply:
                self.reply_content = match_reply.group('reply_content')
                break
        
        #no needed postprocessing found yet
        if match_reply is None:
            logger.warn('Cannot match reply content for question {}'.format(self.uid))