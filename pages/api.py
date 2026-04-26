from datetime import date, datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Institute, ScheduleEntry, StudyGroup


@require_GET
def catalog(request):
    institutes = Institute.objects.prefetch_related('groups').all()

    return _json_response({
        'institutes': [
            {
                'id': institute.id,
                'name': institute.name,
                'shortName': _institute_short_name(institute.name),
                'logo': '',
                'groups': [
                    {
                        'id': group.id,
                        'name': group.name,
                        'course': group.course,
                    }
                    for group in institute.groups.all()
                ],
            }
            for institute in institutes
        ],
    })


@require_GET
def schedule_v1(request):
    group_id = _as_int(request.GET.get('groupId'))
    if group_id is None:
        return _error_response('Передайте groupId.')

    group = StudyGroup.objects.select_related('institute').filter(id=group_id).first()
    if not group:
        return _error_response('Группа с таким groupId не найдена.', status=404)

    from_date = _parse_iso_date(request.GET.get('from'))
    to_date = _parse_iso_date(request.GET.get('to'))

    if request.GET.get('from') and from_date is None:
        return _error_response('from должен быть в формате YYYY-MM-DD.')
    if request.GET.get('to') and to_date is None:
        return _error_response('to должен быть в формате YYYY-MM-DD.')

    lessons = ScheduleEntry.objects.filter(group=group)
    if from_date:
        lessons = lessons.filter(date__gte=from_date)
    if to_date:
        lessons = lessons.filter(date__lte=to_date)

    return _json_response({
        'group': {
            'id': group.id,
            'name': group.name,
            'course': group.course,
            'instituteId': group.institute_id,
            'instituteName': group.institute.name,
        },
        'items': [
            _lesson_v1_payload(lesson)
            for lesson in lessons
        ],
    })


@require_GET
def group_list(request):
    groups = StudyGroup.objects.select_related('institute')

    institute_id = _as_int(request.GET.get('institute_id'))
    course = _as_int(request.GET.get('course'))
    if institute_id is not None:
        groups = groups.filter(institute_id=institute_id)
    if course is not None:
        groups = groups.filter(course=course)

    return _json_response({
        'groups': [
            _group_payload(group)
            for group in groups
        ],
    })


@require_GET
def schedule_detail(request):
    group = _resolve_group(request)
    if isinstance(group, JsonResponse):
        return group

    lessons = ScheduleEntry.objects.filter(group=group)
    start_date = _parse_iso_date(request.GET.get('start_date'))
    end_date = _parse_iso_date(request.GET.get('end_date'))

    if request.GET.get('start_date') and start_date is None:
        return _error_response('start_date должен быть в формате YYYY-MM-DD.')
    if request.GET.get('end_date') and end_date is None:
        return _error_response('end_date должен быть в формате YYYY-MM-DD.')

    if start_date:
        lessons = lessons.filter(date__gte=start_date)
    if end_date:
        lessons = lessons.filter(date__lte=end_date)

    return _json_response({
        'group': _group_payload(group),
        'lessons': [
            _lesson_payload(lesson)
            for lesson in lessons
        ],
    })


def _resolve_group(request):
    group_id = _as_int(request.GET.get('group_id'))
    if group_id is not None:
        group = StudyGroup.objects.select_related('institute').filter(id=group_id).first()
        if group:
            return group
        return _error_response('Группа с таким group_id не найдена.', status=404)

    group_name = (request.GET.get('group_name') or '').strip()
    if not group_name:
        return _error_response('Передайте group_id или group_name.')

    groups = StudyGroup.objects.select_related('institute').filter(name__iexact=group_name)
    institute_id = _as_int(request.GET.get('institute_id'))
    course = _as_int(request.GET.get('course'))
    if institute_id is not None:
        groups = groups.filter(institute_id=institute_id)
    if course is not None:
        groups = groups.filter(course=course)

    matches = list(groups)
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return _error_response('Группа с такими параметрами не найдена.', status=404)
    return _error_response(
        'Найдено несколько групп. Уточните institute_id или используйте group_id.',
        status=400,
        extra={'matches': [_group_payload(group) for group in matches]},
    )


def _group_payload(group):
    return {
        'id': group.id,
        'name': group.name,
        'course': group.course,
        'institute': {
            'id': group.institute_id,
            'name': group.institute.name,
        },
    }


def _lesson_payload(lesson):
    return {
        'id': lesson.id,
        'date': lesson.date.isoformat(),
        'weekday': _weekday_name(lesson.date),
        'start_time': lesson.start_time.strftime('%H:%M'),
        'end_time': lesson.end_time.strftime('%H:%M'),
        'subject': lesson.subject,
        'teacher': lesson.teacher,
        'room': lesson.room,
        'note': lesson.note,
    }


def _lesson_v1_payload(lesson):
    return {
        'id': lesson.id,
        'date': lesson.date.isoformat(),
        'title': lesson.subject,
        'teacher': lesson.teacher,
        'room': lesson.room,
        'startAt': _lesson_datetime_iso(lesson.date, lesson.start_time),
        'endAt': _lesson_datetime_iso(lesson.date, lesson.end_time),
        'status': _lesson_status(lesson),
        'comment': lesson.note,
    }


def _json_response(payload, status=200):
    return JsonResponse(
        payload,
        status=status,
        json_dumps_params={'ensure_ascii': False},
    )


def _error_response(message, status=400, extra=None):
    payload = {'error': message}
    if extra:
        payload.update(extra)
    return _json_response(payload, status=status)


def _as_int(value):
    if value in (None, ''):
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


def _lesson_datetime_iso(lesson_date, lesson_time):
    value = datetime.combine(lesson_date, lesson_time)
    value = timezone.make_aware(value, timezone.get_current_timezone())
    return value.isoformat()


def _lesson_status(lesson):
    text = f'{lesson.room} {lesson.note}'.lower()
    if 'отмен' in text:
        return 'cancelled'
    if 'замен' in text:
        return 'replaced'
    if 'дистанционно' in text or 'онлайн' in text or 'teams' in text:
        return 'online'
    return 'active'


def _institute_short_name(name):
    words = [
        word.strip('«»"(),.')
        for word in name.split()
        if word and word[0].isalpha()
    ]
    letters = ''.join(word[0].upper() for word in words[:4])
    return letters or name[:8].upper()


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
