# OpenBullet Python 🎯

**Um OpenBullet em Python que não deixa pedra sobre pedra!**

Uma reimplementação completa e robusta do OpenBullet em Python puro, oferecendo todas as funcionalidades do original com arquitetura modular, performance otimizada e código limpo.

## ✨ Características Principais

- 🚀 **Performance Avançada**: Multi-threading assíncrono com controle de concorrência
- 🔒 **Segurança Total**: Criptografia AES para dados sensíveis e credenciais
- 🌐 **HTTP Completo**: Cliente HTTP avançado com suporte a proxies, cookies, headers customizados
- 🔄 **Gerenciamento de Proxies**: Rotação automática, validação e estatísticas em tempo real
- 📝 **Wordlists Inteligentes**: Suporte a múltiplos formatos com cache e filtros avançados
- 🤖 **Captcha Solving**: Integração com múltiplos serviços (2Captcha, AntiCaptcha, CapMonster)
- 📊 **Logging Avançado**: Sistema de logs estruturados com rotação e múltiplos outputs
- 🎛️ **LoliScript Completo**: Parser e executor compatível com configs .loli originais

## 🚀 Instalação Rápida

```bash
# Clone o repositório
git clone https://github.com/your-repo/openbullet-python.git
cd openbullet-python

# Instale as dependências
pip install -r requirements.txt

# Execute o exemplo
python main.py -i
```

## 📁 Estrutura do Projeto

```
openbullet_python/
├── core/                      # Módulos principais
│   ├── http_client.py        # Cliente HTTP avançado
│   ├── proxy_manager.py      # Gerenciador de proxies
│   ├── wordlist_manager.py   # Gerenciador de wordlists
│   ├── config_parser.py      # Parser de configs .loli
│   ├── script_engine.py      # Engine de execução
│   └── captcha_solver.py     # Solucionador de captcha
├── utils/                     # Utilitários
│   ├── logger.py             # Sistema de logging
│   └── crypto.py             # Criptografia e segurança
├── scripts/                   # Configs de exemplo
│   └── example_config.loli   # Config demonstrativo
├── wordlists/                 # Wordlists de exemplo
│   └── example_combo.txt     # Combo list de teste
├── main.py                   # Aplicação principal
├── requirements.txt          # Dependências
└── README.md                # Esta documentação
```

## 🎯 Uso Básico

### Modo Interativo

```bash
python main.py -i
```

```
OB-Python> load config scripts/example_config.loli
OB-Python> load wordlist wordlists/example_combo.txt
OB-Python> run example_config.loli example_combo.txt
```

### Linha de Comando

```bash
# Executar config com wordlist e proxies
python main.py -c scripts/example_config.loli -w wordlists/example_combo.txt -p proxies.txt -t 20

# Execução simples
python main.py -c config.loli -w wordlist.txt
```

### Programático

```python
from main import OpenBulletPython

# Criar instância
ob = OpenBulletPython()

# Executar config
results = ob.run_config(
    config_path="scripts/example_config.loli",
    wordlist_path="wordlists/example_combo.txt",
    threads=10
)

print(f"Hits: {len(results['hits'])}")
```

## 🔧 Configuração Avançada

### Configurar Proxies

```python
from core.proxy_manager import ProxyManager, ProxyConfig, ProxyType

proxy_manager = ProxyManager()

# Adicionar proxy manualmente
proxy = ProxyConfig(
    host="127.0.0.1",
    port=8080,
    proxy_type=ProxyType.HTTP,
    username="user",
    password="pass"
)
proxy_manager.add_proxy(proxy)

# Carregar de arquivo
proxy_manager.load_proxies("proxies.txt")

# Verificar proxies
await proxy_manager.check_all_proxies()
```

### Configurar Captcha

```python
from core.captcha_solver import CaptchaSolver, CaptchaService

solver = CaptchaSolver()

# Configurar 2Captcha
solver.configure_service(
    CaptchaService.TWOCAPTCHA,
    api_key="your_api_key"
)

# Resolver captcha
result = await solver.solve_recaptcha_v2(
    sitekey="6LdCsKAUAAAAABX...",
    page_url="https://example.com"
)

if result.success:
    print(f"Captcha resolvido: {result.solution}")
```

### Criptografia de Dados

```python
from utils.crypto import CryptoManager

crypto = CryptoManager()
crypto.initialize_crypto("master_password")

# Criptografar wordlist
encrypted = crypto.encrypt_wordlist(["user:pass", "admin:123"])

# Criptografar config
config_data = {"name": "test", "settings": {...}}
encrypted_config = crypto.encrypt_config(config_data)

# Criar container seguro
crypto.create_secure_container(
    data={"configs": configs, "wordlists": wordlists},
    container_path="secure_data.enc"
)
```

## 📝 Criando Configs

### Formato LoliScript

```loli
#METADATA
Name = "Meu Config"
Author = "Você"
Category = "Login"

#SETTINGS
MaxThreads = 20
RequestDelay = 1000

#SCRIPT

SET VAR "baseUrl" "https://site.com"

REQUEST POST "<baseUrl>/login"
HEADER "User-Agent" "Mozilla/5.0..."
DATA "username=<USER>&password=<PASS>"

PARSE "token" LR "token\":\"" "\""
PARSE "status" LR "\"status\":\"" "\""

IF <status> == "success"
  SET VAR "result" "HIT"
ENDIF
```

### Funcionalidades Suportadas

- ✅ **REQUEST**: GET, POST, PUT, DELETE, HEAD, OPTIONS
- ✅ **PARSE**: Left/Right delimiters, Regex, JSON
- ✅ **FUNCTION**: Hash, Base64, Random, Timestamp, Regex
- ✅ **IF/ENDIF**: Condicionais complexas
- ✅ **FOR/ENDFOR**: Loops com contadores
- ✅ **SET VAR**: Variáveis dinâmicas
- ✅ **HEADER/DATA/COOKIE**: Customização completa

## 🔍 Logging e Monitoramento

### Sistema de Logs

```python
from utils.logger import Logger, LogLevel, LogFormat

logger = Logger(
    name="MyBot",
    level=LogLevel.INFO,
    format_type=LogFormat.COLORED
)

# Logs estruturados
logger.log_config_execution("config.loli", "user:pass", "hit", 1.23)
logger.log_proxy_status("127.0.0.1:8080", "working", 0.5)
logger.log_captcha_result("recaptcha_v2", "2captcha", True, 15.2)

# Estatísticas
stats = logger.get_statistics()
print(f"Total logs: {stats['total_logs']}")
```

### Arquivos de Log Gerados

- `openbullet.log` - Log principal
- `openbullet_errors.log` - Apenas erros
- `openbullet_structured.json` - Logs estruturados em JSON

## 📊 Performance e Otimização

### Multi-threading Assíncrono

```python
# Configuração de threads otimizada
results = await script_engine.execute_config(
    config=parsed_config,
    wordlist=entries,
    threads=50  # Ajuste baseado no seu hardware
)
```

### Cache Inteligente

```python
# Wordlist com cache
wordlist_manager = WordlistManager(
    cache_enabled=True,
    max_cache_size=1000000
)

# Cache de captcha
captcha_solver = CaptchaSolver(
    cache_enabled=True,
    cache_duration=3600  # 1 hora
)
```

### Estatísticas em Tempo Real

```python
# Estatísticas do proxy manager
proxy_stats = proxy_manager.get_statistics()
# {
#   'total_proxies': 1000,
#   'working_proxies': 856,
#   'avg_success_rate': 85.6,
#   'total_requests': 50000
# }

# Estatísticas do script engine
engine_stats = script_engine.get_statistics()
# {
#   'total_executions': 10000,
#   'hits': 234,
#   'fails': 9500,
#   'avg_execution_time': 1.23
# }
```

## 🛡️ Segurança e Compliance

### Boas Práticas Implementadas

- 🔐 **Criptografia AES-256** para dados sensíveis
- 🔑 **PBKDF2** para derivação de chaves
- 🗑️ **Secure delete** para limpeza de dados
- 🎫 **Session tokens** com expiração
- 🔍 **Validação de integridade** para containers

### Uso Ético

Este software é destinado para:
- ✅ Testes de penetração autorizados
- ✅ Auditoria de segurança
- ✅ Pesquisa educacional
- ✅ Bug bounty programs

**⚠️ NÃO use para atividades ilegais ou não autorizadas!**

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Abra um Pull Request

## 📋 Roadmap

- [ ] Interface gráfica (GUI) com PyQt6
- [ ] Suporte a WebDriver para JavaScript
- [ ] Plugin system para extensões
- [ ] API REST para controle remoto
- [ ] Docker containers
- [ ] Integração com bancos de dados
- [ ] Machine learning para detecção automática
- [ ] Suporte a WebSockets

## 🐛 Solução de Problemas

### Problemas Comuns

**Erro de importação de módulos:**
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/openbullet-python"
```

**Proxies não funcionam:**
- Verifique o formato: `host:port` ou `protocol://user:pass@host:port`
- Teste a conectividade manual
- Verifique rate limits

**Captcha falha:**
- Verifique saldo da API
- Confirme chave de API
- Teste com config simples

**Performance baixa:**
- Reduza número de threads
- Otimize configs (remova delays desnecessários)
- Use proxies mais rápidos

## 📜 Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🙏 Agradecimentos

- Equipe original do OpenBullet por criar a ferramenta base
- Comunidade Python por bibliotecas excelentes
- Contribuidores e testadores beta

## 📞 Suporte

- 📧 Email: support@example.com
- 💬 Discord: [Link do servidor]
- 🐛 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 📖 Wiki: [Documentação completa](https://github.com/your-repo/wiki)

---

**⚡ OpenBullet Python - Porque velocidade e precisão importam!**

*"Feito com ❤️ e muito café ☕"*