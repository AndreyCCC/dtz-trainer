import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
import base64
import random
import time
import streamlit.components.v1 as components

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="DTZ Trainer", page_icon="🇩🇪", layout="centered")

LOCAL_API_KEY = "sk-..." # ВСТАВЬ КЛЮЧ

try:
    if "OPENAI_API_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    else:
        client = OpenAI(api_key=LOCAL_API_KEY)
except:
    client = OpenAI(api_key=LOCAL_API_KEY)

PROMPTS = {
    "vorstellung": "Du bist ein DTZ Prüfer (B1). Teil 1. Frage nach: Name, Herkunft, Beruf. Nur EINE Frage.",
    "bild": "Du bist ein DTZ Prüfer (B1). Teil 2. Höre zu. Frage nach Details. Nur EINE Frage.",
    "planung": "Du bist ein DTZ Prüfer (B1). Teil 3. Wir planen eine Party. Mache Vorschläge."
}
GRADING_PROMPT = "Bewertung (B1): Ergebnis (Bestanden/Nicht) und Tipps."

# ==========================================
# 2. ФУНКЦИИ
# ==========================================
def text_to_speech(text):
    try:
        response = client.audio.speech.create(model="tts-1", voice="onyx", input=text)
        return response.content
    except: return None

def get_ai_response(messages):
    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return response.choices[0].message.content

def reset_session():
    st.session_state.chat_history = []
    st.session_state.turn_count = 0
    st.session_state.exam_finished = False
    st.session_state.recorder_key = str(random.randint(1000, 99999))
    if "last_audio" in st.session_state: del st.session_state.last_audio

def go_to(page):
    st.session_state.page = page
    st.rerun()

# --- ХАК С IFRAME ---
def play_audio_hack(audio_bytes):
    """
    Создает невидимый iFrame с правами на автоплей.
    Это работает лучше, чем стандартный st.audio
    """
    b64 = base64.b64encode(audio_bytes).decode()
    
    # HTML код плеера с JS скриптом автозапуска
    html_code = f"""
    <html>
    <body>
        <audio id="player" autoplay controls style="width: 100%;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <script>
            var audio = document.getElementById("player");
            // Пытаемся запустить сразу
            var playPromise = audio.play();
            if (playPromise !== undefined) {{
                playPromise.then(_ => {{
                    console.log("Autoplay started!");
                }})
                .catch(error => {{
                    console.log("Autoplay prevented by browser.");
                }});
            }}
        </script>
    </body>
    </html>
    """
    # Вставляем как iFrame (sandbox позволяет скрипты и автоплей)
    components.html(html_code, height=60)

# ==========================================
# 3. STATE
# ==========================================
if "page" not in st.session_state: st.session_state.page = "menu"
if "exam_type" not in st.session_state: st.session_state.exam_type = "bild"
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "turn_count" not in st.session_state: st.session_state.turn_count = 0
if "recorder_key" not in st.session_state: st.session_state.recorder_key = "1"

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================
if st.session_state.page == "menu":
    st.title("🇩🇪 DTZ Trainer")
    if st.button("🖼️ Teil 2: Bildbeschreibung", use_container_width=True):
        st.session_state.exam_type = "bild"
        reset_session()
        go_to("exam")
        
    st.write("")
    if st.button("🗣️ Teil 3: Planung", use_container_width=True):
        st.session_state.exam_type = "planung"
        reset_session()
        go_to("exam")

elif st.session_state.page == "exam":
    c1, c2 = st.columns([1, 5])
    with c1: 
        if st.button("🔙"): go_to("menu")
    with c2:
        st.progress(st.session_state.turn_count / 4)

    # Приветствие
    if not st.session_state.chat_history:
        start_texts = {
            "vorstellung": "Hallo! Wie heißen Sie?",
            "bild": "Bitte beschreiben Sie dieses Bild.",
            "planung": "Hallo! Wollen wir eine Party organisieren?"
        }
        greeting = start_texts[st.session_state.exam_type]
        st.session_state.chat_history.append(("assistant", greeting))
        st.session_state.last_audio = text_to_speech(greeting)
        st.rerun()

    # ЧАТ
    for role, text in st.session_state.chat_history:
        with st.chat_message(role, avatar="👤" if role == "user" else "👨‍🏫"):
            st.write(text)

    # --- ЗВУК (IFRAME HACK) ---
    # Мы рисуем это ВНИЗУ, сразу над кнопкой записи
    if "last_audio" in st.session_state and st.session_state.last_audio:
        st.write("---")
        # Здесь мы используем наш хак вместо st.audio
        play_audio_hack(st.session_state.last_audio)

    # Управление
    if st.session_state.exam_finished:
        st.success("Prüfung beendet!")
        if st.button("Ergebnis"): go_to("result")
    else:
        st.write("")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                recording_color="#ff4b4b",
                neutral_color="#4CAF50",
                icon_size="4x",
                key=st.session_state.recorder_key,
                pause_threshold=2.0 
            )

        if audio_bytes:
            with st.spinner("..."):
                try:
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=("temp.wav", audio_bytes), language="de")
                    user_text = transcript.text
                except: user_text = ""

                blacklist = ["video hat euch gefallen", "abo da", "untertitel"]
                if any(b in user_text.lower() for b in blacklist) or len(user_text) < 2:
                    st.toast("⚠️ Шум. Повторите.")
                    st.session_state.recorder_key = str(random.randint(1,999))
                    time.sleep(1)
                    st.rerun()

                st.session_state.chat_history.append(("user", user_text))
                st.session_state.turn_count += 1
                
                sys_prompt = PROMPTS[st.session_state.exam_type]
                if st.session_state.turn_count >= 3:
                    sys_prompt = GRADING_PROMPT
                    st.session_state.exam_finished = True

                messages = [{"role": "system", "content": sys_prompt}]
                for r, t in st.session_state.chat_history: messages.append({"role": r, "content": t})
                
                ai_text = get_ai_response(messages)
                st.session_state.chat_history.append(("assistant", ai_text))
                
                st.session_state.last_audio = text_to_speech(ai_text)
                
                st.session_state.recorder_key = str(random.randint(1,999))
                st.rerun()

elif st.session_state.page == "result":
    st.title("Ergebnis")
    st.balloons()
    st.markdown(st.session_state.chat_history[-1][1])
    if st.button("Menü"): go_to("menu")
