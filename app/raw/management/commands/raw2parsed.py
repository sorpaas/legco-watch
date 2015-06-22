# -*- coding: utf-8 -*-

from django.core.management import BaseCommand
import raw.models
from raw.models import ParsedCommittee, ParsedCommitteeMembership, ParsedCouncilMeeting, ParsedMembership, ParsedPerson, ParsedPerson, ParsedQuestion
import logging

logging.disable(logging.CRITICAL)

class Command(BaseCommand):
    help = 'Create parsed models from their raw correspondences'
    
    def handle(self, *args, **options):
        raw.models.ParsedCommittee.objects.populate()
        raw.models.ParsedPerson.objects.populate()
        raw.models.ParsedMembership.objects.populate()
        raw.models.ParsedCommitteeMembership.objects.populate()
        raw.models.ParsedCouncilMeeting.objects.populate()
        #raw.models.ParsedQuestion.objects.populate()