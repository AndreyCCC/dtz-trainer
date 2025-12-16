import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
import os
import random

# ==========================================
# 1. НАСТРОЙКИ И ДИЗАЙН (CSS)
# ==========================================
st.set_page_config(page_title="DTZ Trainer AI", page_icon="🇩🇪", layout="centered")

st.markdown("""
    <style>
    /* 1. Глобальный темный фон */
    .stApp {
        background-color: #121212; /* Еще более глубокий черный */
    }

    /* 2. Текст везде белый */
    h1, h2, h3, p, label, div {
        color: #E0E0E0 !important;
        font-family: sans-serif;
    }

    /* 3. Пузыри чата (Белые с черным текстом) */
    .stChatMessage {
        background-color: #FFFFFF !important;
        border-radius: 18px;
        padding: 15px;
        margin-bottom: 12px;
        border: none;
    }
    .stChatMessage p, .stChatMessage div {
        color: #000000 !important; /* Текст внутри чата черный */
    }

    /* 4. Скрытие рамок у аудио-компонента (Фикс убогости) */
    iframe {
        border: none !important;
        background: transparent !important;
    }

    /* 5. Красивая кнопка старта */
    div.stButton > button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        border: none;
        padding: 15px 30px;
        border-radius: 30px;
        font-size: 18px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: 0.3s;
    }
    div.stButton > button:hover {
        transform: scale(1.02);
    }
    
    /* 6. Картинка */
    .stImage img {
        border-radius: 12px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.5);
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. BACKEND (МОЗГИ)
# ==========================================
# Пробуем взять ключ из Секретов (на сервере), иначе ищем локально (для тестов)
api_key = st.secrets.get("OPENAI_API_KEY")

if not api_key:
    st.error("Нет API ключа! Настройте Secrets.")
    st.stop()
    
client = OpenAI(api_key=api_key)
CHAT_MODEL = "gpt-4o-mini"
MAX_TURNS = 3

SYSTEM_PROMPT = """
Rolle: Prüfer für den Deutsch-Test für Zuwanderer (DTZ).
Niveau: A2/B1.
Aufgabe: Teil 2 - Bildbeschreibung.

REGELN:
1.  **Sprache:** Einfaches Deutsch, kurze Sätze.
2.  **Ablauf:** Stelle immer nur EINE Frage.
3.  **Ende:** Nach 3 Fragen beende das Gespräch mit Bewertung.

Wenn [STOP_EXAM] gesendet wird, gib sofort die Bewertung (B1/A2/Nicht bestanden).
"""

def cleanup_audio():
    if os.path.exists("output_voice.mp3"):
        try:
            os.remove("output_voice.mp3")
        except:
            pass

def speech_to_text(audio_bytes):
    with open("temp_input.mp3", "wb") as f:
        f.write(audio_bytes)
    with open("temp_input.mp3", "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, language="de", temperature=0.2
        )
    return transcript.text

def get_ai_response(messages):
    response = client.chat.completions.create(
        model=CHAT_MODEL, messages=messages, max_tokens=400, temperature=0.7 
    )
    return response.choices[0].message.content

def text_to_speech(text):
    cleanup_audio()
    response = client.audio.speech.create(
        model="tts-1", voice="onyx", input=text
    )
    output_file = "output_voice.mp3"
    response.stream_to_file(output_file)
    return output_file

def init_exam():
    cleanup_audio()
    st.session_state.recorder_key += 1
    st.session_state.turn_count = 0 
    st.session_state.exam_finished = False
    st.session_state.exam_started = False
    
    topics = ["family", "work", "supermarket", "street", "park"]
    seed = random.randint(1,99999)
    new_image_url = f"https://picsum.photos/seed/{seed}/600/400" 
    st.session_state.current_image = new_image_url

    start_phrase = "Guten Tag. Hier ist Ihr Bild. Was sehen Sie?"
    
    st.session_state.messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user", 
            "content": [
                {"type": "text", "text": f"Das ist das Bild. Sei ein einfacher Prüfer (A2/B1)."},
                {"type": "image_url", "image_url": {"url": new_image_url}}
            ]
        },
        {"role": "assistant", "content": start_phrase}
    ]

# ==========================================
# 3. INTERFACE (FRONTEND)
# ==========================================

if "recorder_key" not in st.session_state:
    st.session_state.recorder_key = 0
    st.session_state.messages = []
    init_exam()

# --- HEADER ---
st.markdown("<h1 style='text-align: center; font-weight: 300;'>🇩🇪 DTZ <b style='color:#4A90E2'>Trainer</b></h1>", unsafe_allow_html=True)

# --- INFO BAR ---
if st.session_state.exam_started and not st.session_state.exam_finished:
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.metric("Frage", f"{st.session_state.turn_count + 1} / {MAX_TURNS}")
    if c3.button("🔄 Bild wechseln"):
        init_exam()
        st.rerun()

st.write("---") 

# --- IMAGE ---
if st.session_state.current_image:
    st.image(st.session_state.current_image, use_container_width=True)

# --- SCENARIO 1: START BUTTON ---
if not st.session_state.exam_started:
    st.write("")
    st.write("")
    # Центрируем кнопку старта
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("STARTEN ▶️", use_container_width=True):
            st.session_state.exam_started = True
            first_msg = st.session_state.messages[-1]["content"]
            text_to_speech(first_msg)
            st.rerun()

# --- SCENARIO 2: EXAM IN PROGRESS ---
else:
    # 1. CHAT
    st.write("")
    for msg in st.session_state.messages:
        if msg["role"] == "assistant" or (msg["role"] == "user" and isinstance(msg["content"], str)):
            avatar = "👨‍🏫" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.write(msg["content"])

    # 2. FINISH
    if st.session_state.exam_finished:
        st.success("🏁 Prüfung beendet! (Экзамен завершен)")
        if st.button("Nächstes Bild üben 🔄", type="primary", use_container_width=True):
            init_exam()
            st.rerun()

    # 3. MICROPHONE (BIG & CENTERED)
    else:
        st.write("---")
        
        # Центрирование с помощью колонок
        left, center, right = st.columns([1, 1, 1])
        
        with center:
            # Инструкция с эмодзи
            st.markdown(
                """
                <div style="text-align: center; color: #888; margin-bottom: 10px; font-size: 14px;">
                👆 <b>Нажать</b> (запись) <br> 
                🗣️ <b>Говорить</b> <br> 
                👇 <b>Нажать</b> (стоп)
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            # КНОПКА ЗАПИСИ
            # neutral_color="#FFFFFF" -> Белая кнопка (Стильно на черном)
            # recording_color="#FF4B4B" -> Красная при записи
            # icon_size="6x" -> ОГРОМНАЯ
            audio_bytes = audio_recorder(
                text="",
                recording_color="#FF4B4B", 
                neutral_color="#FFFFFF",
                icon_size="6x",
                key=str(st.session_state.recorder_key),
                pause_threshold=5.0,
                sample_rate=44100
            )

        # Обработка
        if audio_bytes:
            if len(audio_bytes) < 3000:
                st.toast("Zu kurz / Коротко!", icon="⚠️")
                st.session_state.recorder_key += 1
                st.rerun()
            else:
                with st.spinner("Prüfer hört zu..."):
                    user_text = speech_to_text(audio_bytes)
                    blacklist = ["Video hat euch gefallen", "Abo da", "Untertitel", "Bits von White"]
                    is_hallucination = any(p.lower() in user_text.lower() for p in blacklist)
                    
                    if is_hallucination:
                        st.toast("Шум...", icon="🔇")
                    elif len(user_text) < 2:
                        st.toast("?", icon="👂")
                    else:
                        st.session_state.messages.append({"role": "user", "content": user_text})
                        st.session_state.turn_count += 1
                        
                        if st.session_state.turn_count >= MAX_TURNS:
                            st.session_state.messages.append({
                                "role": "system", 
                                "content": "[STOP_EXAM] Gib jetzt die Bewertung (B1/A2)."
                            })
                            st.session_state.exam_finished = True
                        
                        ai_response = get_ai_response(st.session_state.messages)
                        st.session_state.messages.append({"role": "assistant", "content": ai_response})
                        text_to_speech(ai_response)

                    st.session_state.recorder_key += 1
                    st.rerun()

    # AUTOPLAY
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        if os.path.exists("output_voice.mp3"):
            st.audio("output_voice.mp3", format="audio/mp3", autoplay=True)