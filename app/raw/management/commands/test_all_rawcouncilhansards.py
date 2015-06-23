# -*- coding: utf-8 -*-
"""
This test is to found out if the hansard parser (docs.hansard) 
can parse (formal) RawCouncilHansard instances in the database.

You may run
$ python manage.py test_all_rawcouncilhansards >> testhansard.txt
to write result to to testhansard.txt
"""
    
from django.core.management import BaseCommand
#from raw.docs import hansard
from raw.models.raw import RawCouncilHansard
import logging
from raw.models.constants import LANG_BOTH

logging.disable(logging.CRITICAL)

class Command(BaseCommand):
    help = 'Tests RawCouncilHansard parser'
    
    def handle(self, *args, **options):
        #test all instances with a reply link
        han_list = RawCouncilHansard.objects.exclude(language=LANG_BOTH) #only deal with formal hansard
        #initialize lists
        list_no_parser=[]
        #loop over all questions with reply_link
        for han in han_list:
            parser = han.get_parser()
            if parser is None:
                list_no_parser.append(han.uid)
            
        print(u"Number of Hansards without parser:{}".format(len(list_no_parser)))
        
        print(u"Hansard without parser: {}\n".format(list_no_parser))
