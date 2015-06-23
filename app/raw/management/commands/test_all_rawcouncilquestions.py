# -*- coding: utf-8 -*-
"""
This test is to found out if all fields of RawCouncilQuestion instances
in the current database are assigned by parser (docs.question) upon view request.
It does not cover 'old' questions before year 06-07, since they do not have reply link.
Those old questions should be tested by hansard parser (in future).

You may run
$ python manage.py test_all_rawcouncilquestions >> testq.txt
to write to testq.txt
"""
    
from django.core.management import BaseCommand
#from raw.docs import question
from raw.models.raw import RawCouncilQuestion
import logging

logging.disable(logging.CRITICAL)

class Command(BaseCommand):
    help = 'Tests RawCouncilQuestion parser'
    
    def handle(self, *args, **options):
        #test all instances with a reply link
        q_list = RawCouncilQuestion.objects.exclude(reply_link='')
        #initialize lists
        list_no_parser=[]
        list_no_asker=[]
        list_no_repliers=[]
        list_no_title=[]
        list_no_question=[]
        list_no_reply=[]
        #loop over all questions with reply_link
        for q in q_list:
            if q.reply_link[-3:]=='htm':
                parser = q.get_parser()
                if parser is None:
                    list_no_parser.append(q.uid)
                else:
                    if parser.asker is None:
                        list_no_asker.append(q.uid)
                    if parser.repliers is None:
                        list_no_repliers.append(q.uid)
                    if parser.question_title is None:
                        list_no_title.append(q.uid)
                    if parser.question_content is None:
                        list_no_question.append(q.uid)
                    if parser.reply_content is None:
                        list_no_reply.append(q.uid)
            else:
                #no need to test non-htm files (e.g. PDF) here
                pass
            
        print("Number of questions without parser:{}".format(len(list_no_parser)))
        print("Number of questions without asker:{}".format(len(list_no_asker)))
        print("Number of questions without repliers:{}".format(len(list_no_repliers)))
        print("Number of questions without question_title:{}".format(len(list_no_title)))
        print("Number of questions without question content:{}".format(len(list_no_question)))
        print("Number of questions without reply content:{}\n".format(len(list_no_reply)))
        
        print("Questions without parser: {}\n".format(list_no_parser))
        print("Questions without asker: {}\n".format(list_no_asker))
        print("Questions without repliers: {}\n".format(list_no_repliers))
        print("Questions without question_title: {}\n".format(list_no_title))
        print("Questions without question content: {}\n".format(list_no_question))
        print("Questions without reply content: {}\n".format(list_no_reply))