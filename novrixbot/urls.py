from django.contrib import admin
from django.urls import path

from django.views.generic import RedirectView

from bot import atendimento, views

admin.site.site_header = "Novrix Tech · Robô do WhatsApp"
admin.site.site_title = "Robô Novrix"
admin.site.index_title = "Conversas e contatos"
admin.site.site_url = "/painel/atendimento/"  # link "Ver o site" do admin leva para a caixa de entrada

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("privacidade/", views.privacidade, name="privacidade"),
    path("saude/", views.saude, name="saude"),
    path("painel/atendimento/", atendimento.caixa, name="caixa"),
    path("painel/atendimento/api/conversas/", atendimento.api_conversas, name="api_conversas"),
    path("painel/atendimento/api/<int:pk>/mensagens/", atendimento.api_mensagens, name="api_mensagens"),
    path("painel/atendimento/api/<int:pk>/enviar/", atendimento.api_enviar, name="api_enviar"),
    path("painel/atendimento/api/<int:pk>/robo/", atendimento.api_robo, name="api_robo"),
    path("painel/", admin.site.urls),
    path("", RedirectView.as_view(url="/painel/atendimento/", permanent=False)),
]
