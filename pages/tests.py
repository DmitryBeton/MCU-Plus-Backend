from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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


def _schedule_url(group):
    return (
        f'{reverse("home")}'
        f'?institute={group.institute_id}'
        f'&course={group.course}'
        f'&group={group.id}'
    )
