"""
VEGA - Assistente Virtual V3
Full Duplex com PyAudio + Pygame + pyttsx3
Modelo de IA gratuito via OpenRouter
- Ouve enquanto fala (Full Duplex)
- Pode ser interrompido a qualquer momento
- Continua a conversa automaticamente
- Responde hora atual e clima (inclusive previsão para dias futuros) diretamente, sem depender da IA
"""

import speech_recognition as sr
from openai import OpenAI
import pyttsx3
import os
import threading
import pyaudio
import pygame
import numpy as np
import time
import tempfile
import requests
from datetime import datetime
from collections import Counter
import re

from dotenv import load_dotenv

load_dotenv()

# =========================
# VISUAL DO TERMINAL (cores e ícones)
# =========================

try:
    from colorama import init as _colorama_init, Fore, Back, Style
    _colorama_init(autoreset=True)
except ImportError:
    # Fallback caso o colorama não esteja instalado:
    # o programa continua funcionando, só sem cores.
    class _Dummy:
        def __getattr__(self, _name):
            return ""

    Fore = Back = Style = _Dummy()


def _line(char="─", width=60, color=Fore.CYAN):
    print(f"{color}{char * width}{Style.RESET_ALL}")


VEGA_ASCII_ART = [
    "██╗   ██╗███████╗ ██████╗  █████╗ ",
    "██║   ██║██╔════╝██╔════╝ ██╔══██╗",
    "██║   ██║█████╗  ██║  ███╗███████║",
    "╚██╗ ██╔╝██╔══╝  ██║   ██║██╔══██║",
    " ╚████╔╝ ███████╗╚██████╔╝██║  ██║",
    "  ╚═══╝  ╚══════╝ ╚═════╝ ╚═╝  ╚═╝",
]


def print_vega_banner(subtitles=None):
    """Banner ASCII art com o nome VEGA dentro de uma caixa."""
    subtitles = subtitles or ["Vega Assistant V3", "Assistente Virtual com IA"]

    content_width = max(
        max(len(line) for line in VEGA_ASCII_ART),
        max(len(line) for line in subtitles),
    ) + 4

    top = "╔" + "═" * content_width + "╗"
    bottom = "╚" + "═" * content_width + "╝"
    empty = "║" + " " * content_width + "║"

    print(f"\n{Fore.CYAN}{Style.BRIGHT}{top}")
    print(empty)
    for line in VEGA_ASCII_ART:
        print("║" + line.center(content_width) + "║")
    print(empty)
    for line in subtitles:
        print("║" + line.center(content_width) + "║")
    print(empty)
    print(f"{bottom}{Style.RESET_ALL}\n")


def print_banner(title, subtitle=None, width=60):
    """Caixa de destaque simples (usada fora da tela de abertura)."""
    print()
    print(f"{Fore.CYAN}{Style.BRIGHT}╔{'═' * (width - 2)}╗")
    print(f"║{title.center(width - 2)}║")
    if subtitle:
        print(f"║{subtitle.center(width - 2)}║")
    print(f"╚{'═' * (width - 2)}╝{Style.RESET_ALL}")
    print()


def print_section(text, width=60):
    """Separador leve usado entre turnos de conversa."""
    _line("─", width, Fore.CYAN + Style.DIM)


def print_info(text):
    print(f"{Fore.CYAN}{Style.RESET_ALL}{text}")


def print_success(text):
    print(f"{Fore.GREEN}{text}{Style.RESET_ALL}")


def print_listening(text):
    print(f"{Fore.YELLOW}{text}{Style.RESET_ALL}")


def print_processing(text):
    print(f"{Fore.CYAN}{text}{Style.RESET_ALL}")


def print_user(text):
    print(f"{Fore.MAGENTA}{Style.BRIGHT}Você:{Style.RESET_ALL} {text}")


def print_vega(text):
    print(f"{Fore.BLUE}{Style.BRIGHT}Vega:{Style.RESET_ALL} {text}")


def print_warning(text):
    print(f"{Fore.YELLOW}{text}{Style.RESET_ALL}")


def print_error(text):
    print(f"{Fore.RED}{text}{Style.RESET_ALL}")


def print_interrupt(text):
    print(f"{Fore.RED}{Style.BRIGHT}{text}{Style.RESET_ALL}")


# =========================
# CONFIGURAÇÕES
# =========================

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nemotron-3-ultra-550b-a55b:free"
)

SPEECH_RATE = 300
SILENCE_PAUSE = 1.2

# Configurações do Full Duplex
INTERRUPTION_THRESHOLD = 1500
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

# Cidade usada quando o usuário pergunta o clima sem especificar o local
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "São Paulo")

# Descrições em português para os códigos de clima da Open-Meteo (WMO)
WEATHER_CODES = {
    0: "céu limpo",
    1: "poucas nuvens",
    2: "parcialmente nublado",
    3: "nublado",
    45: "névoa",
    48: "névoa com geada",
    51: "garoa fraca",
    53: "garoa moderada",
    55: "garoa forte",
    61: "chuva fraca",
    63: "chuva moderada",
    65: "chuva forte",
    71: "neve fraca",
    73: "neve moderada",
    75: "neve forte",
    80: "pancadas de chuva fracas",
    81: "pancadas de chuva moderadas",
    82: "pancadas de chuva fortes",
    95: "trovoadas",
    96: "trovoadas com granizo leve",
    99: "trovoadas com granizo forte",
}

# Inicializa o mixer do pygame
pygame.mixer.init()


class Vega:
    """
    Vega Assistant V3
    - Ouve enquanto fala (Full Duplex)
    - Pode ser interrompido a qualquer momento
    - Continua a conversa automaticamente
    """

    def __init__(self, key):
        # Cliente OpenRouter (modelo gratuito)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
        )

        # Reconhecimento de voz
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # PyAudio para monitoramento contínuo
        self.pyaudio = pyaudio.PyAudio()

        # Estados do assistente
        self.speaking = False
        self.interrupt_event = threading.Event()
        self.running = True

        # Buffer de áudio
        self.audio_buffer = []
        self.audio_lock = threading.Lock()

        # Comando capturado durante a interrupção
        self.interrupted_command = None

        # Configuração do reconhecimento
        self.recognizer.energy_threshold = 200
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = SILENCE_PAUSE

        print_vega_banner()
        print_info("Full Duplex ativado (ouve enquanto fala)")
        _line("═")

        # Ajuste inicial de ruído
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print_success(
                f"Ruído ambiente ajustado: "
                f"{self.recognizer.energy_threshold}"
            )

    # =========================================================
    # MONITORAMENTO CONTÍNUO
    # =========================================================

    def monitor_audio(self):
        """
        Thread que monitora o microfone continuamente.
        Detecta quando o usuário tenta interromper a fala do Vega.
        """

        print_success("Monitor de áudio iniciado")

        stream = self.pyaudio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )

        high_count = 0
        MIN_HIGH_COUNT = 3

        recording_interruption = False
        interruption_frames = []

        silence_frames = 0
        MAX_SILENCE_FRAMES = 30

        try:
            while self.running:
                data = stream.read(
                    CHUNK_SIZE,
                    exception_on_overflow=False
                )

                audio_data = np.frombuffer(data, dtype=np.int16)
                level = np.abs(audio_data).mean()

                # Enquanto o Vega estiver falando
                if self.speaking:

                    # Guarda o áudio em buffer
                    with self.audio_lock:
                        self.audio_buffer.append(data)

                        max_frames = int(
                            5 * SAMPLE_RATE / CHUNK_SIZE
                        )

                        if len(self.audio_buffer) > max_frames:
                            self.audio_buffer.pop(0)

                    # Detecta interrupção
                    if level > INTERRUPTION_THRESHOLD:
                        high_count += 1

                        if (
                            high_count >= MIN_HIGH_COUNT
                            and not self.interrupt_event.is_set()
                        ):
                            print_interrupt(
                                f"Interrupção detectada! "
                                f"Nível: {level:.0f}"
                            )

                            self.interrupt_event.set()
                            pygame.mixer.music.stop()

                            recording_interruption = True
                            interruption_frames = list(
                                self.audio_buffer
                            )
                    else:
                        high_count = 0

                # Continua gravando a frase do usuário
                if recording_interruption:
                    interruption_frames.append(data)

                    if level < INTERRUPTION_THRESHOLD / 2:
                        silence_frames += 1
                    else:
                        silence_frames = 0

                    # Usuário terminou de falar
                    if silence_frames >= MAX_SILENCE_FRAMES:
                        recording_interruption = False
                        silence_frames = 0

                        audio_bytes = b"".join(interruption_frames)

                        audio_sr = sr.AudioData(
                            audio_bytes,
                            SAMPLE_RATE,
                            2
                        )

                        try:
                            text = self.recognizer.recognize_google(
                                audio_sr,
                                language="pt-BR"
                            )

                            print_success(f"Comando capturado: {text}")
                            self.interrupted_command = text

                        except Exception:
                            print_warning(
                                "Não consegui entender a interrupção"
                            )
                            self.interrupted_command = None

                        interruption_frames = []

                time.sleep(0.03)

        finally:
            stream.stop_stream()
            stream.close()

    # =========================================================
    # ESCUTAR
    # =========================================================

    def listen(self):
        """
        Escuta um comando completo do usuário.
        """

        print_listening("Ouvindo...")

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(
                source,
                duration=0.5
            )

            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=10,
                    phrase_time_limit=20
                )

                text = self.recognizer.recognize_google(
                    audio,
                    language="pt-BR"
                )

                print_user(text)
                return text

            except sr.WaitTimeoutError:
                print_warning("Tempo limite excedido.")
                return None

            except sr.UnknownValueError:
                if not self.interrupted_command:
                    print_warning("Não entendi o que você disse.")
                return None

            except sr.RequestError as e:
                print_error(f"Erro no reconhecimento: {e}")
                return None

            except Exception as e:
                print_error(f"Erro ao ouvir: {e}")
                return None

    # =========================================================
    # HORA E CLIMA (respostas diretas, sem passar pela IA)
    # =========================================================

    def get_time(self):
        """
        Retorna a hora atual formatada, com saudação de acordo com o período do dia.
        """

        now = datetime.now()
        hour = now.hour

        if hour < 12:
            greeting = "Bom dia"
        elif hour < 18:
            greeting = "Boa tarde"
        else:
            greeting = "Boa noite"

        return f"{greeting}! Agora são {now.strftime('%H:%M')}."

    def get_weather(self, city, day_offset=None, week_summary=False):
        """
        Busca o clima de uma cidade usando a API gratuita Open-Meteo
        (geocodificação + previsão), sem necessidade de chave de API.

        - day_offset=None e week_summary=False -> clima atual (agora)
        - day_offset=0 -> hoje (máx/mín do dia)
        - day_offset=1 -> amanhã
        - day_offset=N -> daqui a N dias (ex: um dia da semana específico)
        - week_summary=True -> resumo dos próximos 7 dias
        """

        try:
            geo_response = requests.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": city,
                    "count": 1,
                    "language": "pt",
                    "format": "json",
                },
                timeout=5,
            )
            geo_data = geo_response.json()
            results = geo_data.get("results")

            if not results:
                return f"Não consegui encontrar a cidade {city}."

            place = results[0]
            latitude = place["latitude"]
            longitude = place["longitude"]
            place_name = place.get("name", city)

            forecast_response = requests.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current_weather": True,
                    "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                    "forecast_days": 8,
                    "timezone": "auto",
                },
                timeout=5,
            )
            forecast_data = forecast_response.json()

            # Clima atual (sem dia específico solicitado)
            if day_offset is None and not week_summary:
                current = forecast_data.get("current_weather")

                if not current:
                    return f"Não consegui obter o clima de {place_name} agora."

                temperature = current["temperature"]
                code = current["weathercode"]
                description = WEATHER_CODES.get(code, "condição não identificada")

                return (
                    f"Em {place_name} agora está {description}, "
                    f"com {temperature:.0f} graus."
                )

            daily = forecast_data.get("daily")

            if not daily:
                return f"Não consegui obter a previsão de {place_name}."

            # Resumo da semana que vem (próximos 7 dias)
            if week_summary:
                codes = daily["weathercode"][1:8]
                max_temps = daily["temperature_2m_max"][1:8]
                min_temps = daily["temperature_2m_min"][1:8]

                if not codes:
                    return f"Não consegui obter a previsão semanal de {place_name}."

                dominant_code = Counter(codes).most_common(1)[0][0]
                description = WEATHER_CODES.get(dominant_code, "condição variada")

                return (
                    f"Na semana que vem em {place_name}, a previsão é de "
                    f"{description}, com temperaturas entre "
                    f"{min(min_temps):.0f} e {max(max_temps):.0f} graus."
                )

            # Previsão para um dia específico
            index = day_offset
            dates = daily["time"]

            if index >= len(dates):
                return f"Só consigo prever até {len(dates) - 1} dias à frente, desculpe."

            date_str = dates[index]
            tmax = daily["temperature_2m_max"][index]
            tmin = daily["temperature_2m_min"][index]
            code = daily["weathercode"][index]
            description = WEATHER_CODES.get(code, "condição não identificada")

            day_label = self._format_day_label(day_offset, date_str)

            return (
                f"Para {day_label} em {place_name}, a previsão é de "
                f"{description}, com mínima de {tmin:.0f} e "
                f"máxima de {tmax:.0f} graus."
            )

        except Exception as e:
            print_error(f"Erro ao buscar clima: {e}")
            return "Desculpe, não consegui buscar a previsão do tempo agora."

    def _format_day_label(self, day_offset, date_str):
        """
        Converte um deslocamento de dias em um rótulo falado
        (ex: 'amanhã', 'quinta-feira (01/08)').
        """

        if day_offset == 0:
            return "hoje"

        if day_offset == 1:
            return "amanhã"

        if day_offset == 2:
            return "depois de amanhã"

        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        weekday_names = [
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        ]

        weekday_name = weekday_names[date_obj.weekday()]

        return f"{weekday_name} ({date_obj.strftime('%d/%m')})"

    def _detect_forecast_target(self, text):
        """
        Analisa o texto e decide para qual dia é a previsão pedida.
        Retorna (day_offset, week_summary):
        - (None, False) -> clima atual
        - (N, False)     -> daqui a N dias
        - (None, True)   -> resumo da semana que vem
        """

        text_lower = text.lower()

        if (
            "semana que vem" in text_lower
            or "próxima semana" in text_lower
            or "proxima semana" in text_lower
        ):
            return None, True

        if "depois de amanhã" in text_lower or "depois de amanha" in text_lower:
            return 2, False

        if "amanhã" in text_lower or "amanha" in text_lower:
            return 1, False

        if "hoje" in text_lower:
            return 0, False

        weekday_map = {
            "segunda": 0,
            "terça": 1,
            "terca": 1,
            "quarta": 2,
            "quinta": 3,
            "sexta": 4,
            "sábado": 5,
            "sabado": 5,
            "domingo": 6,
        }

        for name, target_weekday in weekday_map.items():
            if name in text_lower:
                today_weekday = datetime.now().weekday()
                diff = (target_weekday - today_weekday) % 7

                if diff == 0:
                    diff = 7

                return diff, False

        return None, False

    def extract_city(self, text):
        """
        Extrai o nome da cidade a partir de frases como
        'qual o clima em Curitiba' ou 'previsão do tempo para São Paulo'.
        Retorna None se nenhuma cidade for encontrada.
        """

        for preposition in [" em ", " de ", " para ", " no ", " na "]:
            index = text.lower().rfind(preposition)

            if index != -1:
                city = text[index + len(preposition):].strip(" ?.!")

                if city:
                    return city

        return None

    def try_direct_answer(self, text):
        """
        Responde diretamente perguntas sobre hora e clima, sem chamar a IA.
        Retorna a resposta pronta, ou None se o texto não for sobre isso.
        """

        text_lower = text.lower()

        time_triggers = [
            "que horas",
            "qual é a hora",
            "qual a hora",
            "hora atual",
            "me diz a hora",
            "que horas são",
        ]

        if any(trigger in text_lower for trigger in time_triggers):
            return self.get_time()

        weather_triggers = [
            "clima",
            "tempo em",
            "tempo agora",
            "previsão",
            "previsao",
            "vai chover",
            "como está o tempo",
            "temperatura em",
        ]

        if any(trigger in text_lower for trigger in weather_triggers):
            city = self.extract_city(text) or DEFAULT_CITY
            day_offset, week_summary = self._detect_forecast_target(text)
            return self.get_weather(
                city,
                day_offset=day_offset,
                week_summary=week_summary
            )

        return None

    # =========================================================
    # PENSAR
    # =========================================================

    def think(self, text):
        """
        Envia o texto para o OpenRouter e retorna a resposta.
        """

        print_processing("Processando...")

        try:
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/vega-assistant",
                    "X-OpenRouter-Title": "Vega Assistant",
                },
                model=OPENROUTER_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é um assistente virtual chamado Vega. "
                            "Responda sempre em português, de forma "
                            "educada, útil, clara e relativamente concisa. "
                            "Sua resposta será convertida em áudio e falada "
                            "em voz alta, então responda em texto corrido, "
                            "sem markdown: não use asteriscos, hashtags, "
                            "listas numeradas, marcadores ou qualquer "
                            "formatação especial."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
            )

            response_text = response.choices[0].message.content.strip()

            print_vega(response_text)
            return response_text

        except Exception as e:
            print_error(f"Erro na IA: {e}")
            return (
                "Desculpe, ocorreu um erro ao processar sua solicitação."
            )

    # =========================================================
    # LIMPEZA DE MARKDOWN (para a fala soar natural)
    # =========================================================

    def _clean_markdown(self, text):
        """
        Remove formatação markdown do texto (negrito, itálico, títulos,
        listas, links, blocos de código etc.) para que o pyttsx3 não
        leia símbolos como asteriscos e hashtags em voz alta.
        """

        cleaned = text

        # Remove blocos de código ```...```
        cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

        # Remove código inline `texto`
        cleaned = re.sub(r"`([^`]*)`", r"\1", cleaned)

        # Remove negrito/itálico (**texto**, __texto__, *texto*, _texto_)
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
        cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
        cleaned = re.sub(r"(?<!\w)_(.*?)_(?!\w)", r"\1", cleaned)

        # Remove cabeçalhos markdown (#, ##, ### ...)
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)

        # Remove links markdown [texto](url) -> texto
        cleaned = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", cleaned)

        # Remove marcadores de lista (-, *, •) no início da linha
        cleaned = re.sub(r"^\s*[\-\*•]\s+", "", cleaned, flags=re.MULTILINE)

        # Remove numeração de listas (1. 2. etc.)
        cleaned = re.sub(r"^\s*\d+[\.\)]\s+", "", cleaned, flags=re.MULTILINE)

        # Remove linhas horizontais (---, ***, ___)
        cleaned = re.sub(r"^[\-\*_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)

        # Colapsa quebras de linha em pausas naturais para a fala
        cleaned = re.sub(r"\n{2,}", ". ", cleaned)
        cleaned = cleaned.replace("\n", " ")

        # Remove espaços duplicados
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        return cleaned

    # =========================================================
    # FALAR
    # =========================================================

    def speak(self, text):
        """
        Fala usando pygame + pyttsx3.
        Pode ser interrompida a qualquer momento.
        """

        self.speaking = True
        self.interrupt_event.clear()
        self.interrupted_command = None

        # Limpa o buffer
        with self.audio_lock:
            self.audio_buffer = []

        audio_file = os.path.join(
            tempfile.gettempdir(),
            "vega_fala.wav"
        )

        speech_text = self._clean_markdown(text)

        try:
            # Gera o áudio
            engine = pyttsx3.init()

            voices = engine.getProperty("voices")

            for voice in voices:
                name = voice.name.lower()

                if (
                    "brazil" in name
                    or "portuguese" in name
                    or "brasil" in name
                ):
                    engine.setProperty("voice", voice.id)
                    break

            engine.setProperty("rate", SPEECH_RATE)
            engine.setProperty("volume", 1.0)

            # Salva em arquivo (usando o texto já sem markdown)
            engine.save_to_file(speech_text, audio_file)
            engine.runAndWait()
            engine.stop()

            # Garante que o arquivo foi criado
            time.sleep(0.2)

            # Reproduz com pygame
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()

            # Espera terminar OU ser interrompido
            while pygame.mixer.music.get_busy():

                if self.interrupt_event.is_set():
                    pygame.mixer.music.stop()
                    print_interrupt("Fala interrompida!")
                    break

                time.sleep(0.05)

        except Exception as e:
            print_error(f"Erro ao falar: {e}")

        finally:
            self.speaking = False

            try:
                if os.path.exists(audio_file):
                    pygame.mixer.music.unload()
                    os.remove(audio_file)
            except Exception:
                pass

        # Aguarda o reconhecimento da interrupção
        if self.interrupt_event.is_set():
            print_processing("Processando o comando de interrupção...")
            time.sleep(1.0)

        return self.interrupt_event.is_set()

    # =========================================================
    # LOOP PRINCIPAL
    # =========================================================

    def run(self):
        print_info("Agora eu consigo ouvir ENQUANTO estou falando.")
        print_info("Comandos: 'sair', 'encerrar', 'tchau'")
        _line("═")

        # Inicia o monitor em thread separada
        monitor = threading.Thread(
            target=self.monitor_audio,
            daemon=True
        )

        monitor.start()

        time.sleep(1)

        while self.running:

            # Se houve interrupção, usa o comando capturado
            if self.interrupted_command:
                text = self.interrupted_command
                self.interrupted_command = None

                print_interrupt(
                    f"Usando comando da interrupção: {text}"
                )

            else:
                # Escuta normalmente
                text = self.listen()

            if not text:
                continue

            # Encerrar
            if text.lower() in [
                "sair",
                "encerrar",
                "tchau",
                "desligar",
            ]:
                self.speak("Até a próxima!")
                self.running = False
                break

            # Respostas diretas (hora / clima), sem passar pela IA
            direct_response = self.try_direct_answer(text)

            if direct_response:
                self.speak(direct_response)
                print_section("")
                continue

            # Processa e responde
            response = self.think(text)

            # Pode ser interrompido
            self.speak(response)

            print_section("")

        # Limpeza
        self.pyaudio.terminate()
        pygame.mixer.quit()

        print_success("Vega Assistant encerrado.")


# =============================================================
# MAIN
# =============================================================

def main():
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        print_error(
            "A chave do OpenRouter não foi encontrada. "
            "Defina OPENROUTER_API_KEY no arquivo .env."
        )
        return

    try:
        vega = Vega(key)
        vega.run()

    except KeyboardInterrupt:
        print_warning("\nEncerrando o Vega Assistant. Até a próxima!")

    except Exception as e:
        print_error(f"Ocorreu um erro: {e}")


if __name__ == "__main__":
    main()