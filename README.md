# Kawan Beasiswa: Chatbot RAG Informasi Beasiswa Indonesia 🎓

Aplikasi RAG (Retrieval-Augmented Generation) berbasis web menggunakan **Streamlit** (Python) untuk mencari persyaratan, jadwal pendaftaran, dan tips seleksi beasiswa populer di Indonesia (LPDP, IISMA, Beasiswa Unggulan, dan BPI).

Proyek ini dibuat untuk memenuhi tugas kuliah mata kuliah **Retrieval Augmented Generation** oleh **RB Fajriya Hakim**.

## 🚀 Fitur Utama
1. **Minimalist Blue & White Ambience**: Antarmuka web bersih dan ramah pengguna dengan nuansa warna biru dan putih khas akademis.
2. **Local Document Chunking & Indexing**: Ekstraksi berkas panduan PDF secara cerdas menggunakan *Recursive Character Text Splitter*, lalu dikonversi menjadi representasi vektor numerik secara lokal menggunakan model `all-MiniLM-L6-v2`.
3. **Lightweight Vector Store**: Penyimpanan vektor berbasis numpy dan pickle lokal, sangat cepat dan terhindar dari kendala instalasi C++ compiler di Windows.
4. **Semantic Retrieval**: Pencarian kecocokan kosinus (*cosine similarity*) lokal yang cepat dan efisien.
5. **Cohere Reranking (Opsional)**: Penyaringan hasil pencarian menggunakan Cohere Rerank API (`rerank-multilingual-v2.0`) untuk menyeleksi 5 dokumen paling relevan.
6. **Gemini 3.5 Flash Generation**: Integrasi model LLM terbaru (tahun 2026) untuk menghasilkan jawaban valid dengan referensi nomor halaman dokumen asli.
7. **RAG Context Visualizer**: Panel ekspander di bawah jawaban chatbot yang memvisualisasikan dokumen sumber asli (*retrieved context*) dan skor relevansinya.

---

## 🛠️ Persyaratan & Instalasi

### 1. Prasyarat
Pastikan Anda memiliki **Python 3.10** atau versi yang lebih baru terinstal di komputer Anda.

### 2. Instalasi Dependensi
Buka terminal/Command Prompt di folder proyek ini, lalu jalankan perintah berikut:
```bash
pip install -r requirements.txt
```

### 3. Struktur Folder
Struktur berkas proyek:
```
Retrieval Augmented Generation/
│
├── data/
│   └── panduan_beasiswa_indonesia.pdf     # PDF Informasi Beasiswa (6 Halaman)
│
├── app.py                                 # Web GUI Streamlit
├── rag_engine.py                          # Logika Utama RAG
├── requirements.txt                       # Dependensi Python
├── README.md                              # Panduan Penggunaan Singkat
└── Laporan_Tugas_RAG.md                   # Laporan Tugas Kuliah Resmi
```

---

## 🏃 Cara Menjalankan Aplikasi

1. Buka terminal di folder proyek ini dan jalankan perintah:
   ```bash
   streamlit run app.py
   ```
2. Aplikasi akan terbuka otomatis di browser Anda di alamat `http://localhost:8501`.
3. Pada panel samping kiri (**Sidebar**):
   - Masukkan **Gemini API Key** Anda dari Google AI Studio.
   - Masukkan **Cohere API Key** jika ingin mengaktifkan Reranker (opsional).
   - Klik tombol **`🔨 Buat Vector Database (Indexing)`** saat pertama kali dijalankan untuk melatih chatbot membaca PDF panduan beasiswa.
4. Setelah muncul tulisan **`✅ Database Vektor Siap`**, Anda dapat mulai bertanya di tab **Chatbot Informasi**!
