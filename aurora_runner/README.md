# Aurora Runner (Ethical HTTP Automation)

Aurora Runner é uma ferramenta de automação e teste HTTP ética, multiplataforma, em Python 3, com foco em usos autorizados (dev/test/QA). Ela NÃO implementa e não se destina a credential stuffing, brute-force, ou qualquer atividade abusiva.

- Cliente HTTP com headers/cookies/timeouts/redirecionamentos
- Parser de respostas (JSON dot-path e Regex)
- Configuração declarativa via YAML
- Execução concorrente com limite de threads
- Allowlist de domínios, logs detalhados e exportação CSV

Requisitos mínimos:
- Python 3.9+
- Dependências: `requests`, `PyYAML`

Instalação:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -U pip
pip install -r requirements.txt
```

Estrutura:

```
aurora_runner/
├── core/
│   ├── config_loader.py
│   ├── http_client.py
│   ├── proxy_manager.py
│   └── runner.py
├── utils/
│   ├── crypto.py
│   └── logger.py
├── configs/
│   └── example.yaml
├── results/
│   └── (arquivos gerados)
├── logs/
│   └── (logs gerados)
├── requirements.txt
└── main.py
```

Execução (exemplo):

```bash
python main.py --config configs/example.yaml --concurrency 4
```

Exemplo de `configs/example.yaml`:

```yaml
name: Example - httpbin json
allowlist:
  - httpbin.org
steps:
  - name: Fetch JSON
    request:
      method: GET
      url: https://httpbin.org/json
      headers:
        User-Agent: AuroraRunner/1.0
    extract:
      - type: json
        path: slideshow.title
        assign_to: slideshow_title
    asserts:
      - type: regex
        source: text
        pattern: ".*slideshow.*"
    save:
      - type: csv
        file: results/output.csv
        fields: [slideshow_title]
```

Avisos importantes:
- Use apenas em domínios e sistemas que você controla ou possui autorização explícita.
- Respeite `robots.txt`, termos de uso e limites de taxa.
- Esta ferramenta inclui guardrails e não contém mecanismos de brute-force ou wordlists/combos.