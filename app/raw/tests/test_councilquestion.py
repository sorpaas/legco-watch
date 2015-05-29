#!/usr/bin/python
# -*- coding: utf-8 -*-

# Tests for RawCouncilQuestion object

from django.test import TestCase
import logging
from raw.docs import question
from raw.models.raw import RawCouncilQuestion

logging.disable(logging.CRITICAL)

class RawCouncilQuestionTest(TestCase):
    
    def setUp(self):
        pass