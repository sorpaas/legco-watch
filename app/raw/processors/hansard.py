# -*- coding: utf-8 -*-
##################################

##########Depreciated#############

####See library_hansard instead###

##################################
"""
Processor for Hansard
"""
import logging
from urlparse import urljoin
import re
from raw.models import RawHansardAgenda, RawHansardMinutes, RawHansardFloorRecord, RawHansardFormalRecord, LANG_BOTH, LANG_EN, LANG_CN
from raw.processors.base import BaseProcessor, file_wrapper
from django.utils.timezone import now

logger = logging.getLogger('legcowatch')

# keys are fields in the jsonlines item, values are the fields in the model object
field_map = {
# note the 'raw_date' field may contain extra information, e.g. type, time etc
# all hansard models share the 2 fields below
    'date': 'raw_date',
    'source_url': 'crawled_from',
}

class HansardObjectProcessor(BaseProcessor):
    def process(self):
        logger.info("Processing file {}".format(self.items_file_path))
        counter = 0
        for item in file_wrapper(self.items_file_path):
            if item['type'] and item['file_urls']: # if we downloaded something
                counter += 1
                uid, main_type = self._generate_uid(item)
                #get/create the object
                if main_type == 'agenda':
                    obj, created = RawHansardAgenda.objects.get_or_create(uid=uid)
                elif main_type == 'minutes':
                    obj, created = RawHansardMinutes.objects.get_or_create(uid=uid)
                elif main_type == 'floor':
                    obj, created = RawHansardFloorRecord.objects.get_or_create(uid=uid)
                elif main_type == 'hansard':
                    obj, created = RawHansardFormalRecord.objects.get_or_create(uid=uid)
                else:
                    logger.warning('Unknown Harsard type:{}'.format(main_type))
                
                #bookkeeping
                if created:
                    self._count_created += 1
                else:
                    self._count_updated += 1
                
                # Fill in model fields
                try:
                    # Fill in the last parsed and last crawled values
                    if self.job is not None:
                        obj.last_crawled = self.job.completed
                    obj.last_parsed = now()
                    
                    # Fill in the items that can be copied directly
                    for k, v in field_map.items():
                        val = item.get(k, None)
                        setattr(obj, v, val)
                    
                    # Fill in language field
                    lang = uid.split('-')[-1]
                    if lang=='e':
                        obj.language = LANG_EN
                    elif lang=='c':
                        obj.language = LANG_CN
                    elif lang=='ec':
                        obj.language = LANG_BOTH
                    
                    # Fill in URL link to file
                    obj.url = item['file_urls'][0]
                    
                    # Fill in the local path
                    try:
                        obj.local_filename = item['files'][0]['path']
                    except IndexError:
                        logger.warn(u'Could not get local path for Hansard object {} from date {}'.format(item['type'], item['date']))
                
                    # Finally save
                    obj.save()
                    
                except (KeyError, RuntimeError) as e:
                    self._count_error += 1
                    logger.warn(u'Could not process Hansard object {} from date {}'.format(item['type'], item['date']))
                    logger.warn(unicode(e))
                    continue
            else:
                logger.warning('The Harsard type is not specified:{}'.format(item))
                
        logger.info("{} items processed, {} created, {} updated".format(counter, self._count_created, self._count_updated))
    
    def _generate_uid(self,item):
        """
        Returns a uid for an item.
        Common method for all HansardObjects.
        Note: 1.the file links for different terms of LegCo are different!
              2.we do not deal with old (pre-1997) hansard in this processor.
              
        EXAMPLES:
        Agenda
        2012 - 2016: http://www.legco.gov.hk/yr14-15/english/counmtg/agenda/cm20141015.htm
        2008 - 2012: http://www.legco.gov.hk/yr11-12/chinese/counmtg/agenda/cm20111012.htm
        2004 - 2008: http://www.legco.gov.hk/yr07-08/english/counmtg/agenda/cmtg1219.htm
        2000 - 2004: http://www.legco.gov.hk/yr03-04/chinese/counmtg/agenda/cmtg1015.htm
        1998 - 2000: http://www.legco.gov.hk/yr99-00/chinese/counmtg/agenda/cord2010.htm
        1997 - 1998: http://www.legco.gov.hk/yr97-98/chinese/counmtg/ord_ppr/cord0704.htm
        pre  7/1997: (called Order Paper) 
                     http://www.legco.gov.hk/yr95-96/english/lc_sitg/ord_ppr/ord0506.htm
        Note: from what I can access, the earliest agenda dated back to 1995-1996 session
        
        Minutes
        2012 - 2016: http://www.legco.gov.hk/yr14-15/english/counmtg/minutes/cm20141015.pdf
        2008 - 2012: http://www.legco.gov.hk/yr11-12/chinese/counmtg/minutes/cm20111012.pdf
        2004 - 2008: http://www.legco.gov.hk/yr07-08/english/counmtg/minutes/cm080227.pdf
        2000 - 2004: http://www.legco.gov.hk/yr03-04/chinese/counmtg/minutes/cm031016.pdf
        1998 - 2000: http://www.legco.gov.hk/yr99-00/chinese/counmtg/minutes/mn201099.htm
        1997 - 1998: http://www.legco.gov.hk/yr97-98/chinese/counmtg/minutes/cmin0804.htm
        pre  7/1997: http://www.legco.gov.hk/yr95-96/english/lc_sitg/minutes/min0407.htm
                     http://www.legco.gov.hk/yr95-96/english/lc_sitg/minutes/min1701.htm
                     
        Formal Records
        2012 - 2016: http://www.legco.gov.hk/yr14-15/english/counmtg/hansard/cm20141015-translate-e.pdf
        2008 - 2012: http://www.legco.gov.hk/yr11-12/chinese/counmtg/hansard/cm1012-translate-c.pdf
        2004 - 2008: http://www.legco.gov.hk/yr07-08/english/counmtg/hansard/cm0220-translate-e.pdf
        2000 - 2004: http://www.legco.gov.hk/yr03-04/chinese/counmtg/hansard/cm1016ti-translate-c.pdf
        1998 - 2000: http://www.legco.gov.hk/yr99-00/chinese/counmtg/hansard/991020fc.pdf
        1997 - 1998: http://www.legco.gov.hk/yr97-98/chinese/counmtg/hansard/980408fc.doc
        pre  7/1997: http://www.legco.gov.hk/yr95-96/english/lc_sitg/hansard/960710fe.doc 
                     http://www.legco.gov.hk/yr95-96/english/lc_sitg/hansard/han1511.htm
                     
        Floor Records
        2012 - 2016: http://www.legco.gov.hk/yr14-15/chinese/counmtg/floor/cm20150326a-confirm-ec.pdf
        2008 - 2012: http://www.legco.gov.hk/yr11-12/chinese/counmtg/floor/cm1012-confirm-ec.pdf
        2004 - 2008: http://www.legco.gov.hk/yr07-08/chinese/counmtg/floor/cm0305-confirm-ec.pdf
        2000 - 2004: http://www.legco.gov.hk/yr03-04/chinese/counmtg/floor/cm1016ti-confirm-c.pdf
        1998 - 2000: http://www.legco.gov.hk/yr99-00/chinese/counmtg/floor/991020ca.pdf
        1997 - 1998: http://www.legco.gov.hk/yr97-98/chinese/counmtg/floor/980408cd.doc
        pre  7/1997: http://www.legco.gov.hk/yr95-96/chinese/lc_sitg/floor/960110cd.doc
                     http://www.legco.gov.hk/yr95-96/chinese/lc_sitg/floor/960207cd.doc
        
        
        """
        # Get language. We may override this value later
        if item['file_urls'][0].split('/')[4] == 'english':
                lang = 'e'
        elif item['file_urls'][0].split('/')[4] == 'chinese':
                lang = 'c'
        else:
            raise RuntimeError(u'Cannot get the language for url: {}'.format(item['file_urls']))
            
        #get the year - note the difference in format between English and Chinese
        yr = item['date'][-4:] #if lang=='e' else item['date'][:4] #not used
        
        lang = '' #will fill in later
        file_name = item['file_urls'][0].split('/')[-1].split('.')[0]
        
        # Use regex to parse the date (year, month and day)
        if len(file_name.split('-')) == 3:
            #must be a new record
            pattern_record_new = ur'cm(?P<md>\d{4,8})[a-z]{0,2}-(?P<record_type>\S+)-(?P<lang>[a-z]{1,2})'
            record_match = re.match(pattern_record_new,file_name)
            if record_match:
                md = record_match.group('md')[-4:] #only need the month and day
                #record type not needed, we knew already
                lang = record_match.group('lang')
            else:
                raise RuntimeError(u'Unrecognized file name: {} from {}'.format(file_name,item['file_urls']))
        elif len(file_name.split('-')) == 1:
            #can be anything
            pattern_any = ur'[a-z]{0,4}(?P<md>\d{4,6})[a-z]{0,2}'
            record_match = re.match(pattern_any,file_name)
            if record_match:
                md = record_match.group('md')[-4:] #only need the month and day
            else:
                raise RuntimeError(u'Unrecognize file name: {} from {}'.format(file_name,item['file_urls']))
        else:
            raise RuntimeError(u'File name is not of length 1 or 3.')
        
        # date in uid format
        date_uid = yr + md
            
        # get type (agenda | minutes | floor | formal)
        main_type = item['file_urls'][0].split('/')[-2]
        
        """
        UIDs for hansard objects are of the form 'hansard_agenda-20131009-e' (hansard_<type>-<yyyymmdd>-<lang>)
        <type> = agenda | minutes | floor | formal
        <lang> = e | c | ec
        """
        if main_type == 'agenda' or main_type == 'ord_ppr':
            main_type = 'agenda'
            return (u'hansard_agenda-{}-{}'.format(date_uid,lang), main_type)
        elif main_type == 'minutes':
            return (u'hansard_minutes-{}-{}'.format(date_uid,lang), main_type)
        elif main_type == 'hansard':
            return (u'hansard_formal-{}-{}'.format(date_uid,lang), main_type)
        elif main_type == 'floor':
            return (u'hansard_floor-{}-{}'.format(date_uid,lang), main_type)
        else:
            raise RuntimeError(u'Unknown Hansard object type: {} for url={}'.format(main_type,item['file_urls']))