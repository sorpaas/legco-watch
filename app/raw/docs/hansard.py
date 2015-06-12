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
HANSARD_TITLE_e = u'OFFICIAL RECORD OF PROCEEDINGS' #not used
MEMBERS_PRESENT_e = u'MEMBERS PRESENT:'
MEMBERS_ABSENT_e = u'MEMBERS ABSENT:'
PUBLIC_OFFICERS_e = u'PUBLIC OFFICERS ATTENDING:'
CLERKS_e = u'CLERKS IN ATTENDANCE:'
# these sub-sections should be in the main_heading section
# again, should be language-dependent

#<hr></hr> or <hr>

#Main Content
# The PRESIDENT will probably say something before main topic. 
# Sometimes interesting things happen.
TABLED_PAPERS_e = u'TABLING OF PAPERS'
WRITTEN_QUESTIONS_e = u'WRITTEN ANSWERS TO QUESTIONS'
BILLS_e = u'BILLS'
SUSPENSION_e = u'SUSPENSION OF MEETING'

LIST_OF_HEADERS_e = [TABLED_PAPERS_e,WRITTEN_QUESTIONS_e,BILLS_e,SUSPENSION_e]

#<hr></hr> or </hr>

# some footnotes may follow




class CouncilHansard(object):
    """
    Object representing the **formal/translated** Council Hansard document.  This class
    parses the document source and makes all of the individual elements easily accessible
    """
    #Do not make any assumption on what sections will pop up
    SECTION_MAP = OrderedDict()
    
    # Mapping of sections to variables
    SECTION_PARSER = dict({
                     'main_heading':[HANSARD_TITLE_e],      
                     'members_present':[MEMBERS_PRESENT_e],
                     'members_absent':[MEMBERS_ABSENT_e],
                     'public_officers':[PUBLIC_OFFICERS_e],
                     'clerks':[CLERKS_e],
                     'tabled_papers':[TABLED_PAPERS_e],
                     'questions':[WRITTEN_QUESTIONS_e],
                     'bills':[BILLS_e],
                     'suspension':[SUSPENSION_e]
                })
    
    
    def __init__(self, uid, lang, source, *args, **kwargs):
        logger.debug(u'** Parsing hansard {}'.format(uid))
        self.uid = uid
        self.language = lang
        # Raw html string
        self.source = source
        self.tree = None
        # Main Heading
        self.main_heading = None #heading
        # Present List
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
        
        self._headers = [] #store the keys of CouncilHansard.SECTION_MAP here
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
        etree.strip_tags(self.tree, 'strong')
        for xx in self.tree.find_class('pydocx-tab'):
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
        
        # will be dependent of languages - later
        if self.language == LANG_EN:
            LIST_OF_HEADERS = LIST_OF_HEADERS_e
        elif self.language == LANG_CN:
            #LIST_OF_HEADERS = LIST_OF_HEADERS_c
            pass
        elif self.language == LANG_BOTH:
            logger.error(u'The Hansard parser cannot handle Floor Recording:{}'.format(self.uid))
            return None
        
        main_heading = self.tree.xpath('//body/*[count(preceding::hr)=0]')#main title and people attendance
        main_content = self.tree.xpath('//body/*[count(preceding::hr)=1]')#main content of meeting
        main_sidenote = self.tree.xpath('//body/*[count(preceding::hr)=2]')#some sidenotes/appendix (optional?)
        
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
        # Notice that the clerks present section will have some tailing info about the beginning of meeting
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
        
        # Store all keys, and put each section into place
        for key in CouncilHansard.SECTION_MAP.keys():
            self.headers.append(key)

        # Forward each section to its corresponding parser
        
        
    def _parse_main_heading(self,elem_list):  
        """
        Parser for main heading of Hansard.
        Returns an OrderedDict object, with following elements:
        1. The date and time of meeting, as datetime object.
        2. Council member present, as a list of RawMember objects.
        3. Council member absent, as a list of RawMember objects.
        4. Public officers present, as a list of string.
        5. Clerks present, as a list of string.
        """
        LIST_MAIN_HEADING_e = [HANSARD_TITLE_e,MEMBERS_PRESENT_e,MEMBERS_ABSENT_e,PUBLIC_OFFICERS_e,CLERKS_e]
        #LIST_MAIN_HEADING_c = ...
        
        if self.language == LANG_EN:
            LIST_MAIN_HEADING = LIST_MAIN_HEADING_e
        elif self.language == LANG_CN:
            #LIST_MAIN_HEADING = LIST_MAIN_HEADING_c
            pass
        elif self.language == LANG_BOTH:
            logger.error(u'The Hansard parser cannot handle Floor Recording:{}'.format(self.uid))
            return None

        # Again, make no assumption of their order - though quite certain they are identical
        main_heading_map = OrderedDict()
        
        #Put elements into dictionary
        elem_key = ''
        elem_list = []
        for elem in elem_list:
            if elem.text_content() in LIST_MAIN_HEADING:
                # New header found
                if elem_key!='':
                    main_heading_map.update({elem_key:elem_list}) # save the previous part
                elem_key = elem.text_content() #update key
                elem_list = [] #empty list
                continue
            elem_list.append(elem)
        main_heading_map.update({elem_key:elem_list})
        #now the main_heading_map should have 5 keys - do a sanity check?
        
        #
        # The first string should be the date of meeting, e.g.
        # 'Wednesday, 29 April 2015'
        #We can check and see if it matches the RawCouncilHansard object
        
        
        # The second string specifies the time when the council met, e.g.
        #"The Council met at Eleven o'clock"
        
        
        pass
        
    def _parse_members_present(self):
        pass
    
    
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