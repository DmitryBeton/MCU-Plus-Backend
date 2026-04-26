import json
from dataclasses import dataclass
from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Institute, ScheduleEntry, StudyGroup


@dataclass
class ImportSummary:
    institutes_created: int = 0
    groups_created: int = 0
    entries_created: int = 0
    entries_updated: int = 0


def import_schedule_json(uploaded_file):
    try:
        raw_data = uploaded_file.read().decode('utf-8-sig')
        data = json.loads(raw_data)
    except UnicodeDecodeError as error:
        raise ValidationError('Файл должен быть сохранен в UTF-8.') from error
    except json.JSONDecodeError as error:
        raise ValidationError(f'Некорректный JSON: {error.msg}.') from error

    records = list(_iter_schedule_records(data))
    if not records:
        raise ValidationError('В JSON не найдено ни одного занятия.')

    summary = ImportSummary()
    with transaction.atomic():
        for index, record in enumerate(records, start=1):
            normalized = _normalize_record(record, index)
            institute, institute_created = Institute.objects.get_or_create(
                name=normalized['institute']
            )
            group, group_created = StudyGroup.objects.get_or_create(
                institute=institute,
                course=normalized['course'],
                name=normalized['group'],
            )
            _entry, entry_created = ScheduleEntry.objects.update_or_create(
                group=group,
                date=normalized['date'],
                start_time=normalized['start_time'],
                end_time=normalized['end_time'],
                subject=normalized['subject'],
                defaults={
                    'teacher': normalized['teacher'],
                    'room': normalized['room'],
                    'note': normalized['note'],
                },
            )

            summary.institutes_created += int(institute_created)
            summary.groups_created += int(group_created)
            if entry_created:
                summary.entries_created += 1
            else:
                summary.entries_updated += 1

    return summary


def _iter_schedule_records(data):
    if isinstance(data, list):
        yield from data
        return

    if not isinstance(data, dict):
        raise ValidationError('Корневой элемент JSON должен быть объектом или списком.')

    if 'entries' in data:
        yield from _require_list(data['entries'], 'entries')
        return

    if 'groups' in data:
        for group in _require_list(data['groups'], 'groups'):
            for lesson in _lessons_from_group(group):
                yield {
                    **lesson,
                    'institute': _pick(group, 'institute', 'institute_name', 'институт'),
                    'course': _pick(group, 'course', 'курс'),
                    'group': _pick(group, 'group', 'group_name', 'name', 'группа'),
                }
        return

    for institute in _require_list(data.get('institutes', []), 'institutes'):
        institute_name = _pick(institute, 'name', 'institute', 'institute_name', 'институт')
        for group in _require_list(institute.get('groups', []), 'groups'):
            for lesson in _lessons_from_group(group):
                yield {
                    **lesson,
                    'institute': institute_name,
                    'course': _pick(group, 'course', 'курс'),
                    'group': _pick(group, 'name', 'group', 'group_name', 'группа'),
                }


def _lessons_from_group(group):
    lessons = (
        group.get('lessons')
        or group.get('schedule')
        or group.get('entries')
        or group.get('занятия')
        or []
    )
    yield from _require_list(lessons, 'lessons')


def _normalize_record(record, index):
    if not isinstance(record, dict):
        raise ValidationError(f'Занятие #{index}: ожидается объект.')

    normalized = {
        'institute': _required_text(record, index, 'institute', 'institute_name', 'институт'),
        'group': _required_text(record, index, 'group', 'group_name', 'группа'),
        'subject': _required_text(record, index, 'subject', 'дисциплина', 'lesson'),
        'teacher': _optional_text(record, 'teacher', 'преподаватель'),
        'room': _optional_text(record, 'room', 'auditorium', 'аудитория'),
        'note': _optional_text(record, 'note', 'comment', 'заметка'),
        'course': _parse_course(_pick(record, 'course', 'курс'), index),
        'date': _parse_date(_pick(record, 'date', 'дата'), index),
        'start_time': _parse_time(_pick(record, 'start_time', 'start', 'начало'), index, 'начало'),
        'end_time': _parse_time(_pick(record, 'end_time', 'end', 'конец'), index, 'конец'),
    }

    if normalized['end_time'] <= normalized['start_time']:
        raise ValidationError(f'Занятие #{index}: время окончания должно быть позже начала.')

    return normalized


def _pick(mapping, *keys):
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ''):
            return value
    return None


def _required_text(mapping, index, *keys):
    value = _optional_text(mapping, *keys)
    if not value:
        raise ValidationError(f'Занятие #{index}: поле "{keys[0]}" обязательно.')
    return value


def _optional_text(mapping, *keys):
    value = _pick(mapping, *keys)
    if value is None:
        return ''
    return str(value).strip()


def _parse_course(value, index):
    try:
        course = int(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f'Занятие #{index}: курс должен быть числом.') from error
    if course < 1 or course > 6:
        raise ValidationError(f'Занятие #{index}: курс должен быть от 1 до 6.')
    return course


def _parse_date(value, index):
    if not value:
        raise ValidationError(f'Занятие #{index}: поле "date" обязательно.')
    text = str(value).strip()
    for parser in (date.fromisoformat, _parse_ru_date):
        try:
            return parser(text)
        except ValueError:
            continue
    raise ValidationError(f'Занятие #{index}: дата должна быть в формате YYYY-MM-DD или DD.MM.YYYY.')


def _parse_ru_date(value):
    day, month, year = value.split('.')
    return date(int(year), int(month), int(day))


def _parse_time(value, index, field_name):
    if not value:
        raise ValidationError(f'Занятие #{index}: поле "{field_name}" обязательно.')
    text = str(value).strip()
    if len(text.split(':')) == 2:
        text = f'{text}:00'
    try:
        return time.fromisoformat(text)
    except ValueError as error:
        raise ValidationError(f'Занятие #{index}: время "{field_name}" должно быть в формате HH:MM.') from error


def _require_list(value, field_name):
    if not isinstance(value, list):
        raise ValidationError(f'Поле "{field_name}" должно быть списком.')
    return value
