from django import forms

from .models import ScheduleEntry


class ScheduleJsonUploadForm(forms.Form):
    institute_name = forms.CharField(
        label='Институт для Excel',
        max_length=180,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Если файл Excel без названия института'}),
    )
    file = forms.FileField(
        label='Файл расписания',
        widget=forms.FileInput(attrs={'accept': 'application/json,.json,.xlsx'}),
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data['file']
        if not uploaded_file.name.lower().endswith(('.json', '.xlsx')):
            raise forms.ValidationError('Загрузите файл в формате .json или .xlsx.')
        if uploaded_file.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Файл слишком большой. Максимум 5 МБ.')
        return uploaded_file


class GroupCreateForm(forms.Form):
    institute_name = forms.CharField(
        label='Институт',
        max_length=180,
        widget=forms.TextInput(attrs={'placeholder': 'Например: Институт цифрового образования'}),
    )
    course = forms.IntegerField(
        label='Курс',
        min_value=1,
        max_value=6,
        widget=forms.NumberInput(attrs={'placeholder': '1'}),
    )
    group_name = forms.CharField(
        label='Группа',
        max_length=80,
        widget=forms.TextInput(attrs={'placeholder': 'Например: ИВТ-231'}),
    )


class ScheduleEntryForm(forms.ModelForm):
    class Meta:
        model = ScheduleEntry
        fields = ['date', 'start_time', 'end_time', 'subject', 'teacher', 'room', 'note']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'subject': forms.TextInput(attrs={'placeholder': 'Название дисциплины'}),
            'teacher': forms.TextInput(attrs={'placeholder': 'ФИО преподавателя'}),
            'room': forms.TextInput(attrs={'placeholder': 'Аудитория'}),
            'note': forms.Textarea(attrs={'placeholder': 'Комментарий, замена, ссылка на пару'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('Время окончания должно быть позже времени начала.')
        return cleaned_data
