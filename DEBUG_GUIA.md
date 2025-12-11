# 🔧 Guia de Debug - Sistema QR Code WhatsApp

## ✅ Correções Implementadas

### 1. **Retorno Correto de Erros**
- ✅ `obter_qr_code()` agora retorna dict com erro em vez de `None`
- ✅ Tratamento de erro 400 (instância duplicada)
- ✅ Mensagens de erro detalhadas no frontend

### 2. **Polling Automático**
- ✅ Template `conexao.html` agora faz polling a cada 3 segundos
- ✅ Máximo de 40 tentativas (2 minutos)
- ✅ Atualiza status em tempo real
- ✅ Redireciona automaticamente ao conectar

### 3. **Sincronização BD**
- ✅ Nova view `verificar_conexao_api()` para polling AJAX
- ✅ Campo `conectado` em `InstanciaZap` atualizado quando detecta conexão
- ✅ Logs detalhados de cada passo

### 4. **Logs Melhorados**
- ✅ `logger.debug()` em cada etapa do fluxo
- ✅ Payloads logados para debug
- ✅ Estados de resposta da API documentados

---

## 🧪 Como Testar

### **Passo 1: Verificar Credenciais**
```bash
python manage.py shell
```
```python
from trigger.models import InstanciaZap
from trigger.services.uazapi_client import UazApiClient

# Listar instâncias no BD
instancias = InstanciaZap.objects.all()
for inst in instancias:
    print(f"Nome: {inst.nome_operador}")
    print(f"Instance ID: {inst.instancia_id}")
    print(f"Token: {inst.token[:20]}...")
    print(f"Conectado: {inst.conectado}")
    print("---")

# Testar client
client = UazApiClient()
print(f"Base URL: {client.base_url}")
print(f"Instance ID: {client.instance_id}")
print(f"Token: {client.token[:20]}...")
```

### **Passo 2: Testar Obtenção de QR**
```python
from trigger.services.uazapi_client import UazApiClient

client = UazApiClient()
qr_result = client.obter_qr_code()

if qr_result.get('error'):
    print(f"❌ Erro: {qr_result['details']}")
else:
    print(f"✅ QR obtido!")
    print(f"Chaves da resposta: {list(qr_result.keys())}")
    
    # Verificar qual chave tem o base64
    for key in ['base64', 'qrcode', 'qr']:
        if key in qr_result:
            print(f"Chave '{key}' encontrada: {qr_result[key][:50]}...")
```

### **Passo 3: Testar Status de Conexão**
```python
client = UazApiClient()
status = client.verificar_status()
print(f"Conectado: {status}")
```

### **Passo 4: Acessar a URL no Navegador**
```
http://localhost:8000/conectar-whatsapp/
```
- Você deve ver o QR Code carregando
- Se houver erro, veja na console do Django (abra com F12)

---

## 🔍 Troubleshooting

### **Problema: "Erro ao gerar QR"**
Abra o console do Django e procure por:
```
[ERROR] Erro crítico QR: ...
```

**Causas comuns:**
1. **Token inválido** - Verifique no BD e no site da UazAPI
2. **Instance ID incorreto** - Deve ser exatamente como registrado na API
3. **API offline** - Teste: `curl https://free.uazapi.com/instance/connect/seu_instance_id`

### **Problema: QR não desaparece após escanear**
O polling não está detectando a conexão. Verifique:
```python
# No Django shell:
client = UazApiClient()
print(client.verificar_status())  # Deve imprimir True
```

Se retornar `False`:
- O WhatsApp pode não ter sincronizado com a API
- A API pode retornar chaves diferentes de `state`
- Execute: `python manage.py shell`
```python
from trigger.services.uazapi_client import UazApiClient
import logging
logging.basicConfig(level=logging.DEBUG)

client = UazApiClient()
status = client.verificar_status()
```
Isso vai imprimir toda a resposta da API.

### **Problema: "Falha ao criar instância"**
Significa que a instância já existe com outro token ou há erro de permissão.

**Solução:**
1. Delete a instância no painel da UazAPI
2. Limpe o BD: `InstanciaZap.objects.all().delete()`
3. Tente novamente

---

## 📊 Fluxo Esperado

```
Usuario acessa /conectar-whatsapp/
    ↓
Backend busca QR Code (GET)
    ↓
SE 404 (não existe)
    ↓
    Cria instância (POST create)
    ↓
    Busca QR novamente (GET)
    ↓
SE 405 (método errado)
    ↓
    Tenta POST direto
    ↓
SE 200
    ↓
    Renderiza HTML com QR base64
    ↓
Frontend inicia polling AJAX a cada 3s
    ↓
Usuario escaneia com WhatsApp
    ↓
API atualiza estado para "connected"
    ↓
Polling detecta e redireciona para /dashboard/
```

---

## 🛠️ Arquivos Modificados

- ✅ `trigger/services/uazapi_client.py` - Melhorias na lógica e logs
- ✅ `trigger/views.py` - Nova view `verificar_conexao_api()`
- ✅ `trigger/urls.py` - Nova rota `/api/verificar-conexao/`
- ✅ `trigger/templates/trigger/conexao.html` - Polling e melhor UX

---

## 🚀 Próximas Melhorias (Opcional)

1. **Cache do QR** - Não regenerar se já gerado
2. **WebSocket** - Polling em tempo real com socket
3. **Múltiplas Instâncias** - Suportar várias no mesmo BD
4. **Retry automático** - Se criar falhar, tenta de novo em 30s

