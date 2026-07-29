# Vega Assistant

<p align="center">
  <img src="image.png" alt="Vega Assistant">
</p>

<p align="center">
  <img src="https://img.shields.io/github/repo-size/Marcus-Jr/vega-assistant?style=flat-square">
  <img src="https://img.shields.io/github/languages/count/Marcus-Jr/vega-assistant?style=flat-square">
  <img src="https://img.shields.io/github/license/Marcus-Jr/vega-assistant?style=flat-square">
</p>

Vega Assistant é um assistente virtual para desktop desenvolvido em **Python**, projetado para proporcionar uma interação por voz natural em português. O projeto utiliza modelos de IA através da OpenRouter, oferece consultas de clima e horário em tempo real e implementa um modo **Full Duplex**, permitindo que o usuário interrompa o assistente durante a resposta para manter uma conversa mais fluida.

## Funcionalidades

- Conversação por voz em português
- Reconhecimento de fala
- Síntese de voz
- Respostas utilizando IA via OpenRouter
- Modo Full Duplex (ouve enquanto responde)
- Interrupção da fala em tempo real
- Consulta de clima
- Consulta de horário
- Configuração através de arquivo `.env`

## Ecossistema Vega

O projeto está disponível em duas versões:

| Projeto | Descrição |
|---------|-----------|
| **Vega Assistant (Desktop)** | Assistente virtual para desktop desenvolvido em Python com reconhecimento e síntese de voz, integração com IA e modo Full Duplex. |
| **[Vega Assistant Web](https://github.com/Marcus-Jr/vega-assistant-web)** | Versão web construída com Flask e JavaScript, utilizando Web Speech API e uma interface com animação 3D em Three.js. |

## Tecnologias

- Python 3.11+
- OpenRouter
- SpeechRecognition
- pyttsx3
- PyAudio
- Pygame
- Open-Meteo API
- NumPy
- python-dotenv

## Pré-requisitos

- Python 3.11 ou superior
- pip
- Microfone
- Alto-falantes ou fones de ouvido
- Chave de API da OpenRouter

## Instalação

Clone o repositório:

```bash
git clone https://github.com/Marcus-Jr/vega-assistant.git
cd vega-assistant
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente.

**Windows**

```bash
.venv\Scripts\activate
```

**Linux/macOS**

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do projeto:

```env
OPENROUTER_API_KEY=sua_chave
OPENROUTER_MODEL=nemotron-3-ultra-550b-a55b:free
DEFAULT_CITY=São Paulo
```

Execute o projeto:

```bash
python main.py
```

Após iniciar a aplicação, basta conversar com o assistente utilizando o microfone.

## Estrutura do projeto

```text
vega-assistant/
├── services/
├── utils/
├── config/
├── main.py
├── requirements.txt
└── .env
```

## Arquitetura

```text
Microfone
    │
    ▼
SpeechRecognition
    │
    ▼
Processamento da solicitação
    ├── OpenRouter (IA)
    ├── Open-Meteo (Clima)
    └── Serviço de horário
    │
    ▼
pyttsx3
    │
    ▼
Alto-falantes
```

## Implantação

O Vega Assistant é uma aplicação desktop e pode ser executado em qualquer ambiente que possua:

- Python instalado;
- Dependências configuradas;
- Microfone disponível;
- Variáveis de ambiente corretamente definidas.

Para distribuição do aplicativo, recomenda-se utilizar ferramentas como:

- PyInstaller
- auto-py-to-exe

## Testes

Atualmente o projeto não possui testes automatizados.

As principais funcionalidades podem ser verificadas manualmente:

- inicialização do assistente;
- reconhecimento de voz;
- respostas utilizando IA;
- funcionamento do modo Full Duplex;
- consultas de horário;
- consultas de clima e previsão do tempo.

## Autor

**Marcus Everton De França Junior**

GitHub: https://github.com/Marcus-Jr
