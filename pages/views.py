from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import GroupCreateForm, ScheduleEntryForm
from .models import Institute, ScheduleEntry, StudyGroup


@login_required
def home(request):
    selected_institute_id = request.GET.get('institute')
    selected_course = _as_int(request.GET.get('course'))
    selected_group_id = request.GET.get('group')
    edit_entry_id = request.GET.get('edit')
    group_form = GroupCreateForm()
    entry_form = ScheduleEntryForm()

    selected_institute = Institute.objects.filter(id=selected_institute_id).first()
    selected_group = StudyGroup.objects.select_related('institute').filter(id=selected_group_id).first()

    if selected_group:
        selected_institute = selected_group.institute
        selected_course = selected_group.course

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_group':
            group_form = GroupCreateForm(request.POST)
            if group_form.is_valid():
                institute, _created = Institute.objects.get_or_create(
                    name=group_form.cleaned_data['institute_name'].strip()
                )
                group, _created = StudyGroup.objects.get_or_create(
                    institute=institute,
                    course=group_form.cleaned_data['course'],
                    name=group_form.cleaned_data['group_name'].strip(),
                )
                messages.success(request, 'Группа добавлена.')
                return redirect(_schedule_url(group=group))

        elif action in {'create_entry', 'update_entry'}:
            selected_group = get_object_or_404(StudyGroup, id=request.POST.get('group'))
            entry = None
            if action == 'update_entry':
                entry = get_object_or_404(
                    ScheduleEntry,
                    id=request.POST.get('entry'),
                    group=selected_group,
                )
            entry_form = ScheduleEntryForm(request.POST, instance=entry)
            if entry_form.is_valid():
                schedule_entry = entry_form.save(commit=False)
                schedule_entry.group = selected_group
                schedule_entry.save()
                messages.success(request, 'Занятие сохранено.')
                return redirect(_schedule_url(group=selected_group))

        elif action == 'delete_entry':
            selected_group = get_object_or_404(StudyGroup, id=request.POST.get('group'))
            entry = get_object_or_404(
                ScheduleEntry,
                id=request.POST.get('entry'),
                group=selected_group,
            )
            entry.delete()
            messages.success(request, 'Занятие удалено.')
            return redirect(_schedule_url(group=selected_group))

    if selected_group:
        selected_institute = selected_group.institute
        selected_course = selected_group.course

    edit_entry = None
    if selected_group and edit_entry_id:
        edit_entry = ScheduleEntry.objects.filter(id=edit_entry_id, group=selected_group).first()
        if edit_entry and request.method != 'POST':
            entry_form = ScheduleEntryForm(instance=edit_entry)

    institutes = Institute.objects.all()
    courses = []
    groups = StudyGroup.objects.none()
    schedule_entries = ScheduleEntry.objects.none()

    if selected_institute:
        courses = (
            StudyGroup.objects
            .filter(institute=selected_institute)
            .order_by('course')
            .values_list('course', flat=True)
            .distinct()
        )
        groups = StudyGroup.objects.filter(institute=selected_institute)
        if selected_course is not None:
            groups = groups.filter(course=selected_course)

    if selected_group:
        schedule_entries = selected_group.schedule_entries.all()

    context = {
        'institutes': institutes,
        'courses': courses,
        'groups': groups,
        'selected_institute': selected_institute,
        'selected_course': selected_course,
        'selected_group': selected_group,
        'schedule_entries': schedule_entries,
        'group_form': group_form,
        'entry_form': entry_form,
        'edit_entry': edit_entry,
    }
    return render(request, 'pages/home.html', context)


def _schedule_url(group):
    return (
        f'{reverse("home")}'
        f'?institute={group.institute_id}'
        f'&course={group.course}'
        f'&group={group.id}'
    )


def _as_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except ValueError:
        return None
