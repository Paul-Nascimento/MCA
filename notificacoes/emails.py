# notificacoes/emails.py
from __future__ import annotations
from typing import Iterable, Optional
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def _attach_files(msg: EmailMultiAlternatives, paths: Optional[Iterable[Path]] = None):
    for p in (paths or []):
        try:
            p = Path(p)
            if p.exists():
                msg.attach(p.name, p.read_bytes(), "application/pdf")
        except Exception:
            # segura a exceção de anexo para não impedir o envio
            pass


def _attach_bytes(msg: EmailMultiAlternatives, filename: str, data: bytes, mimetype: str):
    if data:
        msg.attach(filename, data, mimetype)


def send_email_html(*, subject, to, template, context, attach_paths=None):
    html = render_to_string(template, context)
    text = strip_tags(html)
    to_list = [to] if isinstance(to, str) else list(to)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER),
        to=to_list,
    )
    msg.attach_alternative(html, "text/html")

    for p in (attach_paths or []):
        p = Path(p)
        if p.exists():
            msg.attach(p.name, p.read_bytes(), "application/pdf")

    # IMPORTANTE: se der erro, vai levantar exceção (bom p/ debug)
    msg.send(fail_silently=False)
    return True


# =======================
# E-mails específicos MCA
# =======================

def send_cliente_cadastro_confirmacao(cliente) -> bool:
    """
    Confirmação de cadastro do cliente.
    """
    if not cliente.email:
        return False
    ctx = {"cliente": cliente}
    subject = f"Bem-vindo(a), {cliente.nome_razao} — Seu cadastro na MCA"
    # anexa exemplo.pdf se existir no BASE_DIR
    exemplo_pdf = Path(getattr(settings, "BASE_DIR", ".")) / "exemplo.pdf"
    return send_email_html(
        subject=subject,
        to=cliente.email,
        template="emails/cliente_cadastro.html",
        context=ctx,
        attach_paths=[exemplo_pdf],
    )


def send_confirmacao_matricula(matricula) -> bool:
    cliente = matricula.cliente
    turma = matricula.turma
    participante = matricula.participante_nome or cliente.nome_razao

    if not cliente.email:
        print("Cliente sem e-mail, abortando.")
        return False

    ctx = {
        "cliente": cliente,
        "matricula": matricula,
        "turma": turma,
        "participante": participante,
    }
    subject = f"Confirmação de matrícula — {turma.modalidade.nome} em {turma.condominio.nome}"
    exemplo_pdf = Path(getattr(settings, "BASE_DIR", ".")) / "exemplo.pdf"

    print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)
    print("Enviando para:", cliente.email)
    print("Subject:", subject)
    ok = send_email_html(
        subject=subject,
        to=cliente.email,
        template="emails/matricula_confirmacao.html",
        context=ctx,
        attach_paths=[exemplo_pdf],
    )
    print("Resultado send:", ok)
    return ok


def send_boleto_lancamento(lancamento, boleto=None,
                           pdf_path: Optional[Path] = None,
                           pdf_bytes: Optional[bytes] = None,
                           pdf_url: Optional[str] = None) -> bool:
    """
    E-mail de cobrança (contas a receber) com boleto.
    - Se tiver pdf_bytes: anexa (preferencial).
    - Senão se tiver pdf_path: anexa do caminho.
    - Senão, usa exemplo.pdf (se existir).
    - Se tiver pdf_url: inclui o link no corpo.
    """
    # Descobrir e-mail do pagador
    to_email = ""
    if getattr(lancamento, "cliente_id", None):
        to_email = getattr(lancamento.cliente, "email", "") or ""
        nome_cliente = getattr(lancamento.cliente, "nome_razao", "Cliente")
        doc_cliente = getattr(lancamento.cliente, "cpf_cnpj", "")
    else:
        to_email = getattr(lancamento, "email_cobranca", "") or ""
        nome_cliente = getattr(lancamento, "contraparte_nome", "Cliente")
        doc_cliente = getattr(lancamento, "contraparte_doc", "")

    if not to_email:
        return False

    ctx = {
        "lancamento": lancamento,
        "boleto": boleto,
        "nome_cliente": nome_cliente,
        "doc_cliente": doc_cliente,
        "pdf_url": pdf_url or getattr(boleto, "pdf_url", "") or "",
        "linha_digitavel": getattr(boleto, "linha_digitavel", "") if boleto else "",
    }
    subject = f"Boleto da sua mensalidade — Vencimento {lancamento.vencimento:%d/%m/%Y}"

    # Decide anexos
    attach_paths = []
    inline = []
    if pdf_bytes:
        inline.append(("boleto.pdf", pdf_bytes, "application/pdf"))
    elif pdf_path:
        attach_paths.append(Path(pdf_path))
    else:
        exemplo_pdf = Path(getattr(settings, "BASE_DIR", ".")) / "exemplo.pdf"
        attach_paths.append(exemplo_pdf)

    return send_email_html(
        subject=subject,
        to=to_email,
        template="emails/boleto_cobranca.html",
        context=ctx,
        attach_paths=attach_paths,
        attach_inline=inline,
    )
