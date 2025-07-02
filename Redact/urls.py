from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('redact-confirm/', views.redact_confirm, name='redact_confirm'),
]
