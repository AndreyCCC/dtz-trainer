import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
import os
import random

# ==========================================
# 1. НАСТРОЙКИ
# ==========================================
st.set_page_config(page_title="DTZ Trainer", page_icon="🇩🇪", layout="centered")

# --- КЛЮЧ ---
LOCAL_API_KEY = "sk-..."  # Вставь свой ключ сюда

try:
    if "OPENAI_API_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    else:
        client = OpenAI(api_key=LOCAL_API_KEY)
except:
    client = OpenAI(api_key=LOCAL_API_KEY)

# --- СЦЕНАРИИ ---
PROMPTS = {
    "vorstellung": "Du bist ein freundlicher DTZ Prüfer (B1). Teil 1: Kennenlernen. Frage nach: Name, Herkunft, Beruf, Familie.",
    "bild": "Du bist ein DTZ Prüfer (B1). Teil 2: Bildbeschreibung. Höre zu. Frage nach Details.",
    "planung": "Du bist ein DTZ Prüfer (B1). Teil 3: Planung. Wir planen eine Party. Mache Vorschläge."
}

GRADING_PROMPT = """
STOPP. Prüfung vorbei.
Bewertung (B1):
### 🏁 Ergebnis: [Bestanden / Nicht bestanden]
- 👍 **Gut:** ...
- ⚠️ **Tipp:** ...
"""

# ==========================================
# 2. ФУНКЦИИ
# ==========================================
def text_to_speech(text):
    try:
        response = client.audio.speech.create(model="tts-1", voice="onyx", input=text)
        return response.content
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def get_ai_response(messages):
    response = client.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return response.choices[0].message.content

def reset_session():
    st.session_state.chat_history = []
    st.session_state.turn_count = 0
    st.session_state.exam_finished = False
    st.session_state.recorder_key = str(random.randint(1000, 99999))
    st.session_state.current_image = f"https://picsum.photos/seed/{random.randint(1,999)}/400/300"
    if "last_audio" in st.session_state: del st.session_state.last_audio

def go_to(page):
    st.session_state.page = page
    st.rerun()

# ==========================================
# 3. STATE
# ==========================================
if "page" not in st.session_state: st.session_state.page = "menu"
if "exam_type" not in st.session_state: st.session_state.exam_type = "bild"
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "turn_count" not in st.session_state: st.session_state.turn_count = 0
if "recorder_key" not in st.session_state: st.session_state.recorder_key = "1"

# Стили
st.markdown("""
<style>
.user-msg {background-color:#e3f2fd; padding:10px; border-radius:10px; text-align:right; color:black; margin: 5px 0;}
.ai-msg {background-color:#f1f8e9; padding:10px; border-radius:10px; text-align:left; color:black; margin: 5px 0;}
.stButton button {width:100%; border-radius:8px; height: 3.5rem; font-weight:bold;}
/* Делаем плеер большим */
audio { width: 100%; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================

# --- МЕНЮ ---
if st.session_state.page == "menu":
    st.title("🇩🇪 DTZ Trainer AI")
    
    col1, col2 = st.columns([1, 5])
    with col1: st.write("👤")
    with col2: 
        if st.button("Teil 1: Vorstellung (О себе)"):
            st.session_state.exam_type = "vorstellung"
            reset_session()
            go_to("exam")

    with col1: st.write("🖼️")
    with col2: 
        if st.button("Teil 2: Bildbeschreibung"):
            st.session_state.exam_type = "bild"
            reset_session()
            go_to("exam")

    with col1: st.write("🗣️")
    with col2: 
        if st.button("Teil 3: Planung (Диалог)"):
            st.session_state.exam_type = "planung"
            reset_session()
            go_to("exam")

# --- ЭКЗАМЕН ---
elif st.session_state.page == "exam":
    # Хедер
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1: 
        if st.button("🔙"): go_to("menu")
    with c2: 
        st.caption(f"Thema: {st.session_state.exam_type.upper()}")
    with c3: 
        if st.button("🔄"): reset_session(); st.rerun()

    # Задание
    if st.session_state.exam_type == "bild":
        st.image(st.session_state.current_image, use_container_width=True)
    elif st.session_state.exam_type == "planung":
        st.info("Aufgabe: Planen Sie eine Party.")
    else:
        st.info("Aufgabe: Stellen Sie sich vor.")

    st.divider()

    # Чат
    chat_container = st.container()
    with chat_container:
        for role, text in st.session_state.chat_history:
            css = "user-msg" if role == "user" else "ai-msg"
            icon = "👤" if role == "user" else "🎓"
            st.markdown(f"<div class='{css}'>{icon} {text}</div>", unsafe_allow_html=True)

    # Приветствие
    if not st.session_state.chat_history:
        start_texts = {
            "vorstellung": "Hallo! Wie heißen Sie?",
            "bild": "Bitte beschreiben Sie dieses Bild.",
            "planung": "Hallo! Wollen wir eine Party organisieren?"
        }
        greeting = start_texts[st.session_state.exam_type]
        st.session_state.chat_history.append(("assistant", greeting))
        
        audio_bytes = text_to_speech(greeting)
        st.session_state.last_audio = audio_bytes
        st.rerun()

    # --- ГЛАВНЫЙ ПЛЕЕР (С ФИКСОМ) ---
    if "last_audio" in st.session_state and st.session_state.last_audio:
        st.write("🔊 Экзаменатор:")
        # ВАЖНО: key=random заставляет Streamlit перерисовать плеер с нуля, что триггерит автоплей
        st.audio(
            st.session_state.last_audio, 
            format="audio/mp3", 
            autoplay=True, 
            key=f"audio_player_{random.randint(0, 1000000)}"
        )

    # Управление
    if st.session_state.exam_finished:
        st.success("Prüfung beendet!")
        if st.button("Zum Ergebnis 🏆"): go_to("result")
    else:
        st.write("---")
        
        audio_bytes = audio_recorder(
            text="",
            recording_color="#ff4b4b",
            neutral_color="#4CAF50",
            icon_size="3x",
            key=st.session_state.recorder_key,
            pause_threshold=2.0 
        )

        if audio_bytes:
            with st.spinner("..."):
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=("temp.wav", audio_bytes), 
                        language="de"
                    )
                    user_text = transcript.text
                except:
                    st.error("Ошибка микрофона")
                    st.stop()

                # Фильтр
                blacklist = ["video hat euch gefallen", "abo da", "untertitel", "copyright"]
                if any(b in user_text.lower() for b in blacklist) or len(user_text) < 2:
                    st.warning("Не расслышал. Повторите.")
                    st.session_state.recorder_key = str(random.randint(1,999))
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
                
                # Генерируем новый звук
                st.session_state.last_audio = text_to_speech(ai_text)
                
                st.session_state.recorder_key = str(random.randint(1,999))
                st.rerun()

# --- РЕЗУЛЬТАТ ---
elif st.session_state.page == "result":
    st.title("Ergebnis")
    st.markdown(st.session_state.chat_history[-1][1])
    if st.button("Menü"): go_to("menu")
