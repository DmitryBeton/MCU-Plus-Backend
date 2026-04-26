from django.db import models


class Institute(models.Model):
    name = models.CharField('название института', max_length=180, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'институт'
        verbose_name_plural = 'институты'

    def __str__(self):
        return self.name


class StudyGroup(models.Model):
    institute = models.ForeignKey(
        Institute,
        on_delete=models.CASCADE,
        related_name='groups',
        verbose_name='институт',
    )
    course = models.PositiveSmallIntegerField('курс')
    name = models.CharField('название группы', max_length=80)

    class Meta:
        ordering = ['institute__name', 'course', 'name']
        unique_together = [('institute', 'course', 'name')]
        verbose_name = 'учебная группа'
        verbose_name_plural = 'учебные группы'

    def __str__(self):
        return f'{self.name}, {self.course} курс'


class ScheduleEntry(models.Model):
    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.CASCADE,
        related_name='schedule_entries',
        verbose_name='группа',
    )
    date = models.DateField('дата занятия')
    start_time = models.TimeField('начало')
    end_time = models.TimeField('конец')
    subject = models.CharField('дисциплина', max_length=180)
    teacher = models.CharField('преподаватель', max_length=140, blank=True)
    room = models.CharField('аудитория', max_length=60, blank=True)
    note = models.TextField('заметка', blank=True)

    class Meta:
        ordering = ['date', 'start_time', 'subject']
        verbose_name = 'занятие'
        verbose_name_plural = 'занятия'

    def __str__(self):
        return f'{self.date:%d.%m.%Y} {self.start_time:%H:%M} {self.subject}'
