# ⚠️ ERRO ENCONTRADO: Token Unauthorized (401)

## 🔴 Problema Identificado

```
POST /instance/create HTTP/1.1" 401 {"error":"Unauthorized"}
```

O token que está no banco de dados é **INVÁLIDO** ou pertence a outra conta/API.

---

## ✅ Solução

### **Opção 1: Usar Token Correto (RECOMENDADO)**

1. **Acesse o painel da UazAPI:**
   - https://free.uazapi.com
   - Faça login com sua conta

2. **Encontre o Token da Instância:**
   - Vá para **Instâncias** ou **Devices**
   - Procure por "fubog1" ou sua instância
   - Copie o token **correto**

3. **Atualize no Django Admin:**
   ```
   http://localhost:8000/admin/
   ```
   - Vá para **Instâncias WhatsApp**
   - Edite a instância "th"
   - Cole o token correto no campo "Token"
   - Salve

4. **Execute o teste novamente:**
   ```bash
   python test_qr_flow.py
   ```

---

### **Opção 2: Usar Token do .env**

Se você tem o token correto em uma variável de ambiente:

1. **Adicione ao `.env`:**
   ```
   UAZAPI_TOKEN=seu_token_correto_aqui
   UAZAPI_INSTANCE=fubog1
   ```

2. **Remova a instância do BD:**
   ```bash
   python manage.py shell
   ```
   ```python
   from trigger.models import InstanciaZap
   InstanciaZap.objects.all().delete()
   ```

3. **Teste novamente** - O sistema vai usar o .env automaticamente

---

### **Opção 3: Criar Nova Instância na API**

Se a instância "fubog1" está problemática:

1. **Delete no painel UazAPI:**
   - https://free.uazapi.com
   - Instâncias → Delete "fubog1"

2. **Crie uma nova instância:**
   - Novo nome: ex. "fubog_nova"
   - Copie o token gerado

3. **Atualize no Django:**
   - Admin → Instâncias WhatsApp
   - Mude para o novo nome e token

4. **Teste:**
   ```bash
   python test_qr_flow.py
   ```

---

## 🔑 Como Obter o Token Correto

### **Na UazAPI (free.uazapi.com):**
1. Login com suas credenciais
2. Vá para a seção de **Instâncias** ou **Devices**
3. Procure a instância (provavelmente "fubog1")
4. Procure por um campo que diz "Token", "API Token", ou "Secret Key"
5. Copie o valor completo

---

## ✨ Depois de Corrigir

Quando o token estiver correto, você verá:

```
✅ QR obtido com sucesso!
   Chaves na resposta: ['qrcode', 'base64']
   ✅ Encontrado 'base64': 5642 caracteres
      Tipo: Data URI (pronto para usar no HTML)
```

---

## 🆘 Ainda Não Funciona?

### **Causa: Token expirou**
- Tokens podem expirar se não forem usados
- Solução: Gere um novo token no painel

### **Causa: Instância deletada**
- Se deletou a instância na API, precisa recriar
- Solução: Crie uma nova no painel

### **Causa: Credenciais de API erradas**
- A API pode exigir um "API Key" além do token
- Verifique na documentação da UazAPI qual é o formato correto

### **Causa: Limite de requisições**
- A versão free pode ter limites
- Solução: Aguarde alguns minutos e tente novamente

---

## 📝 Checklist de Verificação

- [ ] Token copiado corretamente do painel UazAPI
- [ ] Token está no banco de dados (não vazio)
- [ ] Instance ID coincide com o da API
- [ ] Instância existe no painel UazAPI
- [ ] Instância não está deletada
- [ ] Nenhum espaço em branco antes/depois do token
- [ ] Testou com: `python test_qr_flow.py`

---

## 🚀 Próximo Passo

Depois que corrigir o token, acesse:

```
http://localhost:8000/conectar-whatsapp/
```

E veja o QR Code aparecer corretamente!

