import speech_recognition as sr
import pyttsx3
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-4-scout:free")

SPEECH_RATE = 300
SILENCE_PAUSE = 1.2


class Vega:
    def __init__(self, key):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=key,
        )

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.recognizer.pause_threshold = SILENCE_PAUSE

        print("Inicializando o Vega Assistant...")

        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
            print(f"Ajustando para ruído ambiente... Nível de ruído: {self.recognizer.energy_threshold}")

    def listen(self):
        with self.microphone as source:
            try:
                print("Ouvindo...")
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio, language="pt-BR")
                print(f"Você disse: {text}")
                return text

            except sr.WaitTimeoutError:
                print("Tempo limite de espera excedido.")
                return None

            except sr.UnknownValueError:
                print("Não entendi o que você disse. Por favor, tente novamente.")
                return None

            except sr.RequestError as e:
                print(f"Ocorreu um erro ao ouvir: {e}")
                return None

    def think(self, text):
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
                        "content": "Você é um assistente virtual chamado Vega, criado para ajudar os usuários com suas perguntas e tarefas. Seja educado, útil e claro em suas respostas."
                    },
                    {"role": "user", "content": text}
                ]
            )

            response_text = response.choices[0].message.content.strip()
            print(f"Vega: {response_text}")
            return response_text

        except Exception as e:
            print(f"Ocorreu um erro com nossa IA: {e}")
            return "Desculpe, ocorreu um erro ao processar sua solicitação."

    def speak(self, text):
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')

            for voice in voices:
                if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break

            engine.setProperty('rate', SPEECH_RATE)

            engine.say(text)
            engine.runAndWait()
            engine.stop()

        except Exception as e:
            print(f"Erro ao falar: {e}")

        finally:
            if engine:
                try:
                    del engine
                except:
                    pass

    def run(self):
        print("=" * 60)
        print("\nBem-vindo ao Vega Assistant! Diga algo para começar...")
        print("=" * 60)
        print("\nComandos: 'sair' para encerrar")
        print("=" * 60)

        while True:
            text = self.listen()

            if not text:
                continue

            if text.lower() in ["sair", "encerrar", "tchau"]:
                print("Encerrando o Vega Assistant. Até a próxima!")
                break

            response = self.think(text)
            self.speak(response)

            print("\n" + "=" * 60)


def main():
    key = os.getenv("OPENROUTER_API_KEY")

    if not key:
        print("A chave do OpenRouter não foi encontrada. Por favor, defina a variável de ambiente OPENROUTER_API_KEY.")
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