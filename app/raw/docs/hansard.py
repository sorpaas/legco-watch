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

logger = logging.getLogger('legcowatch-docs')

# Global header patterns. All are <strong> and upper case. Some
HANSARD_TITLE_e = 'OFFICIAL RECORD OF PROCEEDINGS'
HANSARD_TITLE_c = u'會議過程正式紀錄'
MEMBERS_PRESENT_e = 'MEMBERS PRESENT:'
MEMBERS_PRESENT_c = u'出席議員:'
MEMBERS_ABSENT_e = 'MEMBERS ABSENT:'
MEMBERS_ABSENT_c = u'缺席議員:'
PUBLIC_OFFICERS_e = 'PUBLIC OFFICERS ATTENDING:'
PUBLIC_OFFICERS_c = u'出席政府官員:'
CLERKS_e = 'CLERKS IN ATTENDANCE:'
CLERKS_c = u'列席秘書:'
# these sub-sections should be in the main_heading section
# again, should be language-dependent

#<hr></hr> or <hr>

#Main Content
# The PRESIDENT will probably say something before main topic. 
# Sometimes interesting things happen.
TABLED_PAPERS_e = 'TABLING OF PAPERS'
TABLED_PAPERS_c = u'提交文件'
WRITTEN_QUESTIONS_e = 'WRITTEN ANSWERS TO QUESTIONS'
WRITTEN_QUESTIONS_c = u'議員質詢的書面答覆'
BILLS_e = 'BILLS'
BILLS_c = u'法案'

SUSPENSION_e = 'SUSPENSION OF MEETING'
SUSPENSION_c = u'暫停會議'
#NEXT_MEETING_e = 'NEXT MEETING'

LIST_OF_HEADERS_e = [TABLED_PAPERS_e,WRITTEN_QUESTIONS_e,BILLS_e,SUSPENSION_e]
LIST_OF_HEADERS_c = [TABLED_PAPERS_c,WRITTEN_QUESTIONS_c,BILLS_c,SUSPENSION_c]
#<hr></hr> or </hr>

# some footnotes may follow


class CouncilHansard(object):
    """
    Object representing the **formal/translated** Council Hansard document.  This class
    parses the document source and makes all of the individual elements easily accessible
    """
    #Do not make any assumption on what sections will pop up
    SECTION_MAP = OrderedDict()
    
    
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
        # Present List
        self.president = None
        self.members_present = None
        self.members_absent = None
        self.public_officers = None
        self.clerks = None
        ## an <hr></hr> line separate heading and content ##
        # Main Content
        # before TABLING OF PAPERS the President will summon Members.
        self.tabled_papers = None
        self.questions = None
        self.question_map = None
        self.bills = None
        self.suspension = None #sometimes contain extra info as well as next meeting schedule.
        ## an <hr></hr> line separate content and footnote etc.
        self.other = None
        
        self.sections = [] #store the keys of CouncilHansard.SECTION_MAP here
        
        self._load()
        self._clean()
        self._parse()
    
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
        
        # May need this for Chinese characters
        #self.source = self.source.decode('hkscs',errors='ignore')
        
        # Use the lxml cleaner
        cleaner = Cleaner()
        parser = HTMLParser(encoding='utf-8')
        # Finally, load the cleaned string to an ElementTree
        self.tree = cleaner.clean_html(lxml.html.fromstring(to_string(self.source), parser=parser))
        # self.tree = lxml.html.fromstring(to_string(self.source))
        
    def _clean(self):
        """
        Removes some of extraneous tags to make parsing easier
        """
        #etree.strip_tags(self.tree, 'strong')
        for xx in self.tree.find_class('pydocx-tab'):
            xx.drop_tag()
        
        for xx in self.tree.find_class('pydocx-caps'):
            xx.text = xx.text_content().upper()
            xx.drop_tag()
            
            
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

        #elems = self.tree.xpath('.//body/*')
        #main_heading = self.tree.xpath('//body/p[position()<4]') # first 3 elements must be heading
        #main_content = self.tree.xpath('//body/*[position()>3]') #main content afterward. A list of Elements
        
        #main_content = self.tree.xpath('//body/*')
        
        if self.language == LANG_EN:
            LIST_OF_HEADERS = LIST_OF_HEADERS_e
        elif self.language == LANG_CN:
            LIST_OF_HEADERS = LIST_OF_HEADERS_c
        else:
            logger.error(u'The Hansard parser cannot handle Floor Recording:{}'.format(self.uid))
            return None
        logger.warning(u'Language: {}'.format(self.language))
        
        
        main_heading = self.tree.xpath('//body/*[count(preceding::hr)=0]')#main title and people attendance
        main_content = self.tree.xpath('//body/*[count(preceding::hr)=1]')#main content of meeting
        main_sidenote = self.tree.xpath('//body/*[count(preceding::hr)=2]')#some sidenotes/appendix (optional?)
        
        #shut up and take my main_heading
        self._parse_main_heading(main_heading)
        
        ### main_content: ###
        # Strategy: we do not make any assumption on the order of occurrence of each section.
        # We will loop over all Elements of main_content, checking for headers - if a <strong> tag
        # is present, is upper case, and the text matches one of the element in LIST_OF_HEADERS, 
        # we remember it and append all following Elements to a list, until another header is found. 
        # In this case, we update the CouncilHansard.SECTION_MAP with the corresponding key(header name) and 
        # value(list of Elements).
        # Afterwards, we will pass these sections on for further processing.
        # Remember: do not only save text_content() to the list since we need the tags and formatting.
        
        # The first element must match MEMBERS_PRESENT_x - do a sanity check.
        #if main_content[0].xpath('./strong') is None or main_content[0].text_content()!=LIST_OF_HEADERS[0]:
        #    logger.error(u'The first element should be HANSARD_TITLE. Receive "{}" instead'.format(main_content[0].text_content()))
        #    return None
        
        # Without assuming anything, loop through all elements for potential headers
        # Note that there are some info about the beginning of meeting (after <hr>)
        elem_key = 'BEFORE MEETING'
        elem_list = []
        
        for part in main_content:
            if part.xpath('./strong') is not None and part.text_content().isupper():
                #Potential header
                potential_header = part.text_content()
                if potential_header in LIST_OF_HEADERS:
                    # New header found
                    CouncilHansard.SECTION_MAP.update({elem_key:elem_list}) # save the previous part
                    elem_key = potential_header #update key
                    elem_list = [] #empty list
                    continue
            elem_list.append(part)
        CouncilHansard.SECTION_MAP.update({elem_key:elem_list})#do not forget the last section
        
        
        # Useful scripts:
        # 1. look into a section
        #for part in CouncilHansard.SECTION_MAP[MEMBER_PRESENT_e]:
            #print(part.text_content())
        # 2. Check what headers were found and their order
        #for key in CouncilHansard.SECTION_MAP.keys():
            #print(key)
        
        # Store all keys in self.headers for easy reference
        for key in CouncilHansard.SECTION_MAP.keys():
            self.sections.append(key)

        # Forward each section to its corresponding parser
        lang_char = 'e' if self.language==LANG_EN else 'c'
        for section in CouncilHansard.SECTION_MAP.keys():
            logger.info(u'Parsing {} section for Hansard: {}'.format(section, self.uid))
            if section == 'BEFORE MEETING':
                self._parse_before_meeting(CouncilHansard.SECTION_MAP[section])
            elif section == eval('TABLED_PAPERS_{}'.format(lang_char)):
            #elif section == globals()['TABLED_PAPERS_{}'.format(lang_char)]:
                self._parse_tabled_papers(CouncilHansard.SECTION_MAP[section])
                
                
                
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
            
        #other languages ('b') should have raised an error in _parse, so no else branch here
        
        #dictionary, key = string to match, value = the key to use in main_heading_map
        DICT_MAIN_HEADING = dict(
                             {
                              HANSARD_TITLE:'HANSARD_TITLE',
                             MEMBERS_PRESENT:'MEMBERS_PRESENT',
                             MEMBERS_ABSENT:'MEMBERS_ABSENT',
                             PUBLIC_OFFICERS:'PUBLIC_OFFICERS',
                             CLERKS:'CLERKS'
                                }
                             )
        #print(DICT_MAIN_HEADING)
        main_heading_map = dict()
        
        #Put elements into dictionary
        elem_key = ''
        elem_val = []
        for elem in heading_list:
            if elem.text_content() in DICT_MAIN_HEADING.keys():
                # New header found
                if elem_key=='':
                    elem_key = DICT_MAIN_HEADING[elem.text_content()] #update key
                    continue
                main_heading_map.update({elem_key:elem_val}) # save the previous part
                elem_key = DICT_MAIN_HEADING[elem.text_content()] #update key
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
            officer_pattern_c = ur'(?P<position>.*局長)(?P<name>.*)'
            if self.language==LANG_EN:
                #split the odd and even entries
                officers_name_str = public_officers_pres[::2]
                officers_position_str = public_officers_pres[1::2]
                if len(officers_name_str)!=len(officers_position_str):
                    logger.error(u'Number of officers does not match number of positions- {}:{}'.format(len(officers_name_str),(officers_position_str)))
                    self.public_officers = None
                else:
                    #officers are not in member list (RawMember), so only get their name and title
                    officers_name=[elem.text_content().split(',')[0] for elem in officers_name_str]
                    officers_title=[elem.text_content().split(',',1)[1] for elem in officers_name_str]
                    #officers_title = ', '.join(officers_title)
                    officers_position=[elem.text_content() for elem in officers_position_str]
                    self.public_officers = zip(officers_name,officers_title,officers_position)
            elif self.language==LANG_CN:
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
                        tmp_list.append((officers_name,officers_title,''))
                self.public_officers = tmp_list
                
        #5. Finally, the clerks in attendance
        #the format in harsard is: name, title(s)[optional],position
        #so similar to officers, return a list of 3-tuple
        clerks = main_heading_map['CLERKS']
        clerk_list = []
        chinese_pattern_re = ur'(?P<title>.*秘書長)(?P<name>.*)'
        for elem in clerks:
            if elem.text_content()!='': #sometimes a tailing '' (perhaps due to <hr>?) at the end
                if self.language==LANG_EN:
                    clerk_str = elem.text_content().rsplit(',',1)
                    # not observed yet, but multiple titles may occur
                    clerk_list.append((clerk_str[0],clerk_str[1]))
                elif self.language==LANG_CN:
                    match = re.match(chinese_pattern_re,elem.text_content())
                    if match is not None:
                        clerk_list.append((match.group('name'),match.group('title')))
                    else:
                        logger.warn(u'Cannot parse a clerk string: {}'.format(elem.text_content()))
                        continue
        self.clerks = clerk_list
        #Done.
    
    def _parse_before_meeting(self,elem_list):
        pass
    
    def _parse_tabled_papers(self,elem_list):
        pass
    
    # Functions
    def _get_member_list(self,elem_list):
        """
        Given a list of Element objects with member names as text_content(),
        return a list of raw string of the name.
        """
        list_members = []
        name_pattern_e = ur'[A-Z\s-]+HONOURABLE\s(?P<name>[A-Z\s-]+)'
        name_pattern_c = ur'(?P<name>.+)議員'
        for member in elem_list:
            full_name = member.text_content()
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
                #store only full name+titles
                logger.warn(u'Cannot find the name for string {}'.format(member_str))
                list_members.append(('',full_name))
            
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