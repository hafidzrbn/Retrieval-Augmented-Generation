import os
import streamlit as st
import requests
import uuid
from rag_engine import RAGEngine

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Kawan Beasiswa - Chatbot RAG Informasi Beasiswa",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "preset_query" not in st.session_state:
    st.session_state.preset_query = None
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    
# Initialize RAG Engine and Load Keys from Secrets
gemini_key = st.secrets.get("gemini_api_key", "")
cohere_key = ""  # Menggunakan pencarian kosinus standar tanpa Cohere Rerank agar performa cepat & mandiri
openai_key = ""
llm_provider = "gemini"

vector_store_path = "data/beasiswa_vector_store.pkl"
pdf_path = "data/panduan_beasiswa_indonesia.pdf"
engine = RAGEngine(vector_store_path=vector_store_path)

# Auto-initialize/Index Vector Database if not present
db_exists = os.path.exists(vector_store_path)
pdf_exists = os.path.exists(pdf_path)

if not db_exists and pdf_exists:
    try:
        engine.build_vector_database(pdf_path)
        db_exists = True
    except Exception as e:
        st.error(f"Gagal menginisialisasi basis data vektor otomatis: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<div style='text-align: center; padding-top: 1rem;'><span style='font-size: 3rem;'>🎓</span></div>", unsafe_allow_html=True)
    st.title("Kawan Beasiswa")
    st.markdown("Asisten AI Informasi Beasiswa Indonesia")
    
    st.divider()
    
    # 1. Popular Questions Section
    st.subheader("🔥 Pertanyaan Populer")
    st.caption("Klik pertanyaan di bawah ini untuk langsung mengisi obrolan:")
    
    if st.button("• Apa itu IISMA?", use_container_width=True):
        st.session_state.preset_query = "Apa itu IISMA?"
        st.rerun()
    if st.button("• Syarat LPDP", use_container_width=True):
        st.session_state.preset_query = "Syarat LPDP"
        st.rerun()
    if st.button("• Jadwal KIP Kuliah", use_container_width=True):
        st.session_state.preset_query = "Jadwal KIP Kuliah"
        st.rerun()
    if st.button("• Tips wawancara LPDP", use_container_width=True):
        st.session_state.preset_query = "Tips wawancara LPDP"
        st.rerun()
    if st.button("• Cara membuat motivation letter", use_container_width=True):
        st.session_state.preset_query = "Cara membuat motivation letter"
        st.rerun()

    st.divider()
    st.subheader("🤖 Mode AI & RAG")
    rag_mode = st.selectbox(
        "Pilih Engine RAG:",
        ["n8n Cloud (Mistral + Pinecone)", "Gemini API (RAG Python Lokal)"]
    )

# --- MAIN CONTENT ---
st.title("🎓 Kawan Beasiswa")

st.markdown("##### *Temukan informasi syarat, jadwal pendaftaran, dan tips praktis lolos beasiswa impian Anda.*")

# Tabs for organization
tab_chat, tab_info = st.tabs(["💬 Chatbot Informasi", "📚 Ringkasan Panduan Beasiswa"])

# --- TAB 1: Chatbot ---
with tab_chat:
    # Render Chat History
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])
            if chat["role"] == "assistant" and "sources" in chat and chat["sources"]:
                with st.expander("🔍 Konteks Dokumen Sumber (RAG)"):
                    for i, src in enumerate(chat["sources"]):
                        st.caption(f"**Dokumen {i+1} &bull; Halaman {src['page']}** &bull; Skor Relevansi: {src['score']:.4f}")
                        st.info(src['text'])

    # Chat Input
    query = st.chat_input("Tanyakan syarat, jadwal, atau tips (misal: 'Apa saja syarat beasiswa IISMA?' atau 'Bagi tips wawancara LPDP dong')")
    
    # Determine active query
    active_query = None
    if query:
        active_query = query
    elif st.session_state.preset_query:
        active_query = st.session_state.preset_query
        st.session_state.preset_query = None  # Reset
        
    if active_query:
        # Display user message
        with st.chat_message("user"):
            st.markdown(active_query)
        st.session_state.chat_history.append({"role": "user", "content": active_query})
        
        # Assistant generation
        with st.chat_message("assistant"):
            if rag_mode == "n8n Cloud (Mistral + Pinecone)":
                with st.spinner("Menghubungi asisten AI di n8n..."):
                    try:
                        n8n_url = "https://satori007.app.n8n.cloud/webhook/55d2b961-6b1b-4bb4-9d0a-cacc865fb33c/chat"
                        payload = {
                            "chatInput": active_query,
                            "sessionId": st.session_state.session_id
                        }
                        response = requests.post(n8n_url, json=payload)
                        response.raise_for_status()
                        response_data = response.json()
                        
                        answer = response_data.get("output", "Gagal mendapatkan jawaban dari n8n.")
                        st.markdown(answer)
                        
                        # Save history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "sources": []
                        })
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal memproses jawaban dari n8n: {e}")
            else:
                # Check API Key
                active_key = gemini_key if llm_provider == "gemini" else openai_key
                if not active_key:
                    st.error("🔑 Mohon isi API Key yang sesuai di file konfigurasi/Secrets.")
                    st.stop()
                    
                if not db_exists:
                    st.error("📁 Database vektor belum dibuat dan gagal diinisialisasi secara otomatis.")
                    st.stop()

                with st.spinner("Mencari referensi beasiswa dan merumuskan jawaban..."):
                    try:
                        # 1. Retrieve
                        retrieved = engine.retrieve(active_query, top_k=15)
                        
                        # 2. Rerank
                        reranked = engine.rerank(active_query, retrieved, top_n=5, cohere_api_key=cohere_key if cohere_key else None)
                        
                        # 3. Generate
                        answer = engine.generate_answer(active_query, reranked, api_key=active_key, model_provider=llm_provider)
                        
                        # Output response
                        st.markdown(answer)
                        
                        # Display sources expander
                        with st.expander("🔍 Konteks Dokumen Sumber (RAG)"):
                            for i, src in enumerate(reranked):
                                st.caption(f"**Dokumen {i+1} &bull; Halaman {src['page']}** &bull; Skor Relevansi: {src['score']:.4f}")
                                st.info(src['text'])
                                
                        # Save history
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": answer,
                            "sources": reranked
                        })
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Gagal memproses jawaban: {e}")

# --- TAB 2: Ringkasan Panduan ---
with tab_info:
    st.subheader("📚 Program Beasiswa Unggulan di Indonesia")
    st.markdown("""
    Berikut adalah rangkuman singkat mengenai beasiswa populer di Indonesia yang dicakup di dalam panduan resmi chatbot ini:
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        ##### 🏆 1. Beasiswa LPDP
        - **Kategori**: Magister (S2) dan Doktor (S3) Dalam/Luar Negeri.
        - **Syarat Kunci**: IPK S2 &ge; 3.00, IPK S3 &ge; 3.25; Batas usia S2 (35 tahun) dan S3 (40 tahun).
        - **Jadwal**: Dibuka 2 tahap (Tahap 1 sekitar Jan-Feb, Tahap 2 sekitar Jun-Jul).
        """)
        
        st.warning("""
        ##### ✈️ 2. Beasiswa IISMA
        - **Kategori**: Pertukaran mahasiswa sarjana (S1) dan vokasi ke luar negeri selama 1 semester.
        - **Syarat Kunci**: Mahasiswa semester 4 atau 6, IPK &ge; 3.0, skor IELTS &ge; 6.0 / Duolingo &ge; 100.
        - **Jadwal**: Pendaftaran dibuka sekitar Jan-Feb setiap tahun.
        """)
        
    with col2:
        st.success("""
        ##### 🌟 3. Beasiswa Unggulan (BU)
        - **Kategori**: Mahasiswa berprestasi jenjang S1, S2, dan S3 di perguruan tinggi dalam negeri.
        - **Syarat Kunci**: Mahasiswa baru atau maksimal semester 3, memiliki sertifikat prestasi minimal tingkat kabupaten/kota.
        - **Jadwal**: Pendaftaran dibuka sekitar Juli-Agustus setiap tahun.
        """)
        
        st.error("""
        ##### 🏫 4. Beasiswa BPI Kemendiktisaintek
        - **Kategori**: Calon dosen, guru, pelaku budaya, dan siswa berprestasi (S1/S2/S3).
        - **Syarat Kunci**: Wajib memiliki surat LoA Unconditional (penerimaan tanpa syarat) dari universitas tujuan.
        - **Jadwal**: Pendaftaran dibuka sekitar Mei-Juni setiap tahun.
        """)
        
    st.divider()
    st.markdown("""
    💡 *Tips Umum*: Siapkan berkas portofolio prestasi, surat rekomendasi, dan sertifikat kemampuan bahasa Inggris Anda minimal 3-6 bulan sebelum tanggal pembukaan pendaftaran untuk hasil yang maksimal.
    """)
