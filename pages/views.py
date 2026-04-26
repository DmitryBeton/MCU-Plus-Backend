from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import GroupCreateForm, ScheduleEntryForm, ScheduleJsonUploadForm
from .importers import import_schedule_file
from .models import Institute, ScheduleEntry, StudyGroup


@login_required
def home(request):
    selected_institute_id = _as_int(request.GET.get('institute'))
    selected_course = _as_int(request.GET.get('course'))
    selected_group_id = _as_int(request.GET.get('group'))
    edit_entry_id = _as_int(request.GET.get('edit'))
    view_mode = request.GET.get('view')
    if view_mode not in {'list', 'table'}:
        view_mode = 'list'
    selected_start_date = _parse_iso_date(request.GET.get('start_date'))
    selected_end_date = _parse_iso_date(request.GET.get('end_date'))
    group_form = GroupCreateForm()
    entry_form = ScheduleEntryForm()
    upload_form = ScheduleJsonUploadForm()

    selected_institute = Institute.objects.filter(id=selected_institute_id).first()
    selected_group = StudyGroup.objects.select_related('institute').filter(id=selected_group_id).first()

    if selected_group:
        selected_institute = selected_group.institute
        selected_course = selected_group.course

    if request.method != 'POST' and selected_institute:
        upload_form.fields['institute_name'].initial = selected_institute.name

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

        elif action == 'import_schedule':
            upload_form = ScheduleJsonUploadForm(request.POST, request.FILES)
            if upload_form.is_valid():
                try:
                    default_institute_name = (
                        upload_form.cleaned_data.get('institute_name')
                        or (selected_institute.name if selected_institute else None)
                    )
                    summary = import_schedule_file(
                        upload_form.cleaned_data['file'],
                        default_institute_name=default_institute_name,
                    )
                except ValidationError as error:
                    messages.error(request, ' '.join(error.messages))
                else:
                    messages.success(
                        request,
                        (
                            'Импорт завершен: '
                            f'создано занятий {summary.entries_created}, '
                            f'обновлено {summary.entries_updated}, '
                            f'новых групп {summary.groups_created}.'
                        ),
                    )
                    return redirect('home')

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
                return redirect(_schedule_url(
                    group=selected_group,
                    view_mode=request.POST.get('view'),
                    start_date=request.POST.get('start_date'),
                    end_date=request.POST.get('end_date'),
                ))

        elif action == 'delete_entry':
            selected_group = get_object_or_404(StudyGroup, id=request.POST.get('group'))
            entry = get_object_or_404(
                ScheduleEntry,
                id=request.POST.get('entry'),
                group=selected_group,
            )
            entry.delete()
            messages.success(request, 'Занятие удалено.')
            return redirect(_schedule_url(
                group=selected_group,
                view_mode=request.POST.get('view'),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date'),
            ))

        elif action == 'delete_group':
            group = get_object_or_404(StudyGroup, id=request.POST.get('group'))
            group_name = group.name
            lessons_count = group.schedule_entries.count()
            institute = group.institute
            group.delete()
            messages.success(
                request,
                f'Группа {group_name} удалена. Удалено занятий: {lessons_count}.',
            )
            return redirect(_institute_url(institute))

        elif action == 'delete_institute':
            institute = get_object_or_404(Institute, id=request.POST.get('institute'))
            institute_name = institute.name
            groups_count = institute.groups.count()
            lessons_count = ScheduleEntry.objects.filter(group__institute=institute).count()
            institute.delete()
            messages.success(
                request,
                (
                    f'Институт {institute_name} удален. '
                    f'Удалено групп: {groups_count}, занятий: {lessons_count}.'
                ),
            )
            return redirect('home')

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
    schedule_table = {'time_slots': [], 'rows': []}

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
        if selected_start_date:
            schedule_entries = schedule_entries.filter(date__gte=selected_start_date)
        if selected_end_date:
            schedule_entries = schedule_entries.filter(date__lte=selected_end_date)
        schedule_table = _build_schedule_table(schedule_entries)

    context = {
        'institutes': institutes,
        'courses': courses,
        'groups': groups,
        'selected_institute': selected_institute,
        'selected_course': selected_course,
        'selected_group': selected_group,
        'selected_start_date': selected_start_date,
        'selected_end_date': selected_end_date,
        'view_mode': view_mode,
        'schedule_table': schedule_table,
        'schedule_entries': schedule_entries,
        'group_form': group_form,
        'entry_form': entry_form,
        'upload_form': upload_form,
        'edit_entry': edit_entry,
    }
    return render(request, 'pages/home.html', context)


def _schedule_url(group, view_mode=None, start_date=None, end_date=None):
    params = {
        'institute': group.institute_id,
        'course': group.course,
        'group': group.id,
    }
    if view_mode in {'list', 'table'}:
        params['view'] = view_mode
    if start_date:
        params['start_date'] = start_date
    if end_date:
        params['end_date'] = end_date
    return f'{reverse("home")}?{urlencode(params)}'


def _institute_url(institute):
    return f'{reverse("home")}?{urlencode({"institute": institute.id})}'


def _as_int(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _build_schedule_table(schedule_entries):
    entries = list(schedule_entries)
    time_slots = sorted({
        (entry.start_time, entry.end_time)
        for entry in entries
    })
    rows_by_date = {}

    for entry in entries:
        rows_by_date.setdefault(entry.date, {}).setdefault(
            (entry.start_time, entry.end_time),
            [],
        ).append(entry)

    rows = []
    for lesson_date in sorted(rows_by_date):
        day_slots = rows_by_date[lesson_date]
        rows.append({
            'date': lesson_date,
            'weekday': _weekday_name(lesson_date),
            'cells': [
                {
                    'slot': slot,
                    'entries': day_slots.get(slot, []),
                }
                for slot in time_slots
            ],
        })

    return {
        'time_slots': time_slots,
        'rows': rows,
    }


def _weekday_name(value):
    weekdays = [
        'Понедельник',
        'Вторник',
        'Среда',
        'Четверг',
        'Пятница',
        'Суббота',
        'Воскресенье',
    ]
    return weekdays[value.weekday()]
