from django.contrib import admin
from raw.models import ScrapeJob, \
    RawCouncilAgenda, \
    RawMember, RawScheduleMember, \
    RawCommittee, RawCommitteeMembership, RawMeetingCommittee, RawMeeting, \
    RawCouncilQuestion, \
    RawHansardAgenda, RawHansardMinutes, RawHansardFloorRecord, RawHansardFormalRecord, \
    Override


admin.site.register(ScrapeJob)
admin.site.register(RawCouncilAgenda)
admin.site.register(RawMember)
admin.site.register(RawScheduleMember)
admin.site.register(RawCommittee)
admin.site.register(RawCommitteeMembership)
admin.site.register(RawMeetingCommittee)
admin.site.register(RawMeeting)
admin.site.register(RawCouncilQuestion)
admin.site.register(RawHansardAgenda)
admin.site.register(RawHansardMinutes)
admin.site.register(RawHansardFloorRecord)
admin.site.register(RawHansardFormalRecord)
admin.site.register(Override)