import streamlit as st
import tempfile
import os
import asyncio
import edge_tts
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, ImageClip, concatenate_videoclips
import base64
import io
import time
import uuid

# Page config
st.set_page_config(
    page_title="AI Ad Generator",
    page_icon="📹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for a professional look
st.markdown("""
<style>
    .main {
        background: #f8f9fa;
    }
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
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
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

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    voice_lang = st.selectbox(
        "Voice Language",
        ["en-US", "en-GB", "fr-FR", "es-ES", "de-DE", "it-IT", "pt-BR"]
    )
    voice_gender = st.radio("Voice Gender", ["Female", "Male"], index=0)
    
    # Map to edge-tts voice names (popular ones)
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
    primary_color = st.color_picker("Primary Color", "#ff4b4b")
    secondary_color = st.color_picker("Secondary Color", "#1e2a3a")
    bg_color = st.color_picker("Background Color", "#ffffff")
    
    st.markdown("---")
    st.subheader("🎵 Background Music")
    bg_music_file = st.file_uploader("Upload MP3/WAV (optional)", type=["mp3", "wav"])

    st.markdown("---")
    st.subheader("📷 Product Images")
    product_images = st.file_uploader("Upload up to 5 images", type=["png", "jpg", "jpeg"], accept_multiple_files=True)
    if len(product_images) > 5:
        st.warning("Maximum 5 images. Only first 5 will be used.")
        product_images = product_images[:5]

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
    product_name = st.text_input("Product / Service Name", placeholder="e.g. Lakay se Lakay Platform")
    product_description = st.text_area("Description / Features", placeholder="Describe your product, its benefits, and key features...", height=150)
    call_to_action = st.text_input("Call to Action", placeholder="Sign up now, Buy today, Learn more...")

# Generate button
generate_btn = st.button("🎥 Generate Ad Video", use_container_width=True)

# Placeholder for video output
video_placeholder = st.empty()

# Function to create a slide (image or color background with text overlay)
def create_slide(text, bg_color, text_color, image=None, duration=3):
    if image is not None:
        # Use image as background, resize to 1920x1080
        img_clip = mp.ImageClip(image).resize(height=1080).resize(width=1920)
    else:
        # Create a colored background
        img_clip = mp.ColorClip(size=(1920, 1080), color=bg_color, duration=duration)
    # Text overlay
    txt_clip = TextClip(text, fontsize=70, color=text_color, font='Arial', stroke_color='black', stroke_width=2, method='label')
    txt_clip = txt_clip.set_position(('center', 'center')).set_duration(duration)
    # Composite
    slide = mp.CompositeVideoClip([img_clip, txt_clip])
    return slide

# Generate video
def generate_video(product_name, description, cta, primary, secondary, bg, images, voice, music_file):
    temp_dir = tempfile.mkdtemp()
    # Build script
    script = f"Introducing {product_name}. {description} {cta}. Contact us now at (509) 4738-5663 or email deslandes78@gmail.com."
    
    # Generate audio using edge-tts
    async def tts():
        communicate = edge_tts.Communicate(script, voice)
        audio_path = os.path.join(temp_dir, "voiceover.mp3")
        await communicate.save(audio_path)
        return audio_path
    
    audio_path = asyncio.run(tts())
    voice_audio = mp.AudioFileClip(audio_path)
    duration = voice_audio.duration
    
    # Determine number of slides
    # We'll create slides: 1) title, 2) description, 3) features, 4) CTA+contact
    # If images provided, we can use them for slides; else use color backgrounds
    
    slides = []
    # Slide 1: Product Name
    slide1 = create_slide(f"✨ {product_name}", bg, primary, image=images[0] if images else None, duration=duration/4)
    slides.append(slide1)
    
    # Slide 2: Description (split into parts if long)
    desc_parts = description.split('.')
    desc_text = '\n'.join([part.strip() for part in desc_parts if part.strip()][:3])  # first 3 sentences
    slide2 = create_slide(desc_text, bg, secondary, image=images[1] if len(images) > 1 else None, duration=duration/4)
    slides.append(slide2)
    
    # Slide 3: Features - if we have more images, use them; else color
    # We'll put a bullet list of features from description
    features = description.split('.')
    feature_text = '\n'.join([f'• {f.strip()}' for f in features if f.strip()][:4])
    slide3 = create_slide(feature_text, bg, primary, image=images[2] if len(images) > 2 else None, duration=duration/4)
    slides.append(slide3)
    
    # Slide 4: Call to Action + Contact
    contact_text = f"{cta}\n📞 (509) 4738-5663\n📧 deslandes78@gmail.com"
    slide4 = create_slide(contact_text, bg, secondary, image=images[3] if len(images) > 3 else None, duration=duration/4)
    slides.append(slide4)
    
    # Combine slides with crossfade
    final_clips = []
    for i, slide in enumerate(slides):
        # Set duration evenly
        slide = slide.set_duration(duration/len(slides))
        if i > 0:
            # Crossfade
            slide = slide.crossfadein(0.5)
        final_clips.append(slide)
    
    video = mp.concatenate_videoclips(final_clips, method="compose")
    video = video.set_audio(voice_audio)
    
    # Add background music if provided
    if music_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(music_file.read())
            music_path = tmp.name
        bg_music = mp.AudioFileClip(music_path)
        # Loop or trim to video duration
        if bg_music.duration < video.duration:
            bg_music = bg_music.loop(duration=video.duration)
        else:
            bg_music = bg_music.subclip(0, video.duration)
        # Mix audio: reduce bg volume
        bg_music = bg_music.volumex(0.3)
        final_audio = mp.CompositeAudioClip([voice_audio, bg_music])
        video = video.set_audio(final_audio)
    
    # Output
    output_path = os.path.join(temp_dir, f"ad_{uuid.uuid4().hex[:8]}.mp4")
    video.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac', temp_audiofile=os.path.join(temp_dir, 'temp_audio.m4a'), remove_temp=True, verbose=False, logger=None)
    
    # Cleanup temp files (except output)
    for f in os.listdir(temp_dir):
        if f != os.path.basename(output_path):
            try:
                os.remove(os.path.join(temp_dir, f))
            except:
                pass
    return output_path

if generate_btn:
    if not product_name:
        st.error("Please enter a product name.")
    elif not product_description:
        st.error("Please enter a product description.")
    elif not call_to_action:
        st.error("Please enter a call to action.")
    else:
        with st.spinner("🎬 Generating your ad video... This may take a minute."):
            try:
                # Process images
                image_list = []
                if product_images:
                    for img_file in product_images[:5]:
                        # Convert to PIL and then to numpy array for moviepy
                        pil_img = Image.open(img_file).convert('RGB')
                        # Resize to 1920x1080 (maintain aspect ratio, fill)
                        pil_img = pil_img.resize((1920, 1080), Image.Resampling.LANCZOS)
                        img_np = np.array(pil_img)
                        image_list.append(img_np)
                
                # Generate video
                video_path = generate_video(
                    product_name,
                    product_description,
                    call_to_action,
                    primary_color,
                    secondary_color,
                    bg_color,
                    image_list,
                    selected_voice,
                    bg_music_file
                )
                
                # Display video
                with video_placeholder.container():
                    st.success("✅ Ad video generated successfully!")
                    # Read video file and display
                    with open(video_path, "rb") as f:
                        video_bytes = f.read()
                    # Encode to base64 for HTML5 video
                    b64 = base64.b64encode(video_bytes).decode()
                    video_html = f"""
                    <video width="100%" controls autoplay>
                        <source src="data:video/mp4;base64,{b64}" type="video/mp4">
                    </video>
                    """
                    st.markdown(video_html, unsafe_allow_html=True)
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Download Video (MP4)",
                        data=video_bytes,
                        file_name=f"{product_name.replace(' ', '_')}_ad.mp4",
                        mime="video/mp4",
                        use_container_width=True
                    )
                
                # Cleanup video file after session ends
                # We'll keep it for download, but we can remove after download? Not necessary.
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.exception(e)
