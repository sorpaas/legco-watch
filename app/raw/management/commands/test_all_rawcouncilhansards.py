# -*- coding: utf-8 -*-
"""
This test is to found out if the hansard parser (docs.hansard) 
can parse (formal) RawCouncilHansard instances in the database.

You may run
$ python manage.py test_all_rawcouncilhansards >> testhansard.txt
to write result to to testhansard.txt
"""
    
from django.core.management import BaseCommand
from raw.models.raw import RawCouncilHansard
import logging
from raw.models.constants import LANG_EN

logging.disable(logging.CRITICAL)

class Command(BaseCommand):
    help = 'Tests RawCouncilHansard parser'
    
    def handle(self, *args, **options):
        ### Test for parser returning None ###
        #test all Formal Hansards
        #initialize lists
        list_exception = []
        list_no_counterpart = []
        list_no_src = []
        list_no_parser=[]
        list_mismatch_tabled_paper_section = []
        list_mismatch_legislation_papers = []
        list_mismatch_other_papers = []
        list_mismatch_oral = []
        list_mismatch_written = []
        han_list = RawCouncilHansard.objects.filter(language__exact=LANG_EN)
        print(u"Total number of hansards: {}\n".format(len(han_list)))
        for han_en in han_list:
            han_cn = han_en.get_lang_counterpart()
            if han_cn is None:
                # nothing to compare with
                list_no_counterpart.append(han_en.uid)
                continue
            elif han_cn.get_source() is None:
                list_no_src.append(han_cn.uid)
                continue
            elif han_en.get_source() is None:
                list_no_src.append(han_en.uid)
                continue
            else:
                # Sometimes source cannot be loaded (usually images)
                try:
                    parser_en = han_en.get_parser()
                except:
                    list_exception.append(han_en.title)
                    continue 
                try:
                    parser_cn = han_cn.get_parser()
                except:
                    list_exception.append(han_cn.title)
                    continue
                
                ### 1. Test for parser returning None ###
                if parser_en is None or parser_cn is None:
                    # Cannot compare against each other.
                    if parser_en is None:
                        list_no_parser.append(han_en.uid)
                    if parser_cn is None:
                        list_no_parser.append(han_cn.uid)
                    continue
                else:
                    ### 2. Test if parsers return same number of tabled papers in both languages ###
                    if parser_en.tabled_legislation is not None:
                        # sometimes the section is not available
                        try:
                            if len(parser_en.tabled_legislation) != len(parser_cn.tabled_legislation):
                                list_mismatch_legislation_papers.append(han_en.uid)
                            if len(parser_en.tabled_other_papers) != len(parser_cn.tabled_other_papers):
                                list_mismatch_other_papers.append(han_en.uid)
                        except:
                            list_mismatch_tabled_paper_section.append(han_en.uid)
                            
                    ### 3. Test if number of oral/written questions are identical ###
                    if parser_en.oral_questions is not None:
                        try:
                            if len(parser_en.oral_questions) != len(parser_cn.oral_questions):
                                list_mismatch_oral.append(han_en.uid)
                        except:
                            pass
                    if parser_en.written_questions is not None:
                        try:
                            if len(parser_en.written_questions) != len(parser_cn.written_questions):
                                list_mismatch_written.append(han_en.uid)
                        except:
                            pass
        
        print(u"Number of Hansards failed to load:{}".format(len(list_exception)))
        print(u"Hansard not loaded: {}\n".format(list_exception))
        print(u"Number of Hansards without parser:{}".format(len(list_no_parser)))
        print(u"Hansard without parser: {}\n".format(list_no_parser))
        print(u"Cannot find language counterpart for hansard:{}\n".format(list_no_counterpart))
        print(u"Number of Hansards without source:{}".format(len(list_no_src)))
        print(u"Hansard without source: {}\n".format(list_no_src))
        print(u"Number of Hansards with mismatch number of legislation paper:{}".format(len(list_mismatch_legislation_papers)))
        print(u"Hansard with mismatch number of legislation paper:{}\n".format(list_mismatch_legislation_papers))
        print(u"Number of Hansards with mismatch number of other paper:{}".format(len(list_mismatch_other_papers)))
        print(u"Hansard with mismatch number of other paper:{}\n".format(list_mismatch_other_papers))
        print(u"Number of Hansards with mismatch number of oral question:{}".format(len(list_mismatch_oral)))
        print(u"Hansard with mismatch number of oral question:{}\n".format(list_mismatch_oral))
        print(u"Number of Hansards with mismatch number of written question:{}".format(len(list_mismatch_written)))
        print(u"Hansard with mismatch number of written question:{}\n".format(list_mismatch_written))