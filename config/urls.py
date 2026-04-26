"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from pages import api
from pages import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='login', permanent=False)),
    path('api/v1/catalog/', api.catalog, name='api_v1_catalog'),
    path('api/v1/schedule/', api.schedule_v1, name='api_v1_schedule'),
    path('api/groups/', api.group_list, name='api_groups'),
    path('api/schedule/', api.schedule_detail, name='api_schedule'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('home/', views.home, name='home'),
]
