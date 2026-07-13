import os
import pickle
import numpy as np
from pypdf import PdfReader

# Optional API integrations
import google.generativeai as genai
import openai
import cohere

class RecursiveCharacterTextSplitter:
    """A simple Python implementation of recursive character text splitter."""
    def __init__(self, chunk_size=800, chunk_overlap=150, separators=None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text):
        return self._split_text(text, self.separators)

    def _split_text(self, text, separators):
        # Base case
        if len(text) <= self.chunk_size:
            return [text]
        
        if not separators:
            # Force split by size
            return [text[i:i+self.chunk_size] for i in range(0, len(text), self.chunk_size - self.chunk_overlap)]

        # Get separator
        separator = separators[0]
        splits = text.split(separator)
        
        chunks = []
        current_chunk = ""
        
        for split in splits:
            # If the single split is larger than chunk size, split it recursively using next separators
            if len(split) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                # Recursively split the long block
                sub_chunks = self._split_text(split, separators[1:])
                chunks.extend(sub_chunks)
            else:
                # Check if adding this split exceeds chunk size
                potential_chunk = current_chunk + separator + split if current_chunk else split
                if len(potential_chunk) <= self.chunk_size:
                    current_chunk = potential_chunk
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    # Start new chunk with overlap
                    # Simple overlap: take last characters from previous chunk
                    if current_chunk:
                        overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                        current_chunk = current_chunk[overlap_start:] + separator + split
                    else:
                        current_chunk = split
                        
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks

class RAGEngine:
    def __init__(self, vector_store_path="data/beasiswa_vector_store.pkl"):
        self.vector_store_path = vector_store_path
        self.embedding_model = None
        self.vector_db = None
        
    def init_local_embeddings(self):
        """Lazy load local sentence-transformers to save startup time."""
        if self.embedding_model is None:
            print("Loading local embedding model (all-MiniLM-L6-v2)...")
            from sentence_transformers import SentenceTransformer
            # Force CPU usage to avoid CUDA conflicts or memory errors
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            print("Local embedding model loaded successfully.")

    def get_embedding(self, text):
        """Generate embedding using local model."""
        self.init_local_embeddings()
        emb = self.embedding_model.encode(text)
        return emb

    def extract_text_from_pdf(self, pdf_path):
        """Extract text page by page from the PDF."""
        print(f"Reading PDF from {pdf_path}...")
        reader = PdfReader(pdf_path)
        pages_content = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                pages_content.append({
                    "text": text,
                    "page_number": i + 1
                })
        print(f"Extracted {len(pages_content)} non-empty pages from PDF.")
        return pages_content

    def build_vector_database(self, pdf_path, chunk_size=800, chunk_overlap=150):
        """Processes PDF, chunks it, generates embeddings, and saves DB to disk."""
        pages_content = self.extract_text_from_pdf(pdf_path)
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        chunks = []
        for page in pages_content:
            text_splits = splitter.split_text(page["text"])
            for split in text_splits:
                if len(split.strip()) > 30: # Filter very small noise chunks
                    chunks.append({
                        "text": split,
                        "page": page["page_number"],
                        "source": os.path.basename(pdf_path)
                    })
        
        print(f"Total chunks generated: {len(chunks)}")
        print("Generating embeddings for all chunks... (this may take a minute)")
        
        # Initalize model
        self.init_local_embeddings()
        
        # Batch encode is faster
        texts_to_encode = [c["text"] for c in chunks]
        embeddings = self.embedding_model.encode(texts_to_encode, show_progress_bar=True)
        
        # Save to database
        self.vector_db = {
            "chunks": chunks,
            "embeddings": np.array(embeddings)
        }
        
        # Ensure output dir exists
        os.makedirs(os.path.dirname(self.vector_store_path), exist_ok=True)
        with open(self.vector_store_path, "wb") as f:
            pickle.dump(self.vector_db, f)
            
        print(f"Vector database saved to {self.vector_store_path}")
        return len(chunks)

    def load_vector_database(self):
        """Load vector database from file."""
        if not os.path.exists(self.vector_store_path):
            return False
        
        with open(self.vector_store_path, "rb") as f:
            self.vector_db = pickle.load(f)
        return True

    def retrieve(self, query, top_k=10):
        """Retrieve top_k chunks using cosine similarity."""
        if not self.vector_db:
            if not self.load_vector_database():
                raise FileNotFoundError("Vector database not found. Please index the PDF document first.")
                
        query_vector = self.get_embedding(query)
        embeddings = self.vector_db["embeddings"]
        chunks = self.vector_db["chunks"]
        
        # Compute cosine similarity manually
        # similarity = dot_product(A, B) / (norm(A) * norm(B))
        dot_products = np.dot(embeddings, query_vector)
        norms_emb = np.linalg.norm(embeddings, axis=1)
        norm_query = np.linalg.norm(query_vector)
        
        # Prevent division by zero
        norms_emb[norms_emb == 0] = 1e-10
        if norm_query == 0:
            norm_query = 1e-10
            
        similarities = dot_products / (norms_emb * norm_query)
        
        # Get top indices sorted descending
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "text": chunks[idx]["text"],
                "page": chunks[idx]["page"],
                "source": chunks[idx]["source"],
                "score": float(similarities[idx])
            })
            
        return results

    def rerank(self, query, retrieved_results, top_n=5, cohere_api_key=None):
        """Rerank retrieved results using Cohere Rerank API if available, else fallback."""
        if not cohere_api_key:
            # Fallback to cosine similarity score order (already sorted)
            return retrieved_results[:top_n]
            
        try:
            print("Reranking results using Cohere Rerank API...")
            co = cohere.Client(cohere_api_key)
            
            # Format documents for Cohere API
            docs = [res["text"] for res in retrieved_results]
            
            response = co.rerank(
                model="rerank-multilingual-v2.0", # Highly effective for Indonesian
                query=query,
                documents=docs,
                top_n=top_n
            )
            
            reranked_results = []
            for hit in response.results:
                original_idx = hit.index
                original_result = retrieved_results[original_idx]
                reranked_results.append({
                    "text": original_result["text"],
                    "page": original_result["page"],
                    "source": original_result["source"],
                    "score": float(hit.relevance_score)
                })
            return reranked_results
            
        except Exception as e:
            print(f"Error during Cohere Rerank: {e}. Falling back to cosine similarity scores.")
            return retrieved_results[:top_n]

    def generate_answer(self, query, context_results, api_key, model_provider="gemini"):
        """Generate answer using Gemini or OpenAI API."""
        # Compile context string
        context_str = ""
        for i, res in enumerate(context_results):
            context_str += f"\n--- DOKUMEN {i+1} (Halaman {res['page']}) ---\n{res['text']}\n"
            
        system_instruction = (
            "Anda adalah 'Kawan Beasiswa', Chatbot RAG informasi dan panduan resmi Beasiswa Indonesia (LPDP, IISMA, Beasiswa Unggulan, BPI Kemendiktisaintek, dll.). "
            "Tugas Anda adalah membantu calon pendaftar mencari syarat pendaftaran, jadwal, dan tips praktis lolos beasiswa berdasarkan dokumen panduan yang disediakan.\n\n"
            "Aturan menjawab:\n"
            "1. Jawablah pertanyaan pengguna menggunakan informasi yang ada pada Konteks Dokumen di bawah.\n"
            "2. Berikan jawaban dalam Bahasa Indonesia yang ramah, profesional, menyemangati, dan mudah dipahami oleh para akademisi/pelajar.\n"
            "3. Sebutkan nomor halaman referensi yang Anda gunakan di bagian akhir kalimat jawaban Anda (contoh: [Halaman 2]).\n"
            "4. Jika jawaban tidak ditemukan pada Konteks Dokumen, katakan dengan sopan bahwa informasi spesifik tersebut tidak dibahas di dalam Panduan Beasiswa Indonesia, kemudian berikan saran umum/tips pencarian yang relevan secara umum untuk membantu mereka.\n\n"
            f"Konteks Dokumen:\n{context_str}"
        )
        
        prompt = f"Pertanyaan Pengguna: {query}\n\nJawaban Anda:"
        
        if model_provider == "gemini":
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name="gemini-3.5-flash",
                    system_instruction=system_instruction
                )
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                return f"Gagal menghasilkan jawaban dari Gemini API: {str(e)}"
                
        elif model_provider == "openai":
            try:
                client = openai.OpenAI(api_key=api_key)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3
                )
                return response.choices[0].message.content
            except Exception as e:
                return f"Gagal menghasilkan jawaban dari OpenAI API: {str(e)}"
        else:
            return "Penyedia model LLM tidak valid."
