import streamlit as st
import tempfile
import os
import asyncio
import edge_tts
import numpy as np
from PIL import Image, ImageDraw
import base64
import uuid
import time
import requests
from io import BytesIO
import subprocess
import sys

# ---- Forcer l'utilisation du binaire FFmpeg fourni par imageio-ffmpeg ----
try:
    import imageio_ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    from moviepy.config import change_settings
    change_settings({"FFMPEG_BINARY": ffmpeg_path})
except ImportError:
    st.error("❌ imageio-ffmpeg n'est pas installé. Ajoutez-le dans requirements.txt.")
    st.stop()

# ---- Importer moviepy ----
try:
    import moviepy.editor as mp
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips
except ImportError as e:
    st.error(f"❌ moviepy n'est pas installé : {e}")
    st.stop()

# ---- Configuration de la page ----
st.set_page_config(
    page_title="Générateur de Pub IA",
    page_icon="📹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- CSS ----
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

st.markdown('<div class="title">🎬 Générateur de Vidéo Publicitaire</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Créez des vidéos professionnelles avec voix IA, couleurs personnalisées et musique</div>', unsafe_allow_html=True)

# ---- Sidebar ----
with st.sidebar:
    st.header("⚙️ Paramètres")
    voice_lang = st.selectbox(
        "Langue de la voix",
        ["en-US", "en-GB", "fr-FR", "es-ES", "de-DE", "it-IT", "pt-BR"]
    )
    voice_gender = st.radio("Genre de la voix", ["Féminin", "Masculin"], index=0)
    
    voice_map = {
        ("en-US", "Féminin"): "en-US-JennyNeural",
        ("en-US", "Masculin"): "en-US-GuyNeural",
        ("en-GB", "Féminin"): "en-GB-SoniaNeural",
        ("en-GB", "Masculin"): "en-GB-RyanNeural",
        ("fr-FR", "Féminin"): "fr-FR-DeniseNeural",
        ("fr-FR", "Masculin"): "fr-FR-HenriNeural",
        ("es-ES", "Féminin"): "es-ES-ElviraNeural",
        ("es-ES", "Masculin"): "es-ES-AlvaroNeural",
        ("de-DE", "Féminin"): "de-DE-KatjaNeural",
        ("de-DE", "Masculin"): "de-DE-ConradNeural",
        ("it-IT", "Féminin"): "it-IT-ElsaNeural",
        ("it-IT", "Masculin"): "it-IT-DiegoNeural",
        ("pt-BR", "Féminin"): "pt-BR-FranciscaNeural",
        ("pt-BR", "Masculin"): "pt-BR-AntonioNeural",
    }
    selected_voice = voice_map.get((voice_lang, voice_gender), "en-US-JennyNeural")
    st.info(f"Voix : {selected_voice}")

    st.markdown("---")
    st.subheader("🎨 Couleurs")
    bg_color = st.color_picker("Couleur de fond", "#1a2a4a")
    accent_color = st.color_picker("Couleur d'accent", "#174478")  # (non utilisé ici, mais gardé pour l'extension)

    st.markdown("---")
    st.subheader("🖼️ Logo")
    logo_file = st.file_uploader("Téléchargez votre logo (PNG, JPG)", type=["png", "jpg", "jpeg"])
    
    st.markdown("---")
    st.subheader("🎵 Musique de fond")
    bg_music_file = st.file_uploader("Téléchargez un MP3/WAV (optionnel)", type=["mp3", "wav"])

    st.markdown("---")
    st.subheader("📷 Images du produit")
    product_images = st.file_uploader("Téléchargez jusqu'à 10 images", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if len(product_images) > 10:
        st.warning("Maximum 10 images. Seules les 10 premières seront utilisées.")
        product_images = product_images[:10]

    st.markdown("---")
    st.markdown("""
    <div class="contact-info">
        📞 (509) 4738-5663<br>
        📧 deslandes78@gmail.com
    </div>
    """, unsafe_allow_html=True)

# ---- Entrées principales ----
col1, col2 = st.columns([2, 1])
with col1:
    product_name = st.text_input("Nom du produit / service", placeholder="ex. Prisme Transfer Haïti")
    product_description = st.text_area("Description / caractéristiques", placeholder="Décrivez votre produit, ses avantages...", height=150)
    call_to_action = st.text_input("Appel à l'action", placeholder="Inscrivez-vous, Achetez maintenant, En savoir plus...")

generate_btn = st.button("🎥 Générer la vidéo", use_container_width=True)
video_placeholder = st.empty()

# ---- Helper : dégradé de fond (résolution réduite) ----
def create_gradient_bg(width=854, height=480, color1=(20,40,80), color2=(10,20,50)):
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    for y in range(height):
        ratio = y / height
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img

# ---- Création d'une diapositive (fond + logo éventuel) ----
def create_slide(bg_color, image=None, duration=3, logo_img=None):
    if image is not None:
        bg_img = Image.fromarray(image)
    else:
        def hex_to_rgb(hex_color):
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        base_rgb = hex_to_rgb(bg_color)
        dark_rgb = (max(base_rgb[0]-30, 0), max(base_rgb[1]-30, 0), max(base_rgb[2]-30, 0))
        bg_img = create_gradient_bg(854, 480, base_rgb, dark_rgb)
    
    if logo_img is not None:
        logo = Image.open(BytesIO(logo_img)).convert('RGBA')
        logo.thumbnail((120, 80), Image.Resampling.LANCZOS)
        bg_img.paste(logo, (bg_img.width - logo.width - 15, 15), logo)
    
    img_np = np.array(bg_img)
    clip = mp.ImageClip(img_np).set_duration(duration)
    return clip

# ---- Génération de la vidéo ----
def generate_video(product_name, description, cta, bg_color, images, voice, music_file, logo_data):
    temp_dir = tempfile.mkdtemp()
    
    # Message de clôture en français
    closing_message = (
        "Pour plus d'informations, contactez-nous au (509) 4738-5663 ou par courriel à deslandes78@gmail.com. "
        "Si vous souhaitez une publicité pour votre entreprise, contactez Gesner Deslandes chez GlobalInternet.py."
    )
    
    script = f"{product_name}. {description} {cta}. {closing_message}"
    
    # Génération audio avec edge-tts
    async def tts():
        communicate = edge_tts.Communicate(script, voice)
        audio_path = os.path.join(temp_dir, "voiceover.mp3")
        await communicate.save(audio_path)
        return audio_path
    
    audio_path = asyncio.run(tts())
    voice_audio = mp.AudioFileClip(audio_path)
    duration = voice_audio.duration
    st.info(f"Durée de la voix : {duration:.1f} secondes")
    
    slides = []
    if images and len(images) > 0:
        slide_count = len(images)
        max_slides = int(duration / 1.5)
        if slide_count > max_slides:
            slide_count = max_slides
        if slide_count == 0:
            slide_count = 1
        images_to_use = images[:slide_count]
        slide_duration = duration / slide_count
        st.info(f"Création de {slide_count} diapositives de {slide_duration:.1f}s chacune")
        for i, img in enumerate(images_to_use):
            slide = create_slide(bg_color, image=img, duration=slide_duration, logo_img=logo_data)
            if i > 0:
                slide = slide.crossfadein(0.5)
            slides.append(slide)
    else:
        st.warning("Aucune image fournie – utilisation d'un fond uni.")
        slide = create_slide(bg_color, image=None, duration=duration, logo_img=logo_data)
        slides.append(slide)
    
    video = mp.concatenate_videoclips(slides, method="compose")
    video = video.set_audio(voice_audio)
    
    # Musique de fond
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
    st.info("Écriture de la vidéo (cela peut prendre jusqu'à 30 secondes)...")
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
    
    # Nettoyage
    for f in os.listdir(temp_dir):
        if f != os.path.basename(output_path):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
    return output_path

# ---- Bouton Générer ----
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
                        pil_img = pil_img.resize((854, 480), Image.Resampling.LANCZOS)
                        img_np = np.array(pil_img)
                        image_list.append(img_np)
                    st.success(f"{len(image_list)} images chargées")
                else:
                    st.info("Aucune image téléchargée. La vidéo utilisera un fond uni.")
                
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
                
                if os.path.exists(video_path) and os.path.getsize(video_path) > 0:
                    with video_placeholder.container():
                        st.success("✅ Vidéo publicitaire générée avec succès !")
                        with open(video_path, "rb") as f:
                            video_bytes = f.read()
                        st.info(f"Taille de la vidéo : {len(video_bytes)//1024} Ko")
                        
                        # Affichage via HTML5 video
                        b64 = base64.b64encode(video_bytes).decode()
                        video_html = f"""
                        <video width="100%" controls autoplay>
                            <source src="data:video/mp4;base64,{b64}" type="video/mp4">
                            Votre navigateur ne supporte pas la lecture vidéo.
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
                else:
                    st.error("❌ La vidéo n'a pas pu être générée (fichier vide ou inexistant).")
            except Exception as e:
                st.error(f"❌ Une erreur s'est produite : {e}")
                st.exception(e)
