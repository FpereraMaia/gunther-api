from __future__ import annotations

import re

# (pattern, category) — matched case-insensitively against description
# Order matters: first match wins
_RULES: list[tuple[str, str]] = [
    # Food delivery
    (r"zé delivery|ze delivery|ifood|rappi|uber.*eat", "Restaurante / Lanchonete / Bar"),
    # Restaurants / bars
    (r"restaurante|lanchonete|pizz|burger|sushi|churrasco|padaria|confeitaria|cafe|bar |koxixo|forneria|rancho|fornerial", "Restaurante / Lanchonete / Bar"),
    # Supermarkets / grocery
    (r"angeloni|mercadinho|supermercado|hortifruti|mercado|padaria aracy|conveniencia|jim\.com", "Supermercados / Mercearia / Padarias / Lojas de Conveniência"),
    # Pharmacy / health
    (r"raia|drogasil|drogaria|farmacia|farmácia|saude|saúde|medic|dentist|clinica|clínica|hospital|nina saude", "Assistência médica e odontológica"),
    # Automotive / fuel
    (r"posto|petrobras|shell|ipiranga|br distrib|combustivel|combustível|pit.?stop|auto.?posto|estacion|estacionamento|urentcar|rent.?car", "Relacionados a Automotivo"),
    # Transport / ride
    (r"uber|99|cabify|taxi|táxi|metrô|metro|onibus|ônibus|passagem|buser", "Transporte"),
    # Marketplace / retail
    (r"mercadolivre|mercado livre|shopee|amazon|aliexpress|shein|magazine|magalu|americanas|submarino|netshoes", "Departamento / Desconto"),
    # Entertainment / streaming
    (r"netflix|spotify|disney|hbo|prime video|globo|premiere|telecine|youtube|apple\.com|deezer|twitch|steam|playstation|xbox", "Entretenimento"),
    # Telecom
    (r"vivo|claro|tim |oi |nextel|net |sky |internet|telefon", "Telecomunicações"),
    # Education
    (r"udemy|alura|coursera|escola|faculdade|universidade|danki|rocketseat|dio\.me|curso", "Educacional"),
    # Pharmacy / drugstore
    (r"panvel|drogaria|farmacia|farmácia", "Assistência médica e odontológica"),
    # Scooters / micro-mobility
    (r"patinetes|scooter|patinete", "Transporte"),
    # Fitness / wellness apps
    (r"queima diaria|queima diária|gympass|totalpass|smartfit|academia", "Esporte / Saúde"),
    # Supermarket local chains
    (r"santa luzia|angeloni|bistek|giassi|imperatriz", "Supermercados / Mercearia / Padarias / Lojas de Conveniência"),
    # Lottery / gambling
    (r"loteria|loterica|lotérica|apostas", "Lazer / Jogos"),
    # PIX to individuals (CNPJ pattern XX.XXX.XXX or personal names via NuPay with no other match)
    (r"pix no crédito|pix no credito|transferência|transferencia|\d{2}\.\d{3}\.\d{3}.*nupay", "Transferência / Pix"),
    # Clothing
    (r"renner|riachuelo|c&a|hm |zara|forever21|farm|reserva|adidas|nike|centauro", "Vestuário / Roupas"),
    # Pet
    (r"petz|cobasi|petshop|pet shop|veterinari", "Pet"),
]

_COMPILED = [(re.compile(pattern, re.IGNORECASE), category) for pattern, category in _RULES]


def infer_category(description: str) -> str | None:
    for pattern, category in _COMPILED:
        if pattern.search(description):
            return category
    return None
