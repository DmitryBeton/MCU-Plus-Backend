from django.contrib import admin

from .models import Institute, ScheduleEntry, StudyGroup


@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'institute']
    list_filter = ['institute', 'course']
    search_fields = ['name', 'institute__name']


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ['date', 'start_time', 'end_time', 'subject', 'group', 'room']
    list_filter = ['date', 'group__institute', 'group__course', 'group']
    search_fields = ['subject', 'teacher', 'room', 'group__name']
