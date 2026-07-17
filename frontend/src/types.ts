export interface User {
  id: number;
  email: string;
  created_at: string;
}

export interface Document {
  id: number;
  title: string;
  content: string;
  source_type: string;
  file_name: string | null;
  chunk_count: number;
  created_at: string;
}

export interface AnalysisMetrics {
  word_count: number;
  unique_words: number;
  sentence_count: number;
  avg_word_length: number;
  reading_time_min: number;
  subjectivity: number;
  readability_grade: number | null;
  flesch_reading_ease: number | null;
}

export interface Analysis {
  id: number;
  document_id: number;
  summary: string;
  sentiment: string;
  sentiment_score: number;
  keywords: string[];
  topics: string[];
  metrics: AnalysisMetrics | null;
  provider: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  document_id: number;
  role: "user" | "assistant";
  content: string;
  rag_chunks_used: number | null;
  created_at: string;
}

export interface Health {
  status: string;
  ai_provider: string;
  features: {
    rag_tfidf: boolean;
    rag_embeddings?: boolean;
    retrieval_mode?: "hybrid" | "tfidf";
    embedding_model?: string | null;
    vector_store?: boolean;
    vector_store_backend?: string | null;
    llm_enabled?: boolean;
    llm_provider?: "local" | "gemini" | "groq" | "ollama";
    llm_model?: string | null;
    storage_mode?: "local" | "ephemeral" | "persistent";
    auth?: boolean;
    readability_metrics: boolean;
    file_upload: boolean;
    analysis_history: boolean;
  };
}
