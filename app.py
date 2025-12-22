import streamlit as st
from openai import OpenAI
from audio_recorder_streamlit import audio_recorder
import streamlit.components.v1 as components
import base64
import os
import random
import time

# ==========================================
# 1. КОНФИГУРАЦИЯ
# ==========================================
st.set_page_config(page_title="DTZ Exam AI", page_icon="🇩🇪", layout="centered")

# --- АВТОРИЗАЦИЯ ---
LOCAL_API_KEY = "sk-..."  # <--- ВСТАВЬ КЛЮЧ

try:
    if "OPENAI_API_KEY" in st.secrets:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    else:
        client = OpenAI(api_key=LOCAL_API_KEY)
except:
    client = OpenAI(api_key=LOCAL_API_KEY)

# --- УМНЫЕ ПРОМПТЫ (En для логики, De для речи) ---
PROMPTS = {
    "vorstellung": """
        You are an official examiner for the DTZ (Deutsch-Test für Zuwanderer) exam, level B1.
        Part 1: Introduction (Vorstellung).
        Task: Ask the candidate strictly ONE question at a time about: Name, Origin, Home, Work, Family, or Hobbies.
        Tone: Professional but friendly. Speak simple German (A2/B1).
    """,
    "bild": """
        You are an official DTZ examiner (B1).
        Part 2: Picture Description (Bildbeschreibung).
        Task: The candidate describes a picture. You SEE the same picture.
        Rules:
        1. Listen to the description.
        2. If the candidate stops, ask ONE specific question about details in the image (clothes, weather, background).
        3. Correct major factual errors politely ("Are you sure? I see...").
    """,
    "planung": """
        You are an official DTZ examiner (B1).
        Part 3: Joint Planning (Planung).
        Situation: We are planning a party or a picnic together.
        Task: Discuss details (When? Where? Food? Gift?).
        Rules: Make your own suggestions, sometimes politely disagree with the candidate.
    """
}

GRADING_PROMPT = """
EXAM FINISHED. ACT AS A STRICT GRADER.
Provide feedback in German using Markdown.
Structure:
### 📊 Ergebnis: [B1 / A2 / unter A2]
- **Inhalt:** ...
- **Grammatik:** ...
- **Wortschatz:** ...
- **Tipp:** (One specific advice)
"""

# ==========================================
# 2. ФУНКЦИИ-ПОМОЩНИКИ
# ==========================================

def get_ai_audio(text):
    """Генерация голоса (TTS)"""
    try:
        response = client.audio.speech.create(model="tts-1", voice="onyx", input=text)
        return response.content
    except Exception as e:
        st.error(f"TTS Error: {e}")
        return None

def check_hallucinations(text):
    """Фильтр бреда Whisper (из нашего опыта)"""
    blacklist = [
        "video hat euch gefallen", "abo da", "untertitel", 
        "bits von white", "amara.org", "copyright", 
        "bis zum nächsten mal", "nächste frage", "mbc"
    ]
    if len(text.strip()) < 3: return True
    if any(phrase in text.lower() for phrase in blacklist): return True
    return False

def autoplay_hack(audio_bytes):
    """Пробиваем защиту Safari через iFrame"""
    if not audio_bytes: return
    b64 = base64.b64encode(audio_bytes).decode()
    html = f"""
        <audio id="player" autoplay controls style="width: 100%;">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        <script>
            var audio = document.getElementById("player");
            audio.play().catch(e => console.log("Autoplay blocked, user must click play"));
        </script>
    """
    # height=50 делает плеер видимым, чтобы юзер мог нажать Play, если автоплей не сработает
    components.html(html, height=50)

def reset_session():
    st.session_state.chat_history = []
    st.session_state.turn_count = 0
    st.session_state.exam_finished = False
    st.session_state.recorder_key = str(random.randint(1000, 99999))
    # Новая картинка для Vision
    st.session_state.current_image = f"https://picsum.photos/seed/{random.randint(1,9999)}/400/300"
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

# Стили для красивых пузырей чата
st.markdown("""
<style>
.user-msg {background-color:#e3f2fd; padding:10px; border-radius:15px 15px 0 15px; text-align:right; color:black; margin: 5px 0; border: 1px solid #bbdefb;}
.ai-msg {background-color:#f1f8e9; padding:10px; border-radius:15px 15px 15px 0; text-align:left; color:black; margin: 5px 0; border: 1px solid #c5e1a5;}
.stButton button {width:100%; border-radius:10px; height: 3.5rem; font-weight:bold; font-size: 16px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. ИНТЕРФЕЙС
# ==========================================

# --- ГЛАВНОЕ МЕНЮ ---
if st.session_state.page == "menu":
    st.title("🇩🇪 DTZ Prüfungssimulator")
    st.info("Wählen Sie einen Teil der Prüfung:")
    
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

# --- ЭКРАН ЭКЗАМЕНА ---
elif st.session_state.page == "exam":
    # 1. Навигация
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1: 
        if st.button("🔙"): go_to("menu")
    with c2: 
        # Прогресс бар экзамена
        progress = min(st.session_state.turn_count / 4, 1.0)
        st.progress(progress)
    with c3: 
        if st.button("🔄"): reset_session(); st.rerun()

    # 2. Визуальный контекст (Задание)
    if st.session_state.exam_type == "bild":
        st.image(st.session_state.current_image, use_container_width=True, caption="Ihre Aufgabe: Beschreiben Sie das Bild")
    elif st.session_state.exam_type == "planung":
        st.success("💡 Aufgabe: Planen Sie gemeinsam eine Abschiedsparty.")
    else:
        st.info("💡 Aufgabe: Stellen Sie sich vor (Name, Land, Beruf).")

    st.divider()

    # 3. Чат-история (Рендеринг)
    chat_container = st.container()
    with chat_container:
        for role, text in st.session_state.chat_history:
            css = "user-msg" if role == "user" else "ai-msg"
            icon = "👤" if role == "user" else "🎓"
            st.markdown(f"<div class='{css}'>{icon} {text}</div>", unsafe_allow_html=True)

    # 4. Приветствие (Авто-старт при пустой истории)
    if not st.session_state.chat_history:
        start_texts = {
            "vorstellung": "Guten Tag. Wie heißen Sie und woher kommen Sie?",
            "bild": "Guten Tag. Bitte beschreiben Sie, was Sie auf dem Bild sehen.",
            "planung": "Hallo! Wir wollen eine Party organisieren. Haben Sie eine Idee?"
        }
        greeting = start_texts[st.session_state.exam_type]
        st.session_state.chat_history.append(("assistant", greeting))
        
        # Генерируем голос
        st.session_state.last_audio = get_ai_audio(greeting)
        st.rerun()

    # 5. Плеер (Гибридный хак)
    if "last_audio" in st.session_state:
        st.write("---")
        # Этот компонент попытается воспроизвести звук сам. Если нет - покажет плеер.
        autoplay_hack(st.session_state.last_audio)

    # 6. Управление (Запись или Финиш)
    if st.session_state.exam_finished:
        st.success("Prüfung beendet! (Экзамен завершен)")
        if st.button("🏆 Ergebnis anzeigen", type="primary"):
            go_to("result")
    else:
        st.write("")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            # КНОПКА ЗАПИСИ
            # pause_threshold=60.0 -> Не отключается сама минуту!
            audio_bytes = audio_recorder(
                text="",
                recording_color="#ff4b4b",
                neutral_color="#4CAF50",
                icon_size="4x",
                key=st.session_state.recorder_key,
                pause_threshold=60.0, 
                sample_rate=44100
            )

        if audio_bytes:
            with st.spinner("Verarbeite..."):
                # A. Whisper (Распознавание)
                try:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=("temp.wav", audio_bytes), 
                        language="de"
                    )
                    user_text = transcript.text
                except:
                    st.error("Mikrofon Fehler")
                    st.stop()

                # B. Фильтр Галлюцинаций
                if check_hallucinations(user_text):
                    st.toast("⚠️ Не расслышал. Повторите!", icon="❌")
                    # Мягкий сброс ключа, чтобы юзер мог нажать снова
                    st.session_state.recorder_key = str(random.randint(1,999))
                    time.sleep(1)
                    st.rerun()

                # C. Сохраняем ответ юзера
                st.session_state.chat_history.append(("user", user_text))
                st.session_state.turn_count += 1
                
                # D. Подготовка контекста для GPT
                # Проверяем, пора ли заканчивать
                sys_content = PROMPTS[st.session_state.exam_type]
                if st.session_state.turn_count >= 4: # 4 хода для полноценного разговора
                    sys_content = GRADING_PROMPT
                    st.session_state.exam_finished = True

                gpt_messages = [{"role": "system", "content": sys_content}]
                
                # VISION: Если это Bildbeschreibung, добавляем картинку в контекст
                if st.session_state.exam_type == "bild":
                    # Передаем картинку вместе с последним текстовым сообщением (или как системный контекст)
                    # GPT-4o-mini поддерживает список content
                    user_content = [
                        {"type": "text", "text": f"Ich sehe auf dem Bild: {user_text}"},
                        {"type": "image_url", "image_url": {"url": st.session_state.current_image}}
                    ]
                    # Добавляем историю
                    for r, t in st.session_state.chat_history[:-1]: # Все кроме последнего
                        gpt_messages.append({"role": r, "content": t})
                    # Добавляем последний с картинкой
                    gpt_messages.append({"role": "user", "content": user_content})
                else:
                    # Обычный текстовый режим
                    for r, t in st.session_state.chat_history:
                        gpt_messages.append({"role": r, "content": t})
                
                # E. GPT Запрос
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=gpt_messages)
                ai_text = resp.choices[0].message.content
                
                st.session_state.chat_history.append(("assistant", ai_text))
                
                # F. TTS Генерация
                st.session_state.last_audio = get_ai_audio(ai_text)
                
                # Сброс рекордера для следующего хода
                st.session_state.recorder_key = str(random.randint(1,999))
                st.rerun()

# --- ЭКРАН РЕЗУЛЬТАТА ---
elif st.session_state.page == "result":
    st.title("Ergebnis")
    st.balloons()
    
    # Последнее сообщение - это оценка
    feedback = st.session_state.chat_history[-1][1]
    
    st.markdown(feedback)
    
    st.write("---")
    if st.button("🏠 Zurück zum Menü (В меню)", use_container_width=True):
        go_to("menu")
