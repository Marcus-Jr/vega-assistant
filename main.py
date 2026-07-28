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

from dotenv import load_dotenv

load_dotenv()

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

# Inicializa o mixer do pygame
pygame.mixer.init()


class Vega:
    """
    Vega Assistant V2
    - Ouve enquanto fala (Full Duplex)
    - Pode ser interrompido a qualquer momento
    - Continua a conversa automaticamente
    """

    def __init__(self, key):
        # Cliente OpenRouter (mantido da V1)
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
        )

        # Reconhecimento de voz (mantido da V1)
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

        print("Inicializando o Vega Assistant V2...")
        print("Full Duplex ativado (ouve enquanto fala)")
        print("=" * 60)

        # Ajuste inicial de ruído
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print(
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

        print("Monitor de áudio iniciado")

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
                            print(
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

                            print(f"Comando capturado: {text}")
                            self.interrupted_command = text

                        except Exception:
                            print(
                                "Não consegui entender a interrupção"
                            )
                            self.interrupted_command = None

                        interruption_frames = []

                time.sleep(0.03)

        finally:
            stream.stop_stream()
            stream.close()

    # =========================================================
    # ESCUTAR (mantendo nome da V1)
    # =========================================================

    def listen(self):
        """
        Escuta um comando completo do usuário.
        """

        print("Ouvindo...")

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

                print(f"Você disse: {text}")
                return text

            except sr.WaitTimeoutError:
                print("Tempo limite excedido.")
                return None

            except sr.UnknownValueError:
                if not self.interrupted_command:
                    print("Não entendi o que você disse.")
                return None

            except sr.RequestError as e:
                print(f"Erro no reconhecimento: {e}")
                return None

            except Exception as e:
                print(f"Erro ao ouvir: {e}")
                return None
            
    # =========================================================
    # PENSAR (mantendo nome da V1)
    # =========================================================

    def think(self, text):
        """
        Envia o texto para o OpenRouter e retorna a resposta.
        """

        print("Processando...")

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
                            "educada, útil, clara e relativamente concisa."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                temperature=0.7,
            )

            response_text = response.choices[0].message.content.strip()

            print(f"Vega: {response_text}")
            return response_text

        except Exception as e:
            print(f"Erro na IA: {e}")
            return (
                "Desculpe, ocorreu um erro ao processar sua solicitação."
            )

    # =========================================================
    # FALAR (mantendo nome da V1)
    # =========================================================

    def speak(self, text):
        """
        Fala usando pygame + pyttsx3.
        Pode ser interrompida a qualquer momento.
        """

        print(f"Vega: {text}\n")

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

            # Salva em arquivo
            engine.save_to_file(text, audio_file)
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
                    print("Fala interrompida!")
                    break

                time.sleep(0.05)

        except Exception as e:
            print(f"Erro ao falar: {e}")

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
            print("Processando o comando de interrupção...")
            time.sleep(1.0)

        return self.interrupt_event.is_set()
    
        # =========================================================
    # LOOP PRINCIPAL (mantendo nome da V1)
    # =========================================================

    def run(self):
        print("=" * 60)
        print("Bem-vindo ao Vega Assistant V2!")
        print("Agora eu consigo ouvir ENQUANTO estou falando.")
        print("=" * 60)
        print("Comandos: 'sair', 'encerrar', 'tchau'")
        print("=" * 60)

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

                print(
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

            # Processa e responde
            response = self.think(text)

            # Pode ser interrompido
            self.speak(response)

            print("\n" + "=" * 60)

        # Limpeza
        self.pyaudio.terminate()
        pygame.mixer.quit()

        print("Vega Assistant encerrado.")


# =============================================================
# MAIN (mantido da V1)
# =============================================================

def main():
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        print(
            "A chave do OpenRouter não foi encontrada. "
            "Defina OPENROUTER_API_KEY no arquivo .env."
        )
        return

    try:
        vega = Vega(key)
        vega.run()

    except KeyboardInterrupt:
        print("\nEncerrando o Vega Assistant. Até a próxima!")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")


if __name__ == "__main__":
    main()