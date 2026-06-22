from django.urls import path
from . import api_views

urlpatterns = [
    path('predict/', api_views.predict, name='predict'),
]