import perplexity

# Criar cliente
client = perplexity.Client()

# Fazer uma pergunta
response = client.search('Explain quantum computing', mode='auto')

# Mostrar resposta
print("Resposta:", response['answer'])