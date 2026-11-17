from django.contrib import admin
from datetime import timedelta

from django.utils import timezone

from .models import Contato, Mensagem


class MensagemInline(admin.TabularInline):
    model = Mensagem
    extra = 0
    fields = ("criado_em", "direcao", "texto")
    readonly_fields = fields
    ordering = ("-criado_em",)
    can_delete = False
    max_num = 0


@admin.register(Contato)
class ContatoAdmin(admin.ModelAdmin):
    list_display = ("nome", "wa_id", "interesse", "quer_orcamento", "status_robo", "atualizado_em")
    list_filter = ("quer_orcamento", "interesse")
    search_fields = ("nome", "wa_id")
    readonly_fields = ("wa_id", "criado_em", "atualizado_em")
    inlines = [MensagemInline]
    actions = ["reativar_robo", "pausar_robo"]

    @admin.display(description="Robô")
    def status_robo(self, obj):
        return "Pausado (pessoa atendendo)" if obj.robo_pausado else "Ativo"

    @admin.action(description="Reativar o robô nessas conversas")
    def reativar_robo(self, request, queryset):
        queryset.update(robo_pausado_ate=None)

    @admin.action(description="Pausar o robô por 24 h nessas conversas")
    def pausar_robo(self, request, queryset):
        queryset.update(robo_pausado_ate=timezone.now() + timedelta(hours=24))


@admin.register(Mensagem)
class MensagemAdmin(admin.ModelAdmin):
    list_display = ("criado_em", "contato", "direcao", "texto")
    list_filter = ("direcao",)
    search_fields = ("texto", "contato__nome", "contato__wa_id")
