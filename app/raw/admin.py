from django.contrib import admin
from raw.models import ScrapeJob, \
    RawCouncilAgenda, \
    RawMember, RawScheduleMember, \
    RawCommittee, RawCommitteeMembership, RawMeetingCommittee, RawMeeting, \
    RawCouncilQuestion, \
    RawCouncilHansard
from raw.models import ParsedPerson, ParsedMembership, ParsedCommittee, ParsedCommitteeMembership, \
    ParsedCouncilMeeting, ParsedQuestion
    
from raw.models.parsed import Override

admin.site.register(ScrapeJob)
admin.site.register(RawCouncilAgenda)
admin.site.register(RawMember)
admin.site.register(RawScheduleMember)
admin.site.register(RawCommittee)
admin.site.register(RawCommitteeMembership)
admin.site.register(RawMeetingCommittee)
admin.site.register(RawMeeting)
admin.site.register(RawCouncilQuestion)
admin.site.register(RawCouncilHansard)


admin.site.register(ParsedPerson)
admin.site.register(ParsedMembership)
admin.site.register(ParsedCommittee)
admin.site.register(ParsedCommitteeMembership)
admin.site.register(ParsedCouncilMeeting)
admin.site.register(ParsedQuestion)

admin.site.register(Override)
