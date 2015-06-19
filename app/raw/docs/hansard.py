#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Document wrappers for LegCo Hansard (formal and floor)
"""
import logging
import lxml
from lxml import etree
import lxml.html
from lxml.html import HTMLParser
from lxml.html.clean import clean_html, Cleaner
import re
import itertools
from collections import OrderedDict
from raw.utils import to_string, to_unicode, grouper
from ..models.constants import *
from lxml.etree import tostring

logger = logging.getLogger('legcowatch-docs')

# Global header patterns. All are <strong> and upper case. Some

# these sub-sections should be in the main_heading section
# again, should be language-dependent

#<hr></hr> or <hr>

#Main Content
# The PRESIDENT will probably say something before main topic. 
# Sometimes interesting things happen.
TABLED_PAPERS_e = 'TABLING OF PAPERS'
TABLED_PAPERS_c = u'提交文件'
ORAL_QUESTIONS_e = 'ORAL ANSWERS TO QUESTIONS'
ORAL_QUESTIONS_c = u'議員質詢的口頭答覆'
WRITTEN_QUESTIONS_e = 'WRITTEN ANSWERS TO QUESTIONS'
WRITTEN_QUESTIONS_c = u'議員質詢的書面答覆'
MOTIONS_e = "MEMBERS' MOTIONS"
MOTIONS_c = u'議員議案'
BILLS_e = 'BILLS'
BILLS_c = u'法案'
STATEMENTS_e = 'STATEMENTS'
STATEMENTS_c = u'聲明'

#rare sessions
CE_Q_AND_A_e = "THE CHIEF EXECUTIVE'S QUESTION AND ANSWER SESSION"
CE_Q_AND_A_c = u'行政長官答問會'

SUSPENSION_e = 'SUSPENSION OF MEETING'
SUSPENSION_c = u'暫停會議'
NEXT_MEETING_e = 'NEXT MEETING'
NEXT_MEETING_c = u'下次會議'
ADJOURNMENT_e = 'ADJOURNMENT OF MEETING'
ADJOURNMENT_c = u'休會'

LIST_OF_HEADERS_e = [TABLED_PAPERS_e,ORAL_QUESTIONS_e,WRITTEN_QUESTIONS_e,MOTIONS_e,BILLS_e,STATEMENTS_e,CE_Q_AND_A_e,SUSPENSION_e,NEXT_MEETING_e,ADJOURNMENT_e]
LIST_OF_HEADERS_c = [TABLED_PAPERS_c,ORAL_QUESTIONS_c,WRITTEN_QUESTIONS_c,MOTIONS_c,BILLS_c,STATEMENTS_c,CE_Q_AND_A_c,SUSPENSION_c,NEXT_MEETING_c,ADJOURNMENT_c]
#<hr></hr> or </hr>

# some footnotes may follow


class CouncilHansard(object):
    """
    Object representing the **formal/translated** Council Hansard document.  This class
    parses the document source and makes all of the individual elements easily accessible
    """
    def __init__(self, uid, lang, source, *args, **kwargs):
        logger.debug(u'** Parsing hansard {}'.format(uid))
        self.uid = uid
        self.language = lang
        # Raw html string
        self.source = source
        self.tree = None
        # Main Heading
        self.main_heading = None #heading, element list
        self.date_and_time = None#datetime.datetime object
        # Attendance List
        self.president = None
        self.members_present = None
        self.members_absent = None
        self.public_officers = None
        self.clerks = None
        self.clerk_extra_string = None
        ## an <hr></hr> line separate heading and content ##
        # Main Content
        self.before_meeting = None
        # before TABLING OF PAPERS the President will summon Members.
        self.tabled_papers = None
        self.oral_questions = None
        self.written_questions = None
        self.bills = None
        self.motions = None
        self.ce_q_and_a = None
        
        self.question_map = None
        
        self.suspension = None #sometimes contain extra info as well as next meeting schedule.
        ## an <hr></hr> line separate content and footnote etc.
        self.other = None
        
        self.sections = [] #store the keys of SECTION_MAP here
        
        self._load()
        self._clean()
        self._parse()
        #self._post_process()
        
    def __repr__(self):
        return u'<CouncilHansard: {}>'.format(self.uid)
    
    def _load(self):
        """
        Load the ElementTree from the source
        """
        # Convert directional quotation marks to regular quotes
        double_quotes = ur'[\u201c\u201d]'
        self.source = re.sub(double_quotes, u'"', self.source)
        single_quotes = ur'[\u2019\u2018]'
        self.source = re.sub(single_quotes, u"'", self.source)
        # Convert colons
        self.source = self.source.replace(u'\uff1a', u':')
        # Convert commas
        #self.source = self.source.replace(u'\u2C', u',')
        # Remove line breaks and tabs
        self.source = self.source.replace(u'\n', u'')
        self.source = self.source.replace(u'\t', u'')
        # There are also some "zero width joiners" in random places in the text
        # Should remove them here, since they make string search unreliable
        # these are the codes: &#8205, &#160 (nbsp), \xa0 (nbsp), \u200d
        zero_width_joiners = u'\u200d'
        self.source = self.source.replace(zero_width_joiners, u'')
        # Also previously had some non breaking spaces in unicode \u00a0, but this
        # may have been fixed by changing the parser below
        
        # Parse unbalanced <hr> tags
        #get rid of all </hr>
        #self.source = self.source.replace('</hr>','')
        #then put proper tags back
        #self.source = self.source.replace('<hr>','<hr></hr>')

        # May need this for Chinese characters
        #self.source = self.source.decode('hkscs',errors='ignore')
        
        # Use the lxml cleaner
        cleaner = Cleaner()
        parser = HTMLParser(encoding='utf-8')
        # Finally, load the cleaned string to an ElementTree
        self.tree = cleaner.clean_html(lxml.html.fromstring(to_string(self.source), parser=parser))
        # self.tree = lxml.html.fromstring(to_string(self.source))
        
        #self._dump_as_fixture()
    
    def _clean(self):
        """
        Removes/combines some of tags to make parsing easier
        """
        #etree.strip_tags(self.tree, 'strong')#we need some <strong> tags in hansard
        
        # A very weird problem: sometimes an empty <p> block will cause the text below
        # <hr> line to be contained by extra <strong> box while trying to get rid of
        # extra <hr>s below. So have to delete them here.
        for xx in self.tree.xpath('//p'):
            if (xx.text_content()=='' or xx.text_content()==' ' or xx.text_content() is None) and xx.getchildren() is None:
                xx.drop_tree()
        
        for xx in self.tree.xpath('.//em'):
            if (xx.text_content()=='' or xx.text_content()==' ' or xx.text_content() is None) and xx.getchildren() is None:
                xx.drop_tree()
        
        # Get rid of some extra <strong> tags
        for xx in self.tree.findall('.//strong'):
            if xx.text_content()=='' or xx.text_content()==' ' or  xx.text_content() is None:
                xx.drop_tree()
        
        for xx in self.tree.find_class('pydocx-tab'):
            xx.drop_tag()
        
        
        #for xx in self.tree.find_class('pydocx-left'):
        #    xx.drop_tree()
        
        if self.language==LANG_EN:
            for xx in self.tree.find_class('pydocx-caps'):
                # Make all text inside uppercase.
                # Loop over all descendants and upper-case their text.
                # usually 'pydocx-caps' class comes with a <strong> tag inside
                desc = xx.xpath('./descendant::*')
                if desc is None:
                    xx.text = xx.text_content().upper()
                elif len(desc)==1:
                    desc[0].text = desc[0].text.upper()
                else:
                    for yy in desc:
                        yy.text = yy.text.upper()
                # Drop the pydocx-caps tag
                xx.drop_tag()
                #xx.attrib.pop('class')
         
        
        #Some testing scripts
        #tmp_content = self.tree.xpath('//body/p[138]')[0]
        #tmp_str = tmp_content.text_content()
        #print tmp_str
        #q_pattern = ur'^(?P<q_num>\d*)\.\s?(?P<name>[^:\(]*)(?P<lang>[^:]{0,15}):'
        #match = re.match(q_pattern, tmp_str)
        #if match is not None:
            #print(match.group('name'))
        
        
        # Handle More than 2 hr tags
        #print len(self.tree.xpath('//hr'))
        if len(self.tree.xpath('//hr'))>2:
            # If there are 2 <hr> tags, they divide the hansard
            
            # Usually this happens for Chinese, e.g. see 2015-04-22: Only Chinese version
            # has more than 2 <hr> tags but English version is alright.
            # A strategy is to get rid of excess <hr> tags to make it fit into the 3-part structure
            # as above. 
            # We can search for first <hr> after the the term '列席秘書', then
            #  delete all <hr>s afterward except the very last one (for main_content+sidenote)
            
            if  self.language==LANG_CN:
                pattern_clerk = u'列席秘書'
                #pattern_suspend = u'暫停會議'
                #pattern_next = u'下次會議'
            elif self.language==LANG_EN:
                pattern_clerk = 'CLERK'
                #pattern_suspend = 'SUSPENSION'
                #pattern_next = 'NEXT MEETING'

            #print(len(self.tree.xpath('//body//hr')))
            
            #search for the clerk block, and strip all <hr> before it
            for block in self.tree.xpath('//body/*'):
                if re.match(pattern_clerk,block.text_content()) is None:
                    if block.tag == 'hr':
                        block.drop_tree()
                    if block.xpath('.//hr'):
                        hrs = block.xpath('.//hr')
                        for hr in hrs:
                            hr.drop_tree()
                else:
                    break
            
            # strip all <hr> tags except the one after clerks
            #for hr in self.tree.xpath('./body//hr')[1:]:
            #    hr.drop_tag()
        
            
        # Some titles may be broken. Join them.
        # Actually the main heading may also need this, but is ignored for now.
        for p in self.tree.xpath('//body/p[count(preceding::hr)=1]'):   #i.e. the main_content
            if p.tail is None: #no text before first element
                children = p.getchildren() #children is everything inside one <p> block
                if len(children)>1:
                    for child in children:
                        if child.tag!='strong' or child.tail is not None:#if other stuffs present, break
                            break
                    else:
                        # Found a <p> block to fix
                        etree.strip_tags(p,'strong')
                        tmp_text = p.text_content()
                        p.clear()
                        subtext = etree.SubElement(p, "strong")
                        subtext.text = tmp_text
                     
        #Before we do anything, we may want to dump the 'cleaned' hansard for inspection in browser etc.
        #Notice that this html is not the same as from RawCouncilHansard._dump_as_fixture(),
        #and is stored in a different folder
        
        self._dump_as_fixture()
                        
                        
    def _parse(self):
        """
        Parse the source document and populate this object's properties
        This method breaks the Hansard by <hr> into (3) sections, and pass they to their
        corresponding parsers.
        """
        
        # The Hansards, unlike agendas, do not have <div> tag. All texts are contained in <p>,
        #occasionally tables turns up, all without much hierarchy.
        # Hansard can be divided into 3 parts, separated by <hr> tag.
        # Main headings lie in <strong> tags, and all letters are of upper case. However, same holds true
        #for the names of speakers and bill titles, etc. 
        # In these cases, we can either look inside the content of <p> tag to decide,
        #or we can match the header strings to see.
        
        if self.language == LANG_EN:
            LIST_OF_HEADERS = LIST_OF_HEADERS_e
        elif self.language == LANG_CN:
            LIST_OF_HEADERS = LIST_OF_HEADERS_c
        else:
            logger.error(u'The Hansard parser cannot handle Floor Recording:{}'.format(self.uid))
            return None
        logger.info(u'Language: {}'.format(self.language))
        
        
        main_heading = self.tree.xpath('//body/*[count(preceding::hr)=0]')#main title and people attendance
        main_content = self.tree.xpath('//body/*[count(preceding::hr)>0]')#main content of meeting
        #main_sidenote = self.tree.xpath('//body/*[count(preceding::hr)=2]')#some sidenotes/appendix (optional?)
        
        #shut up and take my main_heading
        self._parse_main_heading(main_heading)

        #print('here')
        ### parsing main_content: ###
        # Strategy: we do not make any assumption on the order of occurrence of each section.
        # We will loop over all Elements of main_content, checking for headers - if a <strong> tag
        # is present, is upper case, and the text matches one of the element in LIST_OF_HEADERS, 
        # we remember it and append all following Elements to a list, until another header is found. 
        # In this case, we update the CouncilHansard.SECTION_MAP with the corresponding key(header name) and 
        # value(list of Elements).
        # Afterwards, we will pass these sections on for further processing.
        # Remember: do not only save text_content() to the list since we need the tags and formatting.
        
        # Without assuming order, loop through all elements for potential headers
        # Note that there are some info about the beginning of meeting (after first <hr>)
        elem_key = u'BEFORE MEETING' if self.language==LANG_EN else u'會議前'
        elem_list = []
        
        #Do not make any assumption on what sections will pop up
        SECTION_MAP = OrderedDict()
        
        for part in main_content:
            if self.language==LANG_EN:
                if (part.xpath('./strong') is not None and part.text_content().isupper()) or part.tag=='strong':
                    #Potential header
                    #print part.text_content()
                    potential_header = part.text_content()
                    if potential_header in LIST_OF_HEADERS:
                        # New header found
                        if elem_list !=[]:
                            SECTION_MAP.update({elem_key:elem_list}) # save the previous part
                        elem_key = potential_header #update key
                        elem_list = [] #empty list
                        continue
                elem_list.append(part)
            elif self.language==LANG_CN:
                if (part.xpath('./strong') is not None and len(part.xpath('./strong'))==1) or part.tag=='strong':
                    #Potential header
                    #potential_header = part.xpath('./strong')[0].text_content()
                    potential_header = part.text_content()
                    #print potential_header
                    if potential_header in LIST_OF_HEADERS:
                        # New header found
                        if elem_list !=[]:
                            SECTION_MAP.update({elem_key:elem_list}) # save the previous part
                        elem_key = potential_header #update key
                        #print elem_key
                        elem_list = [] #empty list
                        continue
                elem_list.append(part)
        SECTION_MAP.update({elem_key:elem_list})#do not forget the last section
        #for key in SECTION_MAP.keys():
        #    print key
        
        # Useful scripts:
        # 1. look into a section
        #for part in SECTION_MAP[MEMBER_PRESENT_e]:
            #print(part.text_content())
        # 2. Check what headers were found and their order
        #for key in SECTION_MAP.keys():
            #print(key)
        
        # Store all keys in self.headers for easy reference
        for key in SECTION_MAP.keys():
            self.sections.append(key)
        
        # Forward each section to its corresponding parser
        lang_char = 'e' if self.language==LANG_EN else 'c'
        for section in SECTION_MAP.keys():
            logger.info(u'Parsing {} section for Hansard: {}'.format(section, self.uid))
            if section == 'BEFORE MEETING':
                self._parse_before_meeting(SECTION_MAP[section])
                
            elif section == eval('TABLED_PAPERS_{}'.format(lang_char)):
            #elif section == globals()['TABLED_PAPERS_{}'.format(lang_char)]: #also works
                self._parse_tabled_papers(SECTION_MAP[section])
                
            elif section == eval('ORAL_QUESTIONS_{}'.format(lang_char)):
                self._parse_oral_answers_to_questions(SECTION_MAP[section])
            elif section == eval('WRITTEN_QUESTIONS_{}'.format(lang_char)):
                self._parse_written_answers_to_questions(SECTION_MAP[section])
            elif section == eval('BILLS_{}'.format(lang_char)):
                self._parse_bills(SECTION_MAP[section])
            elif section == eval('MOTIONS_{}'.format(lang_char)):
                self._parse_motions(SECTION_MAP[section])
            elif section == eval("CE_Q_AND_A_{}".format(lang_char)):
                self._parse_CE_Q_AND_A(SECTION_MAP[section])
                
    ## Parsers for sections
    def _parse_main_heading(self,heading_list):  
        """
        Parser for main heading of Hansard.
        Fills in the following elements:
        1. self.date_and_time: The date and time of meeting, as datetime.datetime object.
        2. self.president: Name of the president as 2-tuples (name,full_name_and_title).
        3. self.members_present: Council member present, as a list of 2-tuples (name,full_name_and_title).
        4. self.members_absent: Council member absent, as a list of 2-tuples (name and title,full_name_and_title).
        5. self.public_officers: Public officers present, as a list of 3-tuples (name,title,position).
        6. self.clerks: Clerks present, as a list of 2-tuples. Each tuple consists of strings in format
                        (name and title[optional], position)
        """
        #debug
        #for elem in heading_list:
        #    print(elem.text_content())
        
        HANSARD_TITLE_e = 'OFFICIAL RECORD OF PROCEEDINGS'
        HANSARD_TITLE_c = u'會議過程正式紀錄'
        MEMBERS_PRESENT_e = 'MEMBERS PRESENT:'
        MEMBERS_PRESENT_c = u'出席議員:'
        MEMBERS_ABSENT_e = ['MEMBERS ABSENT:','MEMBER ABSENT:']
        MEMBERS_ABSENT_c = u'缺席議員:'
        PUBLIC_OFFICERS_e = ['PUBLIC OFFICERS ATTENDING:','PUBLIC OFFICER ATTENDING:']
        PUBLIC_OFFICERS_c = u'出席政府官員:'
        CLERKS_e = ['CLERKS IN ATTENDANCE:','CLERK IN ATTENDANCE:']
        CLERKS_c = u'列席秘書:'
        
        if self.language==LANG_EN:
            HANSARD_TITLE = HANSARD_TITLE_e
            MEMBERS_PRESENT = MEMBERS_PRESENT_e
            MEMBERS_ABSENT = MEMBERS_ABSENT_e
            PUBLIC_OFFICERS = PUBLIC_OFFICERS_e
            CLERKS = CLERKS_e
            PRESIDENT = u'THE PRESIDENT'
        elif self.language==LANG_CN: 
            HANSARD_TITLE = HANSARD_TITLE_c
            MEMBERS_PRESENT = MEMBERS_PRESENT_c
            MEMBERS_ABSENT = MEMBERS_ABSENT_c
            PUBLIC_OFFICERS = PUBLIC_OFFICERS_c
            CLERKS = CLERKS_c
            PRESIDENT = u'主席'
        
        #other languages ('b') should have raised an error in _parse, so no 'else' branch here
        
        #dictionary, key = string to match, value = the key to use in main_heading_map
        DICT_MAIN_HEADING = dict(
                             {
                              HANSARD_TITLE:'HANSARD_TITLE',
                             MEMBERS_PRESENT:'MEMBERS_PRESENT',
                             #MEMBERS_ABSENT:'MEMBERS_ABSENT',
                             #PUBLIC_OFFICERS:'PUBLIC_OFFICERS',
                             #CLERKS:'CLERKS'
                                }
                             )
        #allow for single/plural in spelling
        if type(MEMBERS_ABSENT) is list and len(MEMBERS_ABSENT)>1:
            for dup in MEMBERS_ABSENT:
                DICT_MAIN_HEADING.update({dup:'MEMBERS_ABSENT'})
        else:
            DICT_MAIN_HEADING.update({MEMBERS_ABSENT:'MEMBERS_ABSENT'})
            
        if type(PUBLIC_OFFICERS) is list and len(PUBLIC_OFFICERS)>1:
            for dup in PUBLIC_OFFICERS:
                DICT_MAIN_HEADING.update({dup:'PUBLIC_OFFICERS'})
        else:
            DICT_MAIN_HEADING.update({PUBLIC_OFFICERS:'PUBLIC_OFFICERS'})
            
        if type(CLERKS) is list and len(CLERKS)>1:
            for dup in CLERKS:
                DICT_MAIN_HEADING.update({dup:'CLERKS'})
        else:
            DICT_MAIN_HEADING.update({CLERKS:'CLERKS'})

        main_heading_map = dict()
        
        #Put elements into dictionary
        elem_key = ''
        elem_val = []
        for elem in heading_list:
            tmp_str = elem.text_content()
            #sometimes it is headed/followed by space(s). Remove them
            """
            try:
                while tmp_str[0] == ' ':
                    tmp_str = tmp_str[1:]
                while tmp_str[-1] == ' ':
                    tmp_str = tmp_str[:-1]
            except IndexError:
                pass
            """
            tmp_str = tmp_str.strip()
            if tmp_str in DICT_MAIN_HEADING.keys():
                # New header found
                if elem_key=='':
                    elem_key = DICT_MAIN_HEADING[tmp_str] #update key
                    continue
                main_heading_map.update({elem_key:elem_val}) # save the previous part
                elem_key = DICT_MAIN_HEADING[tmp_str] #update key
                elem_val = [] #empty list
                continue
            elem_val.append(elem)
        main_heading_map.update({elem_key:elem_val})

        #now the main_heading_map should have 5 keys - do a sanity check?
        
        #1. Get the date and time of meeting, and compare against uid/raw_date
        # The first string should be the date of meeting, e.g.
        # 'Wednesday, 29 April 2015'
        # We can check and see if it matches the RawCouncilHansard object
        
        # The second string specifies the time when the council met, e.g.
        # "The Council met at Eleven o'clock"
        
        #2. Get the president, as well as members present
        members_pres = main_heading_map['MEMBERS_PRESENT'] #a list of Elements
        #notice the format is slightly different in different languages
        if self.language==LANG_EN:
            list_members_pres = self._get_member_list(members_pres[1:])
            # the first entry is the president
            self.president = list_members_pres[0]
            self.members_present = list_members_pres[1:]#the president must present- understood
        elif self.language==LANG_CN:
            members_pres[0].text = members_pres[0].text.replace(PRESIDENT,'')
            list_members_pres = self._get_member_list(members_pres)
            self.president = list_members_pres[0]
            self.members_present = list_members_pres[1:]

        
        #3. Get absent members
        members_abs = main_heading_map['MEMBERS_ABSENT']

        self.members_absent = self._get_member_list(members_abs)

        #4. The list of public officers is a little different: 
        # For English, the first line is a name+title, with a second line about his/her position
        # For Chinese, only 1 line.
        
        public_officers_pres = main_heading_map['PUBLIC_OFFICERS']
        
        #maybe there is a case where no officers present?
        if public_officers_pres is None:
            self.public_officers = None
            logger.warn(u'No public officer present in {}.'.format(self.uid))
        else:
            if self.language==LANG_EN:
                #split the odd and even entries
                officers_name_str = public_officers_pres[::2]
                officers_position_str = public_officers_pres[1::2]
                #print(officers_name_str)
                #print(officers_position_str)
                if len(officers_name_str)!=len(officers_position_str):
                    logger.error(u'Number of officers does not match number of positions- {}:{}'.format(len(officers_name_str),(officers_position_str)))
                    self.public_officers = None
                else:
                    #officers are not in member list (RawMember), so only get their name and title
                    if len(officers_name_str)>1:
                        officers_name=[elem.text_content().split(',')[0] for elem in officers_name_str]
                        officers_title=[elem.text_content().split(',',1)[1] for elem in officers_name_str]
                        #officers_title = ', '.join(officers_title)
                        officers_position=[elem.text_content() for elem in officers_position_str]
                        self.public_officers = zip(officers_name,officers_title,officers_position)
                    else:
                        #print officers_name_str[0].text_content()
                        officers_name = officers_name_str[0].text_content().split(',')[0]
                        officers_title = officers_name_str[0].text_content().split(',',1)[1]
                        officers_position= officers_position_str[0].text_content()
                        self.public_officers = [(officers_name,officers_title,officers_position)]
            elif self.language==LANG_CN:
                officer_pattern_c = ur'(?P<position>.*[局長|司長])(?P<name>.*)'
                tmp_list = []
                for elem in public_officers_pres:
                    officers_name = elem.text_content().split(',',1)[0]
                    if len(elem.text_content().split(',',1))>1:
                        officers_title = elem.text_content().split(',',1)[1]
                    else:
                        officers_title = ''
                    match = re.match(officer_pattern_c,officers_name)
                    if match is not None:
                        tmp_list.append((match.group('name'),officers_title,match.group('position')))
                    else:
                        logger.error(u'Unrecogised string for officers: {}'.format(officers_name))
                        #tmp_list.append((officers_name,officers_title,''))
                        
                self.public_officers = tmp_list
        
        #5. Finally, the clerks in attendance
        #the format in harsard is: name, title(s)[optional],position
        #similar to officers, return a list of 3-tuple
        clerks = main_heading_map['CLERKS']              
        clerk_list = []
        extra_str = None
        chinese_pattern_re = ur'(?P<title>.*秘書長)(?P<name>.*)'
        english_pattern_re = r'SECRETARY' #for English we just check if it is really about a clerk
        for elem in clerks:
            if elem.text_content()!='': #sometimes a tailing '' (perhaps due to <hr>?) at the end
                if self.language==LANG_EN:
                    search = re.search(english_pattern_re, elem.text_content())
                    if search is not None:
                    #if english_pattern_re in elem.text_content():
                        clerk_str = elem.text_content().rsplit(',',1)
                        # not observed yet, but multiple titles may occur
                        clerk_list.append((clerk_str[0],clerk_str[1]))
                    else:
                        logger.warn(u'Cannot parse a clerk string: {}'.format(elem.text_content()))
                        extra_str = elem.text_content()
                        continue
                elif self.language==LANG_CN:
                    match = re.match(chinese_pattern_re,elem.text_content())
                    if match is not None:
                        clerk_list.append((match.group('name'),match.group('title')))
                    else:
                        #sometimes there is extra string after clerk (e.g.2015.03.26)
                        logger.warn(u'Cannot parse a clerk string: {}'.format(elem.text_content()))
                        extra_str = elem.text_content()
                        continue
                    
        self.clerks = clerk_list
        self.clerk_extra_string = extra_str
        #Done.
    
    def _parse_before_meeting(self,elem_list):
        """
        Parse the dialogue before council meeting commences.
        """
        if elem_list==None:
            self.before_meeting = None
        else:
            self.before_meeting = self.parse_dialogs(elem_list)
        
    
    def _parse_tabled_papers(self,elem_list):
        pass

    def _parse_oral_answers_to_questions(self,elem_list):
        """
        Choose parser for oral_answers_to_questions according to language
        Because the format is different for different languages, better use different methods.
        """
        if self.language==LANG_EN:
            self.oral_questions = self._parse_answers_to_questions_e(elem_list)
        elif self.language==LANG_CN:
            self.oral_questions = self._parse_answers_to_questions_c(elem_list)
            
            
    def _parse_written_answers_to_questions(self,elem_list):
        """
        Choose parser for written_answers_to_questions according to language
        Because the format is different for different languages, better use different methods.
        """
        if self.language==LANG_EN:
            self.written_questions = self._parse_answers_to_questions_e(elem_list)
        elif self.language++LANG_CN:
            self.written_questions = self._parse_answers_to_questions_c(elem_list)
    
    
    def _parse_answers_to_questions_e(self,elem_list):
        """
        Parse English xxx_answers to questions.
        """
        logger.info(u'Parsing written answers to questions.')
        #break the section into questions
        q_name=''
        q_elem=[]
        list_of_questions = []
        for elem in elem_list:
            #the title of each question is a single <strong> block with both upper and lower case characters.
            children = elem.getchildren()
            if len(children)==1:
                child = children[0]
                if child.tag=='strong' and child.text_content().isupper()==False:
                    #found a new question
                    if q_name!='':
                        list_of_questions.append((q_name,q_elem))
                    q_name = child.text_content()
                    q_elem=[]
                    continue
            q_elem.append(elem)
        list_of_questions.append((q_name,q_elem)) #last one
        
        #now we have all questions
        #for each question, separate dialogues. The first <p> will contain question number, 
        #name of speaker, and language. All following text will be part of question until another speaker
        #answers. Afterwards, if further conversation presents for the matter, another name of speaker
        #block will turn up just like the answer. All body contents will be contained inside a list of 2-tuple,
        #(speaker,speech)
        question_obj = []
        for q in list_of_questions:
            #From 1st Element, get question number and asker
            tmp_q = q[1][0] #q[0] is the title, q[1] are body elements q[1][0] is the first <p> block
            #question number
            q_num = tmp_q.text
            if q_num is None:
                q_num = '0'
            else:
                q_num = q_num.replace('.','')
            #get rid of number
            tmp_q.text = None
            #question speaker (asker)
            tmp_speaker = tmp_q.xpath('./strong')[0]
            q_speaker = tmp_q.xpath('./strong')[0].text
            #We do not need these text anymore. Drop them.
            tmp_q.remove(tmp_speaker)
            #Replace the original p block with this, and append it to body
            q[1][0] = tmp_q #notice q[1][0] is still an Element object
            
            #However, the above treatment has a side-effect of losing potential '(in Chinese):' text.

            # Now begin putting speeches into containers, until a new speaker is found
            # Note that occasionally there will be <strong> block in answer, so a more
            # sophiscated approach is needed to find speaker:
            #1. p.text is None (no text right after the <p> tag)
            #2. One and only one <strong> block inside a <p> block
            #3. All text inside <strong> block are upper-case
            #Hopefully these conditions will cover all cases
            q_body = [] #holds all (speaker,speech) tuples
            q_speech_container = '' #holds all speeches as a list of Elements
            for block in q[1]:#remember a block can be <p> or <table> or else
                if block.tag=='p' and len(block.xpath('./strong'))==1 and block.text == None:
                    if block.xpath('./strong')[0].text.isupper():
                        #a new speaker found
                        # save the speech of last speaker
                        q_body.append((q_speaker,q_speech_container))
                        q_speech_container = ''
                        # Store the speaker and get rid of the <strong> block
                        q_speaker = block.xpath('./strong')[0].text
                        block.xpath('./strong')[0].text = None
                        
                        # Get rid of extra colon
                        if block.xpath('./strong')[0].tail[0]==':':
                            block.xpath('./strong')[0].tail = block.xpath('./strong')[0].tail[1:]
                        
                        etree.strip_tags(block,'strong')#we know there will only be 1 <strong> block
                q_speech_container = ''.join([q_speech_container,tostring(block)]) 
            q_body.append((q_speaker,q_speech_container))#do not forget the last speech
            question_obj.append((q_num,q[0],q_body))
        return question_obj
    
    def _parse_answers_to_questions_c(self,elem_list):
        """
        Parser for  Chinese xxx_answers_to_questions section.
        """
        # Firstly, split up questions by looking at titles
        # A title has following characteristic:
        # 1. A <p> block with one single <strong> child.
        # 2. No text other than that inside <strong> box
        q_name=''
        q_elem=[]
        list_of_questions = []
        for elem in elem_list:
            if elem.getchildren() is not None:
                if len(elem.getchildren())==1 and elem.text is None:
                    child = elem.getchildren()[0]
                    if child.tag == 'strong' and child.tail is None:
                        #we find a new title
                        if q_name!='':
                            list_of_questions.append((q_name,q_elem))
                        q_name = child.text_content()
                        q_elem=[]
                        continue
            q_elem.append(elem)
        list_of_questions.append((q_name,q_elem))
        
        # For each questions, get question number and speeches
        # This is very similar to English version, except the question number (including the '.')
        # is inside a <strong> box.
        # A quick way is to drop that <strong> tag, then use the same idea as in English version.
        # but beware that sometimes everything lives inside an <em> block.
        
        # Drop the first <strong> tag. We know them must come immediately after the title.
        for q in list_of_questions:
            elem = q[1][0] # first <p> block
            elem.xpath('./strong')[0].drop_tag()
        
        # Process like English version
        question_obj = []
        for q in list_of_questions:
            #From 1st Element, get question number and asker
            tmp_q = q[1][0] #q[0] is the title, q[1] are body elements q[1][0] is the first <p> block
            #question number
            q_num = tmp_q.text
            if q_num is None:
                q_num = '0'
            else:
                q_num = q_num.replace('.','')
            #get rid of number
            tmp_q.text = None
            #question speaker (asker)
            tmp_speaker = tmp_q.xpath('./strong')[0]
            q_speaker = tmp_q.xpath('./strong')[0].text
            #We do not need these text anymore. Drop them.
            tmp_q.remove(tmp_speaker)
            #Replace the original p block with this, and append it to body
            q[1][0] = tmp_q #notice q[1][0] is still an Element object
            
            #However, the above treatment has a side-effect of losing potential '(in Chinese):' text.
            
            # Now begin putting speeches into containers, until a new speaker is found
            #1. A <strong> box, tailed by some text

            q_body = [] #holds all (speaker,speech) tuples
            q_speech_container = '' #holds all speeches as a list of Elements
            for block in q[1]:#remember a block can be <p> or <table> or else
                if block.tag=='p' and len(block.xpath('./strong'))==1:
                    if block.xpath('./strong')[0].tail is not None:
                        #a new speaker found
                        # save the speech of last speaker
                        q_body.append((q_speaker,q_speech_container))
                        q_speech_container = ''
                        # Store the speaker and get rid of the <strong> block
                        q_speaker = block.xpath('./strong')[0].text
                        block.xpath('./strong')[0].text = None
                        
                        # Get rid of extra colon
                        if block.xpath('./strong')[0].tail[0]==':':
                            block.xpath('./strong')[0].tail = block.xpath('./strong')[0].tail[1:]
                        
                        etree.strip_tags(block,'strong')#we know there will only be 1 <strong> block
                q_speech_container = ''.join([q_speech_container,tostring(block)]) 
            q_body.append((q_speaker,q_speech_container))#do not forget the last speech
            question_obj.append((q_num,q[0],q_body))#put each question into question_obj
            
        return question_obj
    
    
    def _parse_bills(self,elem_list):
        """
        Choose parser for bills according to language
        Because the format is different for different languages, better use different methods.
        
        政府主要負責以法案的形式，將新訂法例或現行法例的修訂建議提交立法會審議，以制定成為法例。議員只要符合若干條件，亦可向立法會提交法案。

        法案的通過:

        法案在提交立法會之前，會先在憲報上刊登。法案如要獲立法會通過，必須經首讀、二讀及三讀的程序。
        進行首讀時，立法會秘書會在立法會會議席上宣讀法案的簡稱，這是法案提交立法會的正式程序。
        提交有關法案的政府官員或議員繼而會動議"‍法案予以二讀"的議案，並會發言解釋法案的目的，法案二讀隨之展開。
        在動議議案後，有關的辯論通常會中止待續，以便把法案交付內務委員會，讓議員有更充裕的時間，在內務委員會或由內務委員會專為法案而成立的法案委員會詳加研究。

        法案經內務委員會或法案委員會審議後，便會在其後舉行的立法會會議席上恢復二讀辯論。
        在辯論時，議員會就法案的整體優劣及原則表達意見，並可表明他們是否支持法案。
        立法會繼而會就"‍法案予以二讀"的議案進行表決。若議員否決有關議案，法案的立法程序便會終止。
        若議員通過有關議案，法案獲得二讀通過，立法會全體議員便會在委員會審議階段以"‍全體委員會‍"名義，審議法案各條文，並在委員會同意下作出修正。
        法案不論是否有所修正，經全體委員會通過後，便會向立法會作出報告，以便立法會考慮是否支持進行三讀並通過法案。
        恢復二讀辯論和三讀(若法案獲得二讀通過)通常會在同一次立法會會議進行。

        法案如通過首讀、二讀及三讀程序，便獲制定成為法例。
        除非法案訂明較後的生效日期，否則有關法例經行政長官簽署並在憲報刊登後便可生效。 
        """
        if elem_list is None:
            return None
        
        if self.language==LANG_EN:
            self.bills = self._parse_bills_e(elem_list)
        elif self.language==LANG_CN:
            self.bills = self._parse_bills_c(elem_list)
    
    def _parse_bills_e(self,elem_list):
        first_reading_e = r'First Reading of Bills'
        second_reading_e = r'Second Reading of Bills'
        resumption_e = r'Resumption of Second Reading Debate on Bills' #normally resumption of second reading
        committee_stage_e = r'Committee Stage'
        third_reading_e = r'Third Reading of Bills'
        
        list_of_stages = [first_reading_e,second_reading_e,resumption_e,third_reading_e,committee_stage_e]
        
        # Title of a bill is a single <strong> box inside <p>, with all letters in upper-case,
        # and no tailing text afterward
        # situation of a bill (e.g. first reading, resumption of second reading debate, etc.)
        # are same as title but text are both upper- and lower-case.
        # special condition e.g. reading of a bill the First time will be in <p><em>xxx</em></p> block
        # proposed amendments will be in <p><strong>xxx</strong></p> box with both upper and lower case,
        # but not sure if there is any exception.
        # First Reading -> Second Reading (and adjourn)-> Resumption of Second Reading-> 
        # Committee stage -> Third Reading -> Pass
        
        # We use the strings like 'First Reading' (in <strong> box) to track the stage of bills.
        bill_stage = None
        #bill_title = None
        stage_content_body = []
        stage_elem = []
        # break content according to stages first
        for elem in elem_list:
            if elem.xpath('.//strong') is not None:
                potential_stage = elem.xpath('.//strong')
                if len(potential_stage)==1:
                    # Check for stage
                    # A better way is to use regex for matching
                    if potential_stage[0].text_content() in list_of_stages and not potential_stage[0].text_content().isupper():
                        # Found a new stage
                        # Save previous if necessary
                        if bill_stage is not None and stage_elem!=[]:
                            stage_content_body.append((bill_stage,stage_elem))
                            stage_elem = []
                        bill_stage = potential_stage[0].text_content()
                        continue
            stage_elem.append(elem)
        # Save the last one
        if bill_stage is not None and stage_elem!=[]:
            stage_content_body.append((bill_stage,stage_elem))
        
        #for elem in stage_content_body:
        #    print('{}:len = {}'.format(elem[0],len(elem[1])))
        #    print elem[1][0].text_content() # print the first line after a new stage
        
        
        # Break the stage_content_body into speeches, separated by bill titles
        bill_title = None
        speech_content_body = []
        speech_list = [] #format: [(stage_0,title_0,[elem_0,elem_1,...]),(stage_0,title_1,[elem_0,elem_1,...]), ...]
        for stage in stage_content_body: #for different stages
            for stage_elem in stage[1]: # for all Elements in each stage
                #print stage_elem.text_content()
                # look for a new title
                if len(stage_elem.xpath('./strong'))==1:
                    potential_title = stage_elem.xpath('./strong')
                    #print potential_title[0].text_content()
                    if potential_title[0].tail == None and potential_title[0].text_content().isupper():
                        #Found a new title
                        # Save previous speeches/debates. Sometimes there is no title.
                        if speech_content_body!=[]:
                            speech_list.append((stage[0],bill_title,speech_content_body))
                            speech_content_body = []
                        bill_title = potential_title[0].text_content()
                        continue
                speech_content_body.append(stage_elem)
        if speech_content_body != []:
            speech_list.append((stage[0],bill_title,speech_content_body))
        
        #for speech in speech_list:
        #    print speech[0],speech[1],speech[2][0].text_content()
        
        bills_obj = []
        # pass all speech_content_body to dialog parser
        for speech in speech_list:
            dialog = self.parse_dialogs(speech[2])
            bills_obj.append((speech[0],speech[1],dialog))
        
        return bills_obj
        
    
    def _parse_bills_c(self,elem_list):
        pass
    
    def _parse_motions(self,elem_list):
        
        if self.language==LANG_EN:
            self._parse_motions_e(elem_list)
        elif self.language++LANG_CN:
            self._parse_motions_c(elem_list)
        return
    
    def _parse_motions_e(self,elem_list):
        """
        Parser for motions in English Hansard.
        """
        # English titles have following characteristics:
        # 1. A <strong> box as only element in a <p> block.
        # 2. All text inside <strong> box are upper-case.
        # 3. No tailing text after <strong> box
        # subtitles share the same characteristics, except that the text contain both upper- and lower-case.
        motion_title = None #there may be some speech before first title
        motion_body = [] #element list, will be converted to HTML string later
        list_of_motions = []
        for elem in elem_list:
            if elem.xpath('./strong') is not None:
                strong_box = elem.xpath('./strong')
                if len(strong_box) == 1 and strong_box[0].tail is None and strong_box[0].text.isupper():
                    # We have a new title
                    # Save last speech
                    if motion_body != []:
                        list_of_motions.append((motion_title,motion_body))
                        motion_title = strong_box[0].text
                        motion_body = []
                        continue
            motion_body.append(elem)
        list_of_motions.append((motion_title,motion_body))
        #print list_of_motions
        
        motions_obj = []
        for motion in list_of_motions:
            debates = self.parse_dialogs(motion[1]) #debates is a list of 2-tuple (name, raw HTML string)
            motions_obj.append((motion[0],debates)) #(title,subtitle,[(speaker_0,speech),...])
        
        #print motions_obj[1][2][0][0]
        #print motions_obj[1][2][0][1]
        self.motions = motions_obj
    
    def _parse_motions_c(self,elem_list):
        """
        Parser for motions in Chinese Hansard.
        """
        # The strategy is to split different motions by searching for titles,
        # then pass the debates/speeches of each motions to parse_dialogs()
        # for splitting speeches.
        # Therefore, the primary aim of this parser is to find titles and pass
        # the sections in between to parse_dialogs()
        
        # A Chinese title has following characteristics:
        # 1. Lives inside a <strong> block, and
        # 2. This <strong> block lives inside a <p> block, and is the only element
        #    of this <p> block.
        # 3. This <p> block does not have any text content other than inside
        #    <strong> block
        # Note that sometimes a subtitle pops up after title. It is not possible to
        # tell their differences just by HTML layout. The way to distinguish is to 
        # check if any other blocks are in between them.
        
        motion_title = None #there may be some speech before first title
        motion_body = [] #element list, will be converted to HTML string later
        list_of_motions = []
        for elem in elem_list:
            if elem.xpath('./strong') is not None:
                strong_box = elem.xpath('./strong')
                if len(strong_box) == 1 and strong_box[0].tail is None:
                    # We have a new title/subtitle
                    # Save last speech
                    if motion_body != []:
                        list_of_motions.append((motion_title,motion_body))
                        motion_title = None
                        motion_body = []
                        
                    motion_title = strong_box[0].text
                    continue
            motion_body.append(elem)
        list_of_motions.append((motion_title,motion_body))
        #print list_of_motions
        
        motions_obj = []
        for motion in list_of_motions:
            debates = self.parse_dialogs(motion[1]) #debates is a list of 2-tuple (name, raw HTML string)
            motions_obj.append((motion[0],debates)) #(title,subtitle,[(speaker_0,speech),...])
        
        self.motions = motions_obj
        
    def _parse_CE_Q_AND_A(self,elem_list):
        self.ce_q_and_a = self.parse_dialogs(elem_list)
        
        
    # Functions
    
    def parse_dialogs(self,elem_list):
        """
        Given dialogs as a list of Element objects,
        returns a list of 2-tuple [(speaker_0,speech), (speaker_1,speech), ...]
        The speech is in form of raw HTML string. Sometimes speaker will be NONE,
        which indicates some events happens between dialogs.
        """
        # we do not have to care about titles here - they are supposed to be filtered out
        # already before coming in.
        # Sometimes there are text enclosed by brackets i.e. (xxx) when events happens.
        
        # Before start, sometimes a name is split into 2 <strong> blocks.
        # Merge them for easier processing
        for block in elem_list:
            sub_block = block.getchildren()
            if sub_block is not None:
                if len(sub_block) == 2:
                    if sub_block[0].tag == 'strong' and sub_block[1].tag == 'strong' \
                    and sub_block[1].xpath('preceding-sibling::*[1]')[0] == sub_block[0]:
                        sub_block[0].text += sub_block[1].text
                        sub_block[1].drop_tree()
        
        
        speaker = None
        speech = u''
        list_of_speeches = []
        event_pattern = ur'^\(.+\)$'
        for elem in elem_list:
            #print elem.text_content()
            event_match = re.match(event_pattern, elem.text_content())
            if event_match is not None:
                #An event happens.
                #store previous speech
                if speech != u'' and speech is not None:
                    list_of_speeches.append((speaker,speech))
                    #speaker = None
                    speech = u''
                #store event
                list_of_speeches.append((None,elem.text_content()))
            else:
                # not an event
                # Check if there is a new speaker
                if len(elem.xpath('./strong')) >0 and elem.xpath('./strong')[0].tail is not None:
                    # save last speech
                    if speech != u'':
                        list_of_speeches.append((speaker,speech))
                        speaker = u''
                        speech = u''
                    speaker = elem.xpath('./strong')[0].text_content()
                    elem.xpath('./strong')[0].drop_tree()
                # remove heading ':'
                if elem.text:
                    elem.text = elem.text.lstrip(u':')
                
                # Get rid of <hr> tags (does not always work)
                etree.strip_tags(elem, 'hr')
                speech = u''.join([speech,remove_hr_tags(tostring(elem))])
        if speech != u'':
            list_of_speeches.append((speaker,speech))
            
        #print len(list_of_speeches)
        #for speech in list_of_speeches:
        #    print speech[0]
        #print list_of_speeches[0][1]
        
        return list_of_speeches
        
    
    
    def _get_member_list(self,elem_list):
        """
        Function for parsing member attendance list.
        Given a list of Element objects with member names as text_content(),
        return a list of raw string of the name.
        """
        list_members = []
        name_pattern_e = ur'[A-Z\s-]+HONOURABLE\s(?P<name>[A-Z\s-]+)'
        name_pattern_c = ur'(?P<name>.+)議員'
        for member in elem_list:
            full_name = member.text_content()
            if full_name is not None:
                # Get only the part before comma
                member_str = full_name.split(',')[0]
                # Get rid of all title strings - the name lives after the word 'HONOURABLE'
                if self.language==LANG_EN:
                    name_pattern_match = re.match(name_pattern_e,member_str)
                elif self.language==LANG_CN:
                    name_pattern_match = re.match(name_pattern_c,member_str)
                    
                if name_pattern_match is not None:
                    name_string = name_pattern_match.group('name')
                    list_members.append((name_string,full_name))
                else:
                    logger.error(u'Cannot find the name for string {}'.format(member_str))
                    #store only full name+titles
                    #list_members.append(('',full_name))
            
        return list_members
    
    
    def _build_question_map(self):
        # Map the question numbers to question objects.
        # Since sometimes we may get urgent questions that have their own numbering system,
        # the value in the map maybe a list
        self.question_map = {}
        for question in self.questions:
            if question.number not in self.question_map:
                self.question_map[question.number] = question
            else:
                val = self.question_map[question.number]
                if isinstance(val, list):
                    val.append(question)
                else:
                    self.question_map[question.number] = [val, question]
                    
                    
    def _dump_as_fixture(self):
        """
        Saves the raw html to a fixture for testing
        """
        with open('raw/tests/fixtures/docs/{}_cleaned.html'.format(self.uid), 'wb') as f:
            f.write(etree.tostring(self.tree))


# Common utils
def get_all_hansards(language=-1):
    from raw import models
    objs = models.RawCouncilHansard.objects.order_by('-uid')
    if language == 0:
        return objs.filter(language=models.LANG_BOTH)
    if language == 1:
        return objs.filter(language=models.LANG_CN)
    if language == 2:
        return objs.filter(language=models.LANG_EN)
    return objs.all()


def remove_hr_tags(str_obj):
        """
        Remove all <hr> tags in strings
        """
        hr_pattern = r'<hr>'
        str_obj = re.sub(hr_pattern,'',str_obj)
        return str_obj