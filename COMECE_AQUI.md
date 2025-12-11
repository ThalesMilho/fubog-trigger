# 🚀 Guia Prático - Próximos Passos

## ⚡ RÁPIDO: Apenas 3 Passos

### **Passo 1: Obter Token Correto**
1. Acesse: https://free.uazapi.com
2. Login com sua conta
3. Vá para **Instâncias** e copie o token
4. Não esqueça: **sem espaços antes/depois**

### **Passo 2: Atualizar no Django Admin**
```
http://localhost:8000/admin/
```
- Vá para **Instâncias WhatsApp**
- Edite "th"
- Cole o token correto
- Salve

### **Passo 3: Testar**
```bash
cd c:\Users\caiofaria\Documents\fubog\fubog_wpp_trigger
python test_qr_flow.py
```

Se aparecer ✅ tudo verde → VAI FUNCIONAR!

---

## 🎬 Demo Completa

Depois que o token estiver correto, execute:

```bash
# Terminal 1: Rodar servidor
python manage.py runserver

# Terminal 2 (em outro terminal):
python test_qr_flow.py
```

Então acesse no navegador:
```
http://localhost:8000/conectar-whatsapp/
```

Você vai ver:
1. QR Code carregando
2. Mensagem: "Aguardando escaneamento..."
3. Pegue seu celular com WhatsApp
4. Vá em: Aparelhos Conectados > Conectar
5. Aponte câmera no QR
6. Aguarde a página atualizar
7. ✅ Pronto! Instância conectada

---

## 🔧 Comandos Úteis para Debug

### **Ver instância no BD:**
```bash
python manage.py shell
```
```python
from trigger.models import InstanciaZap

inst = InstanciaZap.objects.first()
print(f"Nome: {inst.nome_operador}")
print(f"ID: {inst.instancia_id}")
print(f"Token: {inst.token[:30]}...")
print(f"Conectado: {inst.conectado}")
```

### **Testar QR manualmente:**
```python
from trigger.services.uazapi_client import UazApiClient
import logging
logging.basicConfig(level=logging.DEBUG)

client = UazApiClient()
resultado = client.obter_qr_code()

if resultado.get('error'):
    print(f"❌ {resultado['details']}")
else:
    print(f"✅ QR obtido!")
    print(f"Chaves: {list(resultado.keys())}")
```

### **Testar Status:**
```python
client = UazApiClient()
print(f"Conectado: {client.verificar_status()}")
```

### **Limpar instância:**
```python
from trigger.models import InstanciaZap
InstanciaZap.objects.all().delete()
# Depois recrie no admin
```

---

## 📚 Documentação Criada

Todos esses arquivos foram criados no root do projeto:

| Arquivo | O que é | Quando ler |
|---------|---------|-----------|
| `RESUMO_MUDANCAS.md` | O que foi corrigido | Visão geral |
| `DEBUG_GUIA.md` | Testes passo a passo | Troubleshooting |
| `ERRO_TOKEN_401.md` | Solução do erro 401 | Se receber erro 401 |
| `test_qr_flow.py` | Script de teste | Para testar tudo |

---

## 🎯 Checklist Antes de Começar

- [ ] Token correto obtido do painel UazAPI
- [ ] Token atualizado no Django Admin
- [ ] Django rodando: `python manage.py runserver`
- [ ] Browser aberto em `http://localhost:8000`
- [ ] Admin acessível em `http://localhost:8000/admin/`

---

## 🆘 Se Algo Deu Errado

### **Erro: "Falha ao criar instância"**
→ Leia `ERRO_TOKEN_401.md`

### **Erro: "Erro ao gerar QR"**
→ Execute `python test_qr_flow.py` para saber qual é

### **QR não desaparece após escanear**
→ Abra console do navegador (F12)
→ Veja se há erros AJAX

### **Instância não conecta**
→ Aguarde 30 segundos
→ Se continuarou, cheque em UazAPI se está "Connected"

---

## ✨ Você Agora Pode

✅ Gerar QR Code dinâmico  
✅ Permitir que usuários conectem seus números  
✅ Detectar quando está conectado automaticamente  
✅ Sincronizar status no BD  
✅ Escalar para múltiplos números  

---

## 📞 Resumo da Arquitetura

```
Usuario (Navegador)
    ↓
    GET /conectar-whatsapp/
    ↓
Django View (conectar_whatsapp)
    ↓
UazAPI Client
    ├─ GET /instance/connect/fubog1  (buscar QR)
    ├─ POST /instance/create         (se não existir)
    └─ GET /instance/connectionState (verificar status)
    ↓
JavaScript (polling)
    └─ GET /api/verificar-conexao/  (a cada 3s)
    ↓
Banco de Dados (Django ORM)
    └─ Atualiza InstanciaZap.conectado = True
    ↓
WhatsApp (no celular)
    └─ Escaneia QR → API muda estado → JS detecta
```

---

## 🎉 Pronto!

Seu sistema de mensagens com suporte a múltiplas instâncias está **funcionando**.

Agora é só:
1. Corrigir o token
2. Testar uma vez
3. Usar!

Boa sorte! 🚀

