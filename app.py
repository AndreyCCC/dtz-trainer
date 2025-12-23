import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
import streamlit.components.v1 as components
import base64
import os
import random
import time

# ==========================================
# 1. КОНФИГУРАЦИЯ И СТИЛИ (THEME)
# ==========================================
st.set_page_config(page_title="DTZ Lingo", page_icon="🦉", layout="centered")

# --- ВСТАВЬ КЛЮЧ СЮДА ---
LOCAL_API_KEY = "sk-..." 

# --- CSS МАГИЯ (Duolingo Style) ---
st.markdown("""
<style>
    /* 1. Глобальный фон и шрифт */
    .stApp {
        background-color: #131F24; /* Глубокий темный */
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* 2. Кнопки как в Duolingo (3D эффект) */
    div.stButton > button {
        width: 100%;
        background-color: #58CC02; /* Ярко-зеленый */
        color: white;
        border: none;
        border-bottom: 5px solid #46A302; /* Тень кнопки */
        border-radius: 15px;
        padding: 15px 20px;
        font-size: 18px;
        font-weight: 700;
        transition: all 0.1s;
    }
    div.stButton > button:hover {
        background-color: #61E002;
        border-bottom: 5px solid #46A302;
        color: white;
    }
    div.stButton > button:active {
        border-bottom: 0px solid #46A302;
        transform: translateY(5px); /* Эффект нажатия */
    }

    /* 3. Вторичные кнопки (Серые) */
    .secondary-button > button {
        background-color: #37464F !important;
        border-bottom: 5px solid #283339 !important;
    }

    /* 4. Карточки заданий */
    .exam-card {
        background-color: #202F36;
        border: 2px solid #37464F;
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        margin-bottom: 15px;
        color: white;
    }
    .exam-icon { font-size: 40px; margin-bottom: 10px; }
    .exam-title { font-size: 20px; font-weight: bold; margin-bottom: 5px; }
    .exam-desc { font-size: 14px; color: #AFBCC4; }

    /* 5. Чат пузыри */
    .chat-container { display: flex; flex-direction: column; gap: 15px; margin-bottom: 20px; }
    
    .bubble-ai {
        align-self: flex-start;
        background-color: #37464F;
        color: white;
        padding: 15px;
        border-radius: 20px 20px 20px 0;
        border: 2px solid #4B5C66;
        max-width: 80%;
        font-size: 16px;
        line-height: 1.5;
    }
    
    .bubble-user {
        align-self: flex-end;
        background-color: #1CB0F6; /* Голубой */
        color: white;
        padding: 15px;
        border-radius: 20px 20px 0 20px;
        border-bottom: 4px solid #1899D6;
        max-width: 80%;
        font-size: 16px;
        text-align: right;
    }

    /* Скрываем лишнее */
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    
    /* Прогресс бар */
    .stProgress > div > div > div > div {
        background-color: #FFC800; /* Золотой */
    }
</style>
""", unsafe_allow_html=True)

# --- АВТОРИЗАЦИЯ ---
try:
    if "OPENAI_API_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    else:
        client = OpenAI(api_key=LOCAL_API_KEY)
except:
    client = OpenAI(api_key=LOCAL_API_KEY)

# --- ЛОГИКА И ПРОМПТЫ ---
# Аватар экзаменатора (ссылка на 3D голову)
AVATAR_URL = "https://cdn3d.iconscout.com/3d/premium/thumb/teacher-5692639-4743450.png"

PROMPTS = {
    "vorstellung": "Du bist ein freundlicher DTZ Prüfer (B1). Teil 1. Frage nach: Name, Herkunft, Beruf, Familie. Nur EINE Frage.",
    "bild": "Du bist ein DTZ Prüfer (B1). Teil 2: Bildbeschreibung. Höre zu. Frage nach Details. Nur EINE Frage.",
    "planung": "Du bist ein DTZ Prüfer (B1). Teil 3: Planung. Wir planen eine Party. Mache Vorschläge."
}
GRADING_PROMPT = "Bewertung (B1). Format: Markdown. Kurz und knackig. Ergebnis: Bestanden/Nicht."

# --- ФУНКЦИИ ---
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
    st.session_state.current_image = f"https://picsum.photos/seed/{random.randint(1,999)}/400/300"
    if "last_audio" in st.session_state: del st.session_state.last_audio

def go_to(page):
    st.session_state.page = page
    st.rerun()

def autoplay_hack(audio_bytes):
    """Невидимый, но надежный плеер"""
    if not audio_bytes: return
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
        <audio id="player" autoplay controls style="width: 100%; border-radius: 10px; margin-top: 10px;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <script>
            var audio = document.getElementById("player");
            audio.play().catch(e => console.log("Autoplay blocked"));
        </script>
    """
    components.html(html, height=60)

# --- STATE ---
if "page" not in st.session_state: st.session_state.page = "menu"
if "exam_type" not in st.session_state: st.session_state.exam_type = "bild"
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "turn_count" not in st.session_state: st.session_state.turn_count = 0
if "recorder_key" not in st.session_state: st.session_state.recorder_key = "1"

# ==========================================
# ЭКРАН 1: ГЛАВНОЕ МЕНЮ (КАРТОЧКИ)
# ==========================================
if st.session_state.page == "menu":
    
    # Хедер
    c1, c2 = st.columns([1, 4])
    with c1: st.image(AVATAR_URL, width=60)
    with c2: 
        st.markdown("<h2 style='margin:0; color:white;'>Lern Deutsch!</h2>", unsafe_allow_html=True)
        st.caption("Wähle deine Lektion")

    st.write("") # Отступ

    # Карточка 1: О себе
    st.markdown("""
    <div class="exam-card">
        <div class="exam-icon">👤</div>
        <div class="exam-title">Vorstellung</div>
        <div class="exam-desc">Erzähl über dich: Name, Hobbys, Arbeit.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("STARTEN (Teil 1)", key="btn1"):
        st.session_state.exam_type = "vorstellung"
        reset_session()
        go_to("exam")

    st.write("") 

    # Карточка 2: Картинка
    st.markdown("""
    <div class="exam-card">
        <div class="exam-icon">🖼️</div>
        <div class="exam-title">Bildbeschreibung</div>
        <div class="exam-desc">Beschreibe, was du auf dem Foto siehst.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("STARTEN (Teil 2)", key="btn2"):
        st.session_state.exam_type = "bild"
        reset_session()
        go_to("exam")

    st.write("") 

    # Карточка 3: Планирование
    st.markdown("""
    <div class="exam-card">
        <div class="exam-icon">🎉</div>
        <div class="exam-title">Planung</div>
        <div class="exam-desc">Organisiere eine Party oder ein Picknick.</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("STARTEN (Teil 3)", key="btn3"):
        st.session_state.exam_type = "planung"
        reset_session()
        go_to("exam")

# ==========================================
# ЭКРАН 2: ЭКЗАМЕН (ЧАТ)
# ==========================================
elif st.session_state.page == "exam":
    
    # 1. Верхний бар (Прогресс и Выход)
    c1, c2, c3 = st.columns([1, 6, 1])
    with c1:
        # Используем пустой контейнер с классом secondary для стилизации кнопки назад (через CSS хак сложнее, оставим стандарт)
        if st.button("❌", key="back"): go_to("menu")
    with c2:
        # Прогресс бар
        st.progress(min(st.session_state.turn_count / 4, 1.0))
    with c3:
        st.write("❤️ 5") # Геймификация (жизни)

    # 2. Визуал задания
    if st.session_state.exam_type == "bild":
        st.image(st.session_state.current_image, use_container_width=True)
        st.caption("Was sehen Sie auf dem Bild?")
    elif st.session_state.exam_type == "planung":
        st.info("📅 Aufgabe: Planen Sie eine Party.")
    else:
        # Аватар экзаменатора для разговора
        c1, c2 = st.columns([1, 2])
        with c1: st.image(AVATAR_URL, width=100)
        with c2: st.success("Hallo! Ich bin Herr Müller.")

    st.write("---")

    # 3. Приветствие (старт)
    if not st.session_state.chat_history:
        start_texts = {
            "vorstellung": "Hallo! Wie heißen Sie und woher kommen Sie?",
            "bild": "Bitte beschreiben Sie dieses Bild.",
            "planung": "Hallo! Wollen wir eine Party organisieren?"
        }
        greeting = start_texts[st.session_state.exam_type]
        st.session_state.chat_history.append(("assistant", greeting))
        st.session_state.last_audio = text_to_speech(greeting)
        st.rerun()

    # 4. Чат (Красивые пузыри)
    # Используем HTML для полного контроля над видом
    chat_html = "<div class='chat-container'>"
    for role, text in st.session_state.chat_history:
        if role == "user":
            chat_html += f"<div class='bubble-user'>{text}</div>"
        else:
            chat_html += f"<div class='bubble-ai'>{text}</div>"
    chat_html += "</div>"
    st.markdown(chat_html, unsafe_allow_html=True)

    # 5. Аудио (Ответ экзаменатора)
    if "last_audio" in st.session_state and st.session_state.last_audio:
        autoplay_hack(st.session_state.last_audio)

    # 6. Ввод (Микрофон)
    st.write("") # Отступ
    
    if st.session_state.exam_finished:
        st.balloons()
        if st.button("WEITER (Результат)", type="primary"):
            go_to("result")
    else:
        # Центрируем микрофон
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            audio_bytes = audio_recorder(
                text="",
                recording_color="#ff4b4b",
                neutral_color="#58CC02", # Зеленый как в кнопках
                icon_size="4x",
                key=st.session_state.recorder_key,
                pause_threshold=60.0,
                sample_rate=44100
            )
            st.caption("Нажми, чтобы говорить")

        # Обработка
        if audio_bytes:
            with st.spinner("..."):
                try:
                    transcript = client.audio.transcriptions.create(model="whisper-1", file=("temp.wav", audio_bytes), language="de")
                    user_text = transcript.text
                except: user_text = ""

                # Фильтр
                blacklist = ["video hat euch gefallen", "abo da", "untertitel"]
                if any(b in user_text.lower() for b in blacklist) or len(user_text) < 2:
                    st.toast("Не слышно. Попробуй еще раз!", icon="⚠️")
                    st.session_state.recorder_key = str(random.randint(1,999))
                    time.sleep(1)
                    st.rerun()

                st.session_state.chat_history.append(("user", user_text))
                st.session_state.turn_count += 1
                
                # Логика финала
                sys_prompt = PROMPTS[st.session_state.exam_type]
                if st.session_state.turn_count >= 3:
                    sys_prompt = GRADING_PROMPT
                    st.session_state.exam_finished = True

                # GPT запрос
                messages = [{"role": "system", "content": sys_prompt}]
                # Vision для картинки
                if st.session_state.exam_type == "bild":
                     user_msg_content = [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": st.session_state.current_image}}
                    ]
                     # Добавляем историю упрощенно, а текущий с картинкой
                     for r, t in st.session_state.chat_history[:-1]: messages.append({"role": r, "content": t})
                     messages.append({"role": "user", "content": user_msg_content})
                else:
                    for r, t in st.session_state.chat_history: messages.append({"role": r, "content": t})
                
                ai_text = get_ai_response(messages)
                st.session_state.chat_history.append(("assistant", ai_text))
                st.session_state.last_audio = text_to_speech(ai_text)
                
                st.session_state.recorder_key = str(random.randint(1,999))
                st.rerun()

# ==========================================
# ЭКРАН 3: РЕЗУЛЬТАТ
# ==========================================
elif st.session_state.page == "result":
    st.markdown("<h1 style='text-align: center; color: #58CC02;'>Gut gemacht!</h1>", unsafe_allow_html=True)
    st.image(AVATAR_URL, width=150) # Аватар доволен
    
    # Карточка с результатом
    feedback = st.session_state.chat_history[-1][1]
    st.markdown(f"""
    <div class="exam-card" style="text-align: left;">
        {feedback}
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if st.button("WEITER (В меню)"):
        go_to("menu")
