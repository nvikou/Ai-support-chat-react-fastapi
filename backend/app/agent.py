import os
import re
import hashlib
from pathlib import Path
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from app.config import get_settings

settings = get_settings()

FAISS_PATH = "./faiss_db"

SYSTEM_PROMPT = """You are a professional AI support agent for a company. Your role is to help customers efficiently and accurately.

Guidelines:
- Be professional, friendly, and concise
- Use the provided context (knowledge base) to answer questions accurately
- If you're not confident in your answer (confidence < 0.7), acknowledge uncertainty clearly
- If a question is outside your knowledge base or requires human judgment, say so clearly
- Always try to resolve issues completely in one response when possible
- Keep responses clear and structured when needed (use bullet points for lists)
- If the customer seems frustrated or the issue is complex/sensitive, recommend escalation to a human agent

Context from knowledge base:
{context}

Conversation history:
{chat_history}

Customer question: {question}

Provide a helpful, accurate response. At the end, on a new line, add: CONFIDENCE: [0.0-1.0] based on how confident you are in your answer.
"""


def split_markdown_text(markdown_text: str, strip_headers: bool = False) -> list[Document]:
    """Découpe un texte Markdown en chunks en suivant les niveaux de titres."""
    # Supprimer les lignes vides multiples et les espaces superflus
    markdown_text = re.sub(r' {1,}', ' ', re.sub(r'\n\s*\n', '\n', markdown_text))

    headers_to_split_on = [
        ("#",   "Header 1"),
        ("##",  "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
        strip_headers=strip_headers,
    )
    return markdown_splitter.split_text(markdown_text)


class SupportAgent:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0.3,
        )
        self.vectorstore = self._load_or_create_vectorstore()
        # Splitter de secours pour les textes non-Markdown (PDF, TXT brut)
        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
        )

    def _load_or_create_vectorstore(self) -> FAISS:
        Path(FAISS_PATH).mkdir(parents=True, exist_ok=True)
        index_file = Path(FAISS_PATH) / "index.faiss"
        if index_file.exists():
            return FAISS.load_local(
                FAISS_PATH,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
        # Initialiser avec un document vide pour créer l'index
        dummy = Document(page_content="VateCon AI Support initialized.", metadata={"source": "system"})
        store = FAISS.from_documents([dummy], self.embeddings)
        store.save_local(FAISS_PATH)
        return store

    def _save_vectorstore(self):
        self.vectorstore.save_local(FAISS_PATH)

    def _get_chain(self, session_history: list[dict]):
        prompt = PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template=SYSTEM_PROMPT,
        )
        retriever = self.vectorstore.as_retriever(
            search_type="mmr",
            search_kwargs={"k": 5, "fetch_k": 10},
        )
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=10,
            output_key="answer",
        )
        for msg in session_history[-10:]:
            if msg["role"] == "user":
                memory.chat_memory.add_user_message(msg["content"])
            elif msg["role"] == "assistant":
                memory.chat_memory.add_ai_message(msg["content"])

        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=retriever,
            memory=memory,
            combine_docs_chain_kwargs={"prompt": prompt},
            return_source_documents=True,
            verbose=False,
        )

    async def answer(self, question: str, history: list[dict]) -> dict:
        chain = self._get_chain(history)
        result = await chain.ainvoke({"question": question})

        raw_answer = result["answer"]
        source_docs = result.get("source_documents", [])

        confidence = 0.8
        answer_text = raw_answer
        if "CONFIDENCE:" in raw_answer:
            parts = raw_answer.rsplit("CONFIDENCE:", 1)
            answer_text = parts[0].strip()
            try:
                confidence = float(parts[1].strip())
            except ValueError:
                confidence = 0.8

        sources = list({doc.metadata.get("source", "Knowledge Base") for doc in source_docs})
        should_escalate = confidence < 0.5 or self._detect_escalation_keywords(question)

        return {
            "answer": answer_text,
            "confidence": confidence,
            "sources": sources,
            "should_escalate": should_escalate,
            "escalation_reason": self._get_escalation_reason(confidence, question) if should_escalate else None,
        }

    def _detect_escalation_keywords(self, text: str) -> bool:
        keywords = [
            "refund", "lawsuit", "legal", "fraud", "cancel account",
            "speak to manager", "human agent", "very upset", "furious",
            "remboursement", "arnaque", "parler à un humain",
        ]
        return any(kw in text.lower() for kw in keywords)

    def _get_escalation_reason(self, confidence: float, question: str) -> str:
        if self._detect_escalation_keywords(question):
            return "Sensitive topic detected — requires human handling"
        return f"Low confidence answer ({confidence:.0%}) — escalating to ensure accuracy"

    async def ingest_document(self, file_path: str, filename: str) -> int:
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            for doc in documents:
                doc.metadata["source"] = filename
            chunks = self.fallback_splitter.split_documents(documents)
        else:
            # Lire le contenu texte et utiliser MarkdownHeaderTextSplitter
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            chunks = split_markdown_text(content, strip_headers=False)
            for chunk in chunks:
                chunk.metadata["source"] = filename

            # Si le splitter Markdown ne produit qu'un seul chunk (texte sans titres),
            # on repasse par le splitter récursif classique
            if len(chunks) <= 1:
                loader = TextLoader(file_path, encoding="utf-8")
                documents = loader.load()
                for doc in documents:
                    doc.metadata["source"] = filename
                chunks = self.fallback_splitter.split_documents(documents)

        self.vectorstore.add_documents(chunks)
        self._save_vectorstore()
        return len(chunks)

    async def add_faq_entries(self, entries: list[dict]) -> int:
        docs = [
            Document(
                page_content=f"Q: {e['question']}\nA: {e['answer']}",
                metadata={"source": "FAQ", "category": e.get("category", "general")},
            )
            for e in entries
        ]
        self.vectorstore.add_documents(docs)
        self._save_vectorstore()
        return len(docs)


_agent_instance: SupportAgent | None = None


def get_agent() -> SupportAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SupportAgent()
    return _agent_instance

