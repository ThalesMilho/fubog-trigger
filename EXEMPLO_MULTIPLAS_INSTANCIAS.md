# 💼 Exemplo Prático: Usando Múltiplas Instâncias

Seu sistema agora está pronto para **permitir que cada usuário use seu próprio número de WhatsApp**.

---

## 🎬 Cenário Real

```
Você tem um app de mensagens
├─ Maria: 11 99999-9999
├─ João: 85 98888-8888
├─ Pedro: 21 97777-7777
└─ Ana: 31 96666-6666

Cada um conecta seu próprio número via QR Code
Você gerencia tudo no mesmo banco de dados
```

---

## 🔧 Como Configurar (Passo a Passo)

### **Passo 1: Django Admin**

```
http://localhost:8000/admin/
```

Vá para **Instâncias WhatsApp** e crie cada uma:

```
MARIA:
├─ Nome do Operador: Maria (Atendimento)
├─ Número Telefone: 11999999999
├─ Instance ID: maria_whatsapp
├─ Token: [token_de_maria_do_painel_uazapi]
└─ Conectado: [ ] (unchecked)

JOÃO:
├─ Nome do Operador: João (Vendas)
├─ Número Telefone: 85988888888
├─ Instance ID: joao_vendas
├─ Token: [token_de_joao_do_painel_uazapi]
└─ Conectado: [ ] (unchecked)
```

### **Passo 2: Conectar via QR Code**

Para Maria:
```
http://localhost:8000/conectar-whatsapp/
```
- Vê o QR de maria_whatsapp
- Escaneia com WhatsApp
- Sistema marca como conectado ✅

Para João:
```
# Modificar para aceitar qual instância (veja sugestão abaixo)
# Por enquanto, edite na URL ou use:
```

### **Passo 3: Enviar Mensagens**

Depois que cada uma está conectada, você pode enviar:

```python
from trigger.services.uazapi_client import UazApiClient
from trigger.models import InstanciaZap

# Pegar instância de Maria
maria = InstanciaZap.objects.get(instancia_id='maria_whatsapp')

# Criar client com Maria
from trigger.services.uazapi_client import UazApiClient

class UazApiClientComInstancia(UazApiClient):
    def __init__(self, instancia=None):
        self.instancia = instancia or InstanciaZap.objects.first()
        self.base_url = os.getenv('UAZAPI_URL', 'https://free.uazapi.com').rstrip('/')
        self.token = self.instancia.token
        self.instance_id = self.instancia.instancia_id
        self.headers = {
            "token": self.token,
            "apikey": self.token,
            "Content-Type": "application/json"
        }

# Usar:
client_maria = UazApiClientComInstancia(maria)
resposta = client_maria.enviar_texto('5521987654321', 'Olá!')
```

---

## 🎯 Melhorias Sugeridas (Para Depois)

### **1. Selecionar Instância na URL**

Modificar `conectar_whatsapp` para:

```python
def conectar_whatsapp(request, instancia_id=None):
    if instancia_id:
        instancia = InstanciaZap.objects.get(instancia_id=instancia_id)
    else:
        instancia = InstanciaZap.objects.first()
    
    client = UazApiClient(instancia)  # Passar instância específica
    # ... resto do código
```

Então usar:
```
http://localhost:8000/conectar-whatsapp/maria_whatsapp/
http://localhost:8000/conectar-whatsapp/joao_vendas/
```

### **2. Dashboard de Instâncias**

```python
def dashboard_instancias(request):
    instancias = InstanciaZap.objects.all()
    
    for inst in instancias:
        client = UazApiClient(inst)
        inst.status_real = client.verificar_status()
    
    return render(request, 'instancias.html', {'instancias': instancias})
```

Template HTML:
```html
<table>
  <tr>
    <th>Operador</th>
    <th>Telefone</th>
    <th>Status</th>
    <th>Ação</th>
  </tr>
  {% for inst in instancias %}
  <tr>
    <td>{{ inst.nome_operador }}</td>
    <td>{{ inst.numero_telefone }}</td>
    <td>
      {% if inst.status_real %}
        <span class="badge bg-success">✓ Conectado</span>
      {% else %}
        <span class="badge bg-warning">⏳ Aguardando</span>
      {% endif %}
    </td>
    <td>
      <a href="/conectar-whatsapp/{{ inst.instancia_id }}/" class="btn btn-sm btn-primary">
        Conectar
      </a>
    </td>
  </tr>
  {% endfor %}
</table>
```

### **3. Enviar com Instância Específica**

```python
def enviar_com_instancia(instancia_id, numero, mensagem):
    instancia = InstanciaZap.objects.get(instancia_id=instancia_id)
    
    # Modificar UazApiClient para aceitar instância:
    client = UazApiClient(instancia=instancia)
    return client.enviar_texto(numero, mensagem)

# Usar:
enviar_com_instancia('maria_whatsapp', '5511987654321', 'Olá Maria!')
enviar_com_instancia('joao_vendas', '5585988888888', 'Olá João!')
```

---

## 🔄 Fluxo Multi-Instância

```
Usuario 1 (Maria)
    ↓
GET /conectar-whatsapp/maria_whatsapp/
    ↓
UazApiClient(maria_instancia)
    ├─ instance_id = maria_whatsapp
    ├─ token = maria_token
    └─ base_url = https://free.uazapi.com
    ↓
QR Code gerado ✅

---

Usuario 2 (João)
    ↓
GET /conectar-whatsapp/joao_vendas/
    ↓
UazApiClient(joao_instancia)
    ├─ instance_id = joao_vendas
    ├─ token = joao_token
    └─ base_url = https://free.uazapi.com
    ↓
QR Code gerado ✅

---

Depois, enviar mensagens:
    ↓
Maria envia via maria_whatsapp ✓
João envia via joao_vendas ✓
Tudo sincronizado no BD ✓
```

---

## 📋 Checklist de Implementação

- [ ] Criar instâncias no Django Admin
- [ ] Testar QR de cada uma
- [ ] Modificar UazApiClient para aceitar instância no __init__
- [ ] Atualizar conectar_whatsapp para receber instancia_id
- [ ] Criar dashboard de instâncias
- [ ] Atualizar função enviar para selecionar instância
- [ ] Testar envio de cada número

---

## 💡 Dicas

### **Backup de Dados**
```bash
python manage.py dumpdata trigger.InstanciaZap > instancias_backup.json
```

### **Restaurar**
```bash
python manage.py loaddata instancias_backup.json
```

### **Limpar Instância Específica**
```python
InstanciaZap.objects.filter(instancia_id='maria_whatsapp').delete()
```

### **Mudar Token**
```python
inst = InstanciaZap.objects.get(instancia_id='maria_whatsapp')
inst.token = 'novo_token_aqui'
inst.conectado = False
inst.save()
```

---

## 🚀 Exemplo Completo de Uso

```python
# Teste no Django shell:
python manage.py shell

from trigger.models import InstanciaZap
from trigger.services.uazapi_client import UazApiClient

# Listar todas as instâncias
for inst in InstanciaZap.objects.all():
    print(f"\n📱 {inst.nome_operador}")
    print(f"   Telefone: {inst.numero_telefone}")
    print(f"   ID: {inst.instancia_id}")
    print(f"   Conectado: {inst.conectado}")
    
    # Verificar status real na API
    client = UazApiClient()  # Vai usar a instância no BD
    status = client.verificar_status()
    print(f"   Status API: {status}")
```

---

**Pronto! Você tem um sistema escalável para múltiplas instâncias de WhatsApp.** 🎉

