from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker
import random, re

from clientes import services as cs  # usa seus services
# from clientes.models import Cliente  # se precisar consultar direto

UFs = ['AC','AL','AM','AP','BA','CE','DF','ES','GO','MA','MG','MS','MT','PA','PB','PE','PI','PR','RJ','RN','RO','RR','RS','SC','SE','SP','TO']

def only_digits(s): return re.sub(r'\D', '', s or '')

class Command(BaseCommand):
    help = "Gera clientes fake e vínculos (responsável → dependente)."

    def add_arguments(self, parser):
        parser.add_argument('--responsaveis', type=int, default=20)
        parser.add_argument('--dependentes', type=int, default=40)
        parser.add_argument('--empresas', type=int, default=10)

    def handle(self, *args, **opts):
        fake = Faker('pt_BR')
        Faker.seed(42); random.seed(42)

        docs = set()
        def uniq_doc(gen_func):
            # garante CPF/CNPJ único e só dígitos (11 ou 14)
            while True:
                doc = only_digits(gen_func())
                if doc and len(doc) in (11, 14) and doc not in docs:
                    docs.add(doc)
                    return doc

        def rand_endereco():
            uf = random.choice(UFs)
            try:
                bairro = fake.bairro()
            except AttributeError:
                bairro = 'Centro'
            return {
                'cep': fake.postcode(),
                'numero_id': str(fake.random_int(1, 9999)),
                'logradouro': fake.street_name(),
                'bairro': bairro,
                'complemento': 'SN',
                'municipio': fake.city(),
                'estado': uf,
            }

        created_resp_ids = []

        with transaction.atomic():
            # Empresas (CNPJ)
            for _ in range(opts['empresas']):
                data = {
                    'cpf_cnpj': uniq_doc(fake.cnpj),
                    'nome_razao': fake.company(),
                    'email': fake.company_email(),
                    'telefone_emergencial': fake.phone_number(),
                    'telefone_celular': fake.phone_number(),
                    'ativo': True, **rand_endereco(),
                }
                cs.upsert_cliente_por_cpf_cnpj(data)

            # Responsáveis (pessoas)
            for _ in range(opts['responsaveis']):
                nasc = fake.date_of_birth(minimum_age=25, maximum_age=60)
                data = {
                    'cpf_cnpj': uniq_doc(fake.cpf),
                    'nome_razao': fake.name(),
                    'data_nascimento': nasc,
                    'email': fake.free_email(),
                    'telefone_emergencial': fake.phone_number(),
                    'telefone_celular': fake.phone_number(),
                    'ativo': True, **rand_endereco(),
                }
                cli, _ = cs.upsert_cliente_por_cpf_cnpj(data)
                created_resp_ids.append(cli.id)

            # Dependentes (pessoas) + vínculos
            tipos = ['PAI', 'MAE', 'TUTOR', 'OUTRO']
            for _ in range(opts['dependentes']):
                nasc = fake.date_of_birth(minimum_age=5, maximum_age=17)
                data = {
                    'cpf_cnpj': uniq_doc(fake.cpf),
                    'nome_razao': f"{fake.first_name()} {fake.last_name()}",
                    'data_nascimento': nasc,
                    'email': fake.free_email(),
                    'telefone_emergencial': fake.phone_number(),
                    'telefone_celular': fake.phone_number(),
                    'ativo': True, **rand_endereco(),
                }
                dep, _ = cs.upsert_cliente_por_cpf_cnpj(data)

                # Vincula 1 ou 2 responsáveis aleatórios
                if created_resp_ids:
                    for rid in random.sample(created_resp_ids, k=random.randint(1, min(2, len(created_resp_ids)))):
                        cs.vincular_responsavel_dependente(
                            responsavel_id=rid,
                            dependente_id=dep.id,
                            tipo=random.choice(tipos),
                            inicio=None
                        )

        self.stdout.write(self.style.SUCCESS('Seed concluído.'))
