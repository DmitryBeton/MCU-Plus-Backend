import json
from datetime import date
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from .models import Institute, ScheduleEntry, StudyGroup


class HomePageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='demo',
            password='demo12345',
        )

    def test_home_requires_login(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_home_renders_for_authenticated_user(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Расписание занятий')

    def test_empty_filter_values_do_not_crash_home_page(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('home'), {
            'institute': '',
            'course': '',
            'group': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Выберите группу')

    def test_selected_institute_loads_courses_and_groups(self):
        self.client.force_login(self.user)
        institute = Institute.objects.create(name='Институт цифрового образования')
        StudyGroup.objects.create(institute=institute, course=1, name='ИВТ-101')
        StudyGroup.objects.create(institute=institute, course=2, name='ИВТ-201')

        response = self.client.get(reverse('home'), {
            'institute': institute.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 курс')
        self.assertContains(response, '2 курс')
        self.assertContains(response, 'ИВТ-101')
        self.assertContains(response, 'ИВТ-201')

        response = self.client.get(reverse('home'), {
            'institute': institute.id,
            'course': '2',
        })

        self.assertContains(response, 'ИВТ-201')
        self.assertNotContains(response, 'ИВТ-101')


class ScheduleManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='demo',
            password='demo12345',
        )
        self.client.force_login(self.user)

    def test_can_create_group_from_home_page(self):
        response = self.client.post(reverse('home'), {
            'action': 'create_group',
            'institute_name': 'Институт цифрового образования',
            'course': '2',
            'group_name': 'ИВТ-231',
        })

        group = StudyGroup.objects.get(name='ИВТ-231')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(group.course, 2)
        self.assertEqual(group.institute.name, 'Институт цифрового образования')

    def test_can_create_update_and_delete_schedule_entry(self):
        institute = Institute.objects.create(name='Институт педагогики')
        group = StudyGroup.objects.create(
            institute=institute,
            course=1,
            name='ПЕД-101',
        )

        response = self.client.post(_schedule_url(group), {
            'action': 'create_entry',
            'group': group.id,
            'date': '2026-04-27',
            'start_time': '09:00',
            'end_time': '10:30',
            'subject': 'Психология',
            'teacher': 'Иванов И.И.',
            'room': '101',
            'note': 'Первая пара',
        })

        entry = ScheduleEntry.objects.get(group=group)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(entry.subject, 'Психология')

        response = self.client.post(_schedule_url(group), {
            'action': 'update_entry',
            'group': group.id,
            'entry': entry.id,
            'date': '2026-04-28',
            'start_time': '11:00',
            'end_time': '12:30',
            'subject': 'Педагогика',
            'teacher': '',
            'room': '202',
            'note': '',
        })

        entry.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(entry.subject, 'Педагогика')
        self.assertEqual(entry.room, '202')

        response = self.client.post(_schedule_url(group), {
            'action': 'delete_entry',
            'group': group.id,
            'entry': entry.id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(ScheduleEntry.objects.filter(id=entry.id).exists())

    def test_edit_form_contains_delete_entry_action(self):
        institute = Institute.objects.create(name='Институт цифрового образования')
        group = StudyGroup.objects.create(
            institute=institute,
            course=2,
            name='ИВТ-231',
        )
        entry = ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Математический анализ',
        )

        response = self.client.get(reverse('home'), {
            'institute': group.institute_id,
            'course': group.course,
            'group': group.id,
            'edit': entry.id,
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Удалить занятие')
        self.assertContains(response, 'id="delete-edited-entry"')
        self.assertContains(response, 'name="action" value="delete_entry"')

    def test_entry_end_time_must_be_later_than_start_time(self):
        institute = Institute.objects.create(name='Институт культуры')
        group = StudyGroup.objects.create(
            institute=institute,
            course=3,
            name='КУЛ-301',
        )

        response = self.client.post(_schedule_url(group), {
            'action': 'create_entry',
            'group': group.id,
            'date': '2026-04-27',
            'start_time': '10:30',
            'end_time': '09:00',
            'subject': 'История искусства',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Время окончания должно быть позже времени начала.')
        self.assertEqual(ScheduleEntry.objects.count(), 0)

    def test_table_view_renders_schedule_by_dates_and_time_slots(self):
        institute = Institute.objects.create(name='Институт цифрового образования')
        group = StudyGroup.objects.create(
            institute=institute,
            course=2,
            name='ИВТ-231',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Математический анализ',
            teacher='Иванов И.И.',
            room='101',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='10:40',
            end_time='12:10',
            subject='Программирование',
            teacher='Петров П.П.',
            room='202',
        )

        response = self.client.get(reverse('home'), {
            'institute': group.institute_id,
            'course': group.course,
            'group': group.id,
            'view': 'table',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Таблица')
        self.assertContains(response, '1 пара')
        self.assertContains(response, '09:00 - 10:30')
        self.assertContains(response, '01.09.2026')
        self.assertContains(response, 'Математический анализ')
        self.assertContains(response, 'Программирование')

    def test_period_filter_limits_table_entries(self):
        institute = Institute.objects.create(name='Институт экономики')
        group = StudyGroup.objects.create(
            institute=institute,
            course=1,
            name='ЭК-101',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Микроэкономика',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-10-01',
            start_time='09:00',
            end_time='10:30',
            subject='Статистика',
        )

        response = self.client.get(reverse('home'), {
            'institute': group.institute_id,
            'course': group.course,
            'group': group.id,
            'view': 'table',
            'start_date': '2026-10-01',
            'end_date': '2026-10-31',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Статистика')
        self.assertNotContains(response, 'Микроэкономика')

    def test_can_delete_group_with_schedule_entries(self):
        institute = Institute.objects.create(name='Институт цифрового образования')
        group = StudyGroup.objects.create(
            institute=institute,
            course=2,
            name='ИВТ-231',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Математический анализ',
        )

        response = self.client.post(reverse('home'), {
            'action': 'delete_group',
            'group': group.id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Institute.objects.filter(id=institute.id).exists())
        self.assertFalse(StudyGroup.objects.filter(id=group.id).exists())
        self.assertEqual(ScheduleEntry.objects.count(), 0)

    def test_can_delete_institute_with_groups_and_schedule_entries(self):
        institute = Institute.objects.create(name='Институт экономики')
        group = StudyGroup.objects.create(
            institute=institute,
            course=1,
            name='ЭК-101',
        )
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Микроэкономика',
        )

        response = self.client.post(reverse('home'), {
            'action': 'delete_institute',
            'institute': institute.id,
        })

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Institute.objects.filter(id=institute.id).exists())
        self.assertEqual(StudyGroup.objects.count(), 0)
        self.assertEqual(ScheduleEntry.objects.count(), 0)

    def test_can_import_schedule_from_json_file(self):
        payload = {
            'entries': [
                {
                    'institute': 'Институт цифрового образования',
                    'course': 2,
                    'group': 'ИВТ-231',
                    'date': '2026-09-01',
                    'start_time': '09:00',
                    'end_time': '10:30',
                    'subject': 'Математический анализ',
                    'teacher': 'Иванов И.И.',
                    'room': '101',
                    'note': 'Лекция',
                },
                {
                    'institute': 'Институт цифрового образования',
                    'course': 2,
                    'group': 'ИВТ-231',
                    'date': '2026-09-01',
                    'start_time': '10:40',
                    'end_time': '12:10',
                    'subject': 'Программирование',
                    'teacher': 'Петров П.П.',
                    'room': '202',
                    'note': 'Практика',
                },
            ],
        }
        uploaded_file = SimpleUploadedFile(
            'schedule.json',
            json.dumps(payload).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(reverse('home'), {
            'action': 'import_schedule',
            'file': uploaded_file,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Institute.objects.count(), 1)
        self.assertEqual(StudyGroup.objects.count(), 1)
        self.assertEqual(ScheduleEntry.objects.count(), 2)
        self.assertEqual(ScheduleEntry.objects.first().subject, 'Математический анализ')

    def test_can_import_schedule_from_excel_file(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = '2к ЦИБ-241'
        worksheet['A8'] = 'день / неделя/дата'
        worksheet['B8'] = 'время'
        worksheet['C8'] = 1
        worksheet['E8'] = 2
        worksheet['C9'] = date(2026, 2, 9)
        worksheet['E9'] = date(2026, 2, 16)
        worksheet['A10'] = 'ПОНЕДЕЛЬНИК'
        worksheet['B10'] = '9.00 - 10.20'
        worksheet['C10'] = 'Математический анализ\nдоц., к.п.н.\nИванов И.И.\nЛК\nауд. 101'
        worksheet['E10'] = '1 подгруппа\nАнглийский язык\nст. преп.\nПетров П.П.\nПР\nауд. 308 (Б)'
        file_data = BytesIO()
        workbook.save(file_data)
        uploaded_file = SimpleUploadedFile(
            'schedule.xlsx',
            file_data.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

        response = self.client.post(reverse('home'), {
            'action': 'import_schedule',
            'institute_name': 'Институт тестового импорта',
            'file': uploaded_file,
        })

        self.assertEqual(response.status_code, 302)
        group = StudyGroup.objects.get(name='ЦИБ-241')
        self.assertEqual(group.course, 2)
        self.assertEqual(group.institute.name, 'Институт тестового импорта')
        self.assertEqual(ScheduleEntry.objects.count(), 2)
        math_entry = ScheduleEntry.objects.get(subject='Математический анализ')
        self.assertEqual(math_entry.teacher, 'доц., к.п.н Иванов И.И')
        self.assertEqual(math_entry.room, 'ауд. 101')
        english_entry = ScheduleEntry.objects.get(subject='Английский язык')
        self.assertEqual(english_entry.note, '1 подгруппа, ПР')

    def test_can_import_nested_schedule_json_file(self):
        payload = {
            'institutes': [
                {
                    'name': 'Институт экономики',
                    'groups': [
                        {
                            'name': 'ЭК-101',
                            'course': 1,
                            'lessons': [
                                {
                                    'date': '01.09.2026',
                                    'start_time': '09:00',
                                    'end_time': '10:30',
                                    'subject': 'Экономика',
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        uploaded_file = SimpleUploadedFile(
            'schedule.json',
            json.dumps(payload).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(reverse('home'), {
            'action': 'import_schedule',
            'file': uploaded_file,
        })

        self.assertEqual(response.status_code, 302)
        entry = ScheduleEntry.objects.get()
        self.assertEqual(entry.group.institute.name, 'Институт экономики')
        self.assertEqual(entry.group.name, 'ЭК-101')
        self.assertEqual(entry.subject, 'Экономика')

    def test_import_updates_existing_entry(self):
        institute = Institute.objects.create(name='Институт цифрового образования')
        group = StudyGroup.objects.create(institute=institute, course=2, name='ИВТ-231')
        ScheduleEntry.objects.create(
            group=group,
            date='2026-09-01',
            start_time='09:00',
            end_time='10:30',
            subject='Математический анализ',
            room='101',
        )
        payload = {
            'entries': [
                {
                    'institute': institute.name,
                    'course': 2,
                    'group': group.name,
                    'date': '2026-09-01',
                    'start_time': '09:00',
                    'end_time': '10:30',
                    'subject': 'Математический анализ',
                    'teacher': 'Иванов И.И.',
                    'room': '301',
                },
            ],
        }
        uploaded_file = SimpleUploadedFile(
            'schedule.json',
            json.dumps(payload).encode('utf-8'),
            content_type='application/json',
        )

        response = self.client.post(reverse('home'), {
            'action': 'import_schedule',
            'file': uploaded_file,
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ScheduleEntry.objects.count(), 1)
        entry = ScheduleEntry.objects.get()
        self.assertEqual(entry.teacher, 'Иванов И.И.')
        self.assertEqual(entry.room, '301')


def _schedule_url(group):
    return (
        f'{reverse("home")}'
        f'?institute={group.institute_id}'
        f'&course={group.course}'
        f'&group={group.id}'
    )


class ScheduleApiTests(TestCase):
    def setUp(self):
        self.institute = Institute.objects.create(name='Институт цифрового образования')
        self.group = StudyGroup.objects.create(
            institute=self.institute,
            course=2,
            name='ЦИБ-241',
        )
        ScheduleEntry.objects.create(
            group=self.group,
            date='2026-02-09',
            start_time='09:00',
            end_time='10:20',
            subject='Математический анализ',
            teacher='Иванов И.И.',
            room='101',
            note='ЛК',
        )
        ScheduleEntry.objects.create(
            group=self.group,
            date='2026-02-16',
            start_time='10:30',
            end_time='11:50',
            subject='Программирование',
            teacher='Петров П.П.',
            room='202',
            note='ПР',
        )

    def test_groups_api_returns_available_groups(self):
        response = self.client.get(reverse('api_groups'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['groups'][0]['id'], self.group.id)
        self.assertEqual(payload['groups'][0]['name'], 'ЦИБ-241')
        self.assertEqual(payload['groups'][0]['institute']['name'], self.institute.name)

    def test_v1_catalog_returns_institutes_with_groups(self):
        response = self.client.get(reverse('api_v1_catalog'))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['institutes'][0]['id'], self.institute.id)
        self.assertEqual(payload['institutes'][0]['name'], self.institute.name)
        self.assertIn('shortName', payload['institutes'][0])
        self.assertIn('logo', payload['institutes'][0])
        self.assertEqual(payload['institutes'][0]['groups'][0]['id'], self.group.id)
        self.assertEqual(payload['institutes'][0]['groups'][0]['name'], 'ЦИБ-241')

    def test_groups_api_can_filter_by_course(self):
        StudyGroup.objects.create(
            institute=self.institute,
            course=3,
            name='ЦИБ-231',
        )

        response = self.client.get(reverse('api_groups'), {'course': 2})

        self.assertEqual(response.status_code, 200)
        groups = response.json()['groups']
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['name'], 'ЦИБ-241')

    def test_schedule_api_returns_lessons_for_group_id(self):
        response = self.client.get(reverse('api_schedule'), {'group_id': self.group.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['group']['name'], 'ЦИБ-241')
        self.assertEqual(len(payload['lessons']), 2)
        self.assertEqual(payload['lessons'][0]['date'], '2026-02-09')
        self.assertEqual(payload['lessons'][0]['start_time'], '09:00')
        self.assertEqual(payload['lessons'][0]['subject'], 'Математический анализ')

    def test_v1_schedule_api_returns_items_for_group_id(self):
        response = self.client.get(reverse('api_v1_schedule'), {'groupId': self.group.id})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['group']['id'], self.group.id)
        self.assertEqual(payload['group']['instituteId'], self.institute.id)
        self.assertEqual(len(payload['items']), 2)
        self.assertEqual(payload['items'][0]['title'], 'Математический анализ')
        self.assertEqual(payload['items'][0]['startAt'], '2026-02-09T09:00:00+03:00')
        self.assertEqual(payload['items'][0]['endAt'], '2026-02-09T10:20:00+03:00')
        self.assertEqual(payload['items'][0]['status'], 'active')
        self.assertEqual(payload['items'][0]['comment'], 'ЛК')

    def test_schedule_api_can_filter_lessons_by_period(self):
        response = self.client.get(reverse('api_schedule'), {
            'group_id': self.group.id,
            'start_date': '2026-02-16',
            'end_date': '2026-02-16',
        })

        self.assertEqual(response.status_code, 200)
        lessons = response.json()['lessons']
        self.assertEqual(len(lessons), 1)
        self.assertEqual(lessons[0]['subject'], 'Программирование')

    def test_v1_schedule_api_can_filter_items_by_period(self):
        response = self.client.get(reverse('api_v1_schedule'), {
            'groupId': self.group.id,
            'from': '2026-02-16',
            'to': '2026-02-16',
        })

        self.assertEqual(response.status_code, 200)
        items = response.json()['items']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['title'], 'Программирование')

    def test_v1_schedule_api_reports_missing_group_id(self):
        response = self.client.get(reverse('api_v1_schedule'))

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_v1_schedule_api_detects_lesson_status(self):
        ScheduleEntry.objects.create(
            group=self.group,
            date='2026-02-23',
            start_time='12:40',
            end_time='14:00',
            subject='Базы данных',
            room='Дистанционно',
            note='Подключение через Teams',
        )
        ScheduleEntry.objects.create(
            group=self.group,
            date='2026-02-24',
            start_time='12:40',
            end_time='14:00',
            subject='Алгебра',
            note='Пара отменена',
        )
        ScheduleEntry.objects.create(
            group=self.group,
            date='2026-02-25',
            start_time='12:40',
            end_time='14:00',
            subject='Геометрия',
            note='Замена преподавателя',
        )

        response = self.client.get(reverse('api_v1_schedule'), {'groupId': self.group.id})

        statuses = {
            item['title']: item['status']
            for item in response.json()['items']
        }
        self.assertEqual(statuses['Базы данных'], 'online')
        self.assertEqual(statuses['Алгебра'], 'cancelled')
        self.assertEqual(statuses['Геометрия'], 'replaced')

    def test_schedule_api_accepts_group_name_with_course(self):
        response = self.client.get(reverse('api_schedule'), {
            'group_name': 'ЦИБ-241',
            'course': 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['group']['id'], self.group.id)

    def test_schedule_api_requires_group(self):
        response = self.client.get(reverse('api_schedule'))

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_schedule_api_reports_ambiguous_group_name(self):
        other_institute = Institute.objects.create(name='Другой институт')
        StudyGroup.objects.create(
            institute=other_institute,
            course=2,
            name='ЦИБ-241',
        )

        response = self.client.get(reverse('api_schedule'), {'group_name': 'ЦИБ-241'})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn('matches', payload)
        self.assertEqual(len(payload['matches']), 2)
