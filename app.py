import streamlit as st
import tempfile
import os
import asyncio
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import base64
import uuid
import time
import requests
from io import BytesIO

# Try to import moviepy with fallback
try:
    import moviepy.editor as mp
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, concatenate_videoclips, ColorClip
except ImportError:
    st.error("❌ moviepy is not installed. Please check your requirements.txt.")
    st.stop()

# Page config
st.set_page_config(
    page_title="AI Ad Generator",
    page_icon="📹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main { background: #f8f9fa; }
    .stButton>button {
        background: #ff4b4b;
        color: white;
        border-radius: 30px;
        padding: 0.5rem 2rem;
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background: #e60000;
        transform: scale(1.02);
    }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e2a3a;
        text-align: center;
        margin-bottom: 1rem;
    }
    .subtitle {
        text-align: center;
        color: #555;
        margin-bottom: 2rem;
    }
    .contact-info {
        background: #1e2a3a;
        padding: 1rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">🎬 AI Advertisement Video Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Create professional ad videos with AI voiceovers, custom colors & music</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    voice_lang = st.selectbox(
        "Voice Language",
        ["en-US", "en-GB", "fr-FR", "es-ES", "de-DE", "it-IT", "pt-BR"]
    )
    voice_gender = st.radio("Voice Gender", ["Female", "Male"], index=0)
    
    voice_map = {
        ("en-US", "Female"): "en-US-JennyNeural",
        ("en-US", "Male"): "en-US-GuyNeural",
        ("en-GB", "Female"): "en-GB-SoniaNeural",
        ("en-GB", "Male"): "en-GB-RyanNeural",
        ("fr-FR", "Female"): "fr-FR-DeniseNeural",
        ("fr-FR", "Male"): "fr-FR-HenriNeural",
        ("es-ES", "Female"): "es-ES-ElviraNeural",
        ("es-ES", "Male"): "es-ES-AlvaroNeural",
        ("de-DE", "Female"): "de-DE-KatjaNeural",
        ("de-DE", "Male"): "de-DE-ConradNeural",
        ("it-IT", "Female"): "it-IT-ElsaNeural",
        ("it-IT", "Male"): "it-IT-DiegoNeural",
        ("pt-BR", "Female"): "pt-BR-FranciscaNeural",
        ("pt-BR", "Male"): "pt-BR-AntonioNeural",
    }
    selected_voice = voice_map.get((voice_lang, voice_gender), "en-US-JennyNeural")
    st.info(f"Voice: {selected_voice}")

    st.markdown("---")
    st.subheader("🎨 Brand Colors")
    bg_color = st.color_picker("Background Color (for slides)", "#1a2a4a")
    accent_color = st.color_picker("Accent Color", "#174478")

    st.markdown("---")
    st.subheader("🖼️ Logo Upload")
    logo_file = st.file_uploader("Upload your logo (PNG, JPG)", type=["png", "jpg", "jpeg"])
    
    st.markdown("---")
    st.subheader("🎵 Background Music")
    bg_music_file = st.file_uploader("Upload MP3/WAV (optional)", type=["mp3", "wav"])

    st.markdown("---")
    st.subheader("📷 Product Images")
    product_images = st.file_uploader("Upload up to 10 images to show in the video", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if len(product_images) > 10:
        st.warning("Maximum 10 images. Only first 10 will be used.")
        product_images = product_images[:10]

    st.markdown("---")
    st.markdown("""
    <div class="contact-info">
        📞 (509) 4738-5663<br>
        📧 deslandes78@gmail.com
    </div>
    """, unsafe_allow_html=True)

# Main inputs
col1, col2 = st.columns([2, 1])
with col1:
    product_name = st.text_input("Product / Service Name", placeholder="e.g. Prisme Transfer Haiti")
    product_description = st.text_area("Description / Features", placeholder="Describe your product, its benefits, and key features...", height=150)
    call_to_action = st.text_input("Call to Action", placeholder="Sign up now, Buy today, Learn more...")

generate_btn = st.button("🎥 Generate Ad Video", use_container_width=True)
video_placeholder = st.empty()

# ---- Helper: create a gradient background ----
def create_gradient_bg(width=1920, height=1080, color1=(20,40,80), color2=(10,20,50)):
    """Create a vertical gradient image."""
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img

# ---- Slide creation without text (background + optional logo) ----
def create_slide(bg_color, image=None, duration=3, logo_img=None):
    if image is not None:
        bg_img = Image.fromarray(image).resize((1920, 1080), Image.Resampling.LANCZOS)
    else:
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        base_rgb = hex_to_rgb(bg_color)
        dark_rgb = (max(base_rgb[0]-30, 0), max(base_rgb[1]-30, 0), max(base_rgb[2]-30, 0))
        bg_img = create_gradient_bg(1920, 1080, base_rgb, dark_rgb)
    
    if logo_img is not None:
        logo = Image.open(BytesIO(logo_img)).convert('RGBA')
        logo.thumbnail((200, 120), Image.Resampling.LANCZOS)
        bg_img.paste(logo, (bg_img.width - logo.width - 30, 30), logo)
    
    img_np = np.array(bg_img)
    clip = mp.ImageClip(img_np).set_duration(duration)
    return clip

# ---- Video generation ----
def generate_video(product_name, description, cta, bg_color, images, voice, music_file, logo_data):
    temp_dir = tempfile.mkdtemp()
    
    # ------------------------------------------------------------------
    # Message de clôture en français (modifié pour éviter l'anglais)
    # ------------------------------------------------------------------
    closing_message = (
        "Pour plus d'informations, contactez-nous au (509) 4738-5663 ou par courriel à deslandes78@gmail.com. "
        "Si vous souhaitez une publicité pour votre entreprise, contactez Gesner Deslandes chez GlobalInternet.py."
    )
    
    # Construire le script complet – **sans** "Introducing" en anglais
    # On utilise directement le nom du produit, la description et l'appel à l'action.
    script = f"{product_name}. {description} {cta}. {closing_message}"
    
    # Générer l'audio avec edge-tts
    async def tts():
        communicate = edge_tts.Communicate(script, voice)
        audio_path = os.path.join(temp_dir, "voiceover.mp3")
        await communicate.save(audio_path)
        return audio_path
    
    audio_path = asyncio.run(tts())
    voice_audio = mp.AudioFileClip(audio_path)
    duration = voice_audio.duration
    
    slides = []
    
    # Construire les diapositives à partir des images téléchargées
    if images and len(images) > 0:
        slide_count = len(images)
        # S'assurer que chaque diapositive dure au moins 1.5 secondes
        max_slides = int(duration / 1.5)
        if slide_count > max_slides:
            slide_count = max_slides
        if slide_count == 0:
            slide_count = 1
        images_to_use = images[:slide_count]
        slide_duration = duration / slide_count
        for i in range(slide_count):
            img = images_to_use[i]
            slide = create_slide(bg_color, image=img, duration=slide_duration, logo_img=logo_data)
            if i > 0:
                slide = slide.crossfadein(0.5)
            slides.append(slide)
    else:
        # Aucune image – utiliser une seule diapositive dégradée pour toute la durée
        slide = create_slide(bg_color, image=None, duration=duration, logo_img=logo_data)
        slides.append(slide)
    
    # Aucune diapositive de contact à la fin – la vidéo se termine sur la dernière image ou le dégradé
    
    # Concaténer toutes les diapositives
    video = mp.concatenate_videoclips(slides, method="compose")
    video = video.set_audio(voice_audio)
    
    # Ajouter la musique de fond si fournie
    if music_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(music_file.read())
            music_path = tmp.name
        bg_music = mp.AudioFileClip(music_path)
        if bg_music.duration < video.duration:
            bg_music = bg_music.loop(duration=video.duration)
        else:
            bg_music = bg_music.subclip(0, video.duration)
        bg_music = bg_music.volumex(0.3)
        final_audio = mp.CompositeAudioClip([voice_audio, bg_music])
        video = video.set_audio(final_audio)
    
    output_path = os.path.join(temp_dir, f"ad_{uuid.uuid4().hex[:8]}.mp4")
    video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile=os.path.join(temp_dir, 'temp_audio.m4a'),
        remove_temp=True,
        verbose=False,
        logger=None
    )
    
    # Nettoyer les fichiers temporaires
    for f in os.listdir(temp_dir):
        if f != os.path.basename(output_path):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
    return output_path

# ---- Génération au clic sur le bouton ----
if generate_btn:
    if not product_name:
        st.error("Veuillez entrer un nom de produit.")
    elif not product_description:
        st.error("Veuillez entrer une description.")
    elif not call_to_action:
        st.error("Veuillez entrer un appel à l'action.")
    else:
        with st.spinner("🎬 Génération de votre vidéo... Cela peut prendre une minute."):
            try:
                image_list = []
                if product_images:
                    for img_file in product_images[:10]:
                        pil_img = Image.open(img_file).convert('RGB')
                        pil_img = pil_img.resize((1920, 1080), Image.Resampling.LANCZOS)
                        img_np = np.array(pil_img)
                        image_list.append(img_np)
                
                logo_data = None
                if logo_file:
                    logo_data = logo_file.read()
                
                video_path = generate_video(
                    product_name,
                    product_description,
                    call_to_action,
                    bg_color,
                    image_list,
                    selected_voice,
                    bg_music_file,
                    logo_data
                )
                
                with video_placeholder.container():
                    st.success("✅ Vidéo publicitaire générée avec succès !")
                    with open(video_path, "rb") as f:
                        video_bytes = f.read()
                    b64 = base64.b64encode(video_bytes).decode()
                    video_html = f"""
                    <video width="100%" controls autoplay>
                        <source src="data:video/mp4;base64,{b64}" type="video/mp4">
                    </video>
                    """
                    st.markdown(video_html, unsafe_allow_html=True)
                    
                    st.download_button(
                        label="⬇️ Télécharger la vidéo (MP4)",
                        data=video_bytes,
                        file_name=f"{product_name.replace(' ', '_')}_ad.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Une erreur s'est produite : {e}")
                st.exception(e)
