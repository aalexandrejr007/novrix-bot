from django.db import models
from datetime import timedelta

from django.utils import timezone


class Contato(models.Model):
    """Uma pessoa que conversou com a Novrix pelo WhatsApp."""

    wa_id = models.CharField("WhatsApp", max_length=32, unique=True)
    nome = models.CharField("Nome no WhatsApp", max_length=120, blank=True)
    interesse = models.CharField("Último interesse", max_length=40, blank=True)
    quer_orcamento = models.BooleanField("Pediu orçamento / atendimento", default=False)
    robo_pausado_ate = models.DateTimeField(
        "Robô pausado até", null=True, blank=True,
        help_text="Enquanto isso, o robô não responde: quem atende é uma pessoa.",
    )
    criado_em = models.DateTimeField("Primeiro contato", auto_now_add=True)
    atualizado_em = models.DateTimeField("Última mensagem", auto_now=True)

    class Meta:
        verbose_name = "contato"
        verbose_name_plural = "contatos"
        ordering = ["-atualizado_em"]

    def __str__(self):
        return f"{self.nome or 'Sem nome'} ({self.wa_id})"

    @property
    def robo_pausado(self):
        return bool(self.robo_pausado_ate and self.robo_pausado_ate > timezone.now())

    def pausar_robo(self, horas):
        self.robo_pausado_ate = timezone.now() + timedelta(hours=horas)
        self.save(update_fields=["robo_pausado_ate", "atualizado_em"])


class Mensagem(models.Model):
    """Histórico do que entrou e saiu pelo robô."""

    ENTRADA, SAIDA = "entrada", "saida"
    contato = models.ForeignKey(Contato, on_delete=models.CASCADE, related_name="mensagens")
    direcao = models.CharField("Direção", max_length=8, choices=[(ENTRADA, "Recebida"), (SAIDA, "Enviada")])
    wa_message_id = models.CharField("ID na Meta", max_length=128, unique=True, null=True, blank=True)
    tipo = models.CharField("Tipo", max_length=24, blank=True)
    texto = models.TextField("Texto", blank=True)
    criado_em = models.DateTimeField("Quando", auto_now_add=True)

    class Meta:
        verbose_name = "mensagem"
        verbose_name_plural = "mensagens"
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.get_direcao_display()}: {self.texto[:50]}"
