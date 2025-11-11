# clientes/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template import Context, Template
from django.core.mail import EmailMessage
from .models import Cliente
from parametros.models import ParametroContrato

@receiver(post_save, sender=Cliente)
def enviar_contrato_email(sender, instance, created, **kwargs):
    if not created:
        return  # só envia na criação

    try:
        contrato = ParametroContrato.objects.filter(ativo=True).first()
        if not contrato:
            print("⚠️ Nenhum modelo de contrato ativo encontrado.")
            return

        # Renderiza o corpo do email e do contrato com dados do cliente
        contexto = Context({"cliente": instance})
        corpo_email = Template(contrato.corpo_email).render(contexto)
        corpo_contrato = Template(contrato.corpo_contrato).render(contexto)

        email = EmailMessage(
            subject=Template(contrato.assunto_email).render(contexto),
            body=corpo_email,
            to=[instance.email],
        )
        email.content_subtype = "html"  # envia como HTML
        email.send(fail_silently=False)

        print(f"✅ Contrato enviado para {instance.email}")
    except Exception as e:
        print(f"❌ Erro ao enviar contrato: {e}")
