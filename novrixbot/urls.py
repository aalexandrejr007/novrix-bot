from django.contrib import admin
from django.urls import path

from bot import views

admin.site.site_header = "Novrix Tech · Robô do WhatsApp"
admin.site.site_title = "Robô Novrix"
admin.site.index_title = "Conversas e contatos"

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("saude/", views.saude, name="saude"),
    path("painel/", admin.site.urls),
]
