from django import forms

from .models import ScheduleEntry


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
