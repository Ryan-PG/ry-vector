from __future__ import annotations

from dataclasses import asdict
import json
import sqlite3

import streamlit as st

from app.auth.service import login_user, register_user
from app.config import get_settings
from app.db.database import init_db
from app.db import repositories as repo
from app.models.schemas import ChatSessionRecord, UserRecord
from app.rag.chat import answer_question, stream_answer_question
from app.rag.ingestion import delete_document, ingest_upload, supported_file_types
from app.rag.retrieval import search_documents


st.set_page_config(page_title="Ry-Vector", layout="wide")


def init_state() -> None:
    init_db()
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("active_chat_id", None)


def current_user() -> UserRecord | None:
    user = st.session_state.get("user")
    if not user:
        return None
    fresh = repo.get_user_by_id(user["id"])
    return fresh


def login_register_page() -> None:
    st.title("Ry-Vector")
    st.caption("Private multi-user RAG over your own documents.")
    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            identifier = st.text_input("Username or email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = login_user(identifier, password)
            if user:
                st.session_state["user"] = {"id": user.id, "username": user.username, "email": user.email}
                st.rerun()
            st.error("Invalid username/email or password.")

    with tab_register:
        with st.form("register_form"):
            username = st.text_input("Username", key="register_username")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            if len(username.strip()) < 3:
                st.error("Username must be at least 3 characters.")
            elif "@" not in email:
                st.error("Enter a valid email address.")
            elif len(password) < 8:
                st.error("Password must be at least 8 characters.")
            elif password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    user = register_user(username, email, password)
                    st.session_state["user"] = {"id": user.id, "username": user.username, "email": user.email}
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Username or email already exists.")


def sidebar(user: UserRecord) -> None:
    with st.sidebar:
        st.subheader("Ry-Vector")
        st.caption(f"Signed in as {user.username}")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def dashboard_page(user: UserRecord) -> None:
    stats = repo.user_stats(user.id)
    st.title("Dashboard")
    cols = st.columns(4)
    cols[0].metric("Documents", stats["documents"])
    cols[1].metric("Chunks", stats["chunks"])
    cols[2].metric("Chats", stats["sessions"])
    cols[3].metric("Messages", stats["messages"])

    st.subheader("Recent documents")
    documents = repo.list_documents(user.id)
    if not documents:
        st.info("Upload a document to start searching and chatting.")
        return
    for document in documents[:8]:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            left.markdown(f"**{document.original_filename}**")
            left.caption(f"Status: {document.status} | Chunks: {document.chunk_count} | Uploaded: {document.created_at}")
            if document.preview_text:
                left.write(document.preview_text)
            if right.button("Delete", key=f"delete_doc_{document.id}"):
                try:
                    delete_document(user.id, document.id)
                    st.success("Document deleted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Delete failed: {exc}")


def upload_page(user: UserRecord) -> None:
    settings = get_settings()
    st.title("Upload Documents")
    st.caption(f"Chunk size {settings.chunk_size}, overlap {settings.chunk_overlap}.")
    uploaded_files = st.file_uploader(
        "Upload PDF, DOCX, XLSX, Markdown, or TXT",
        type=supported_file_types(),
        accept_multiple_files=True,
    )
    reembed_existing = st.checkbox("Re-embed duplicate files", value=False)
    if st.button("Process uploads", disabled=not uploaded_files, use_container_width=True):
        for uploaded in uploaded_files or []:
            with st.status(f"Processing {uploaded.name}", expanded=True) as status:
                try:
                    document = ingest_upload(
                        user_id=user.id,
                        original_filename=uploaded.name,
                        file_bytes=uploaded.getvalue(),
                        settings=settings,
                        reembed_existing=reembed_existing,
                    )
                    status.update(label=f"Ready: {document.original_filename}", state="complete")
                    st.write(f"Document ID {document.id}, {document.chunk_count} chunks")
                except Exception as exc:
                    status.update(label=f"Failed: {uploaded.name}", state="error")
                    st.error(str(exc))

    st.subheader("Your documents")
    for document in repo.list_documents(user.id):
        with st.container(border=True):
            st.markdown(f"**{document.original_filename}**")
            st.caption(f"ID {document.id} | {document.status} | {document.chunk_count} chunks")
            if document.preview_text:
                st.write(document.preview_text)


def selected_document_ids(user: UserRecord, key: str) -> list[int] | None:
    documents = [doc for doc in repo.list_documents(user.id) if doc.status == "ready"]
    labels = {f"{doc.original_filename} (ID {doc.id})": doc.id for doc in documents}
    selected = st.multiselect("Document filter", list(labels.keys()), key=key)
    return [labels[label] for label in selected] if selected else None


def search_page(user: UserRecord) -> None:
    settings = get_settings()
    st.title("Search")
    top_k = st.slider("Top K results", min_value=1, max_value=20, value=settings.top_k_default)
    document_ids = selected_document_ids(user, "search_doc_filter")
    query = st.text_input("Search query")
    if st.button("Search", disabled=not query.strip(), use_container_width=True):
        try:
            results = search_documents(user.id, query.strip(), top_k=top_k, document_ids=document_ids)
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            return
        st.caption(f"Returned {len(results)} of requested top {top_k}.")
        if not results:
            st.info("No matching chunks found.")
        for result in results:
            with st.container(border=True):
                st.markdown(f"**{result.filename}** | chunk `{result.chunk_index}` | score `{result.score:.4f}`")
                if result.source_ref:
                    st.caption(result.source_ref)
                st.write(result.text_chunk)


def ensure_chat_session(user: UserRecord, document_ids: list[int] | None) -> int:
    session_id = st.session_state.get("active_chat_id")
    if session_id and repo.get_chat_session(session_id, user.id):
        repo.update_chat_session_scope(session_id, user.id, document_ids)
        return session_id
    session = repo.create_chat_session(user.id, "New chat", document_scope=document_ids)
    st.session_state["active_chat_id"] = session.id
    return session.id


def active_chat_session(sessions: list[ChatSessionRecord]) -> ChatSessionRecord | None:
    session_id = st.session_state.get("active_chat_id")
    for session in sessions:
        if session.id == session_id:
            return session
    if sessions:
        st.session_state["active_chat_id"] = sessions[0].id
        return sessions[0]
    st.session_state.pop("active_chat_id", None)
    return None


def activate_next_chat_session(sessions: list[ChatSessionRecord], deleted_session_id: int) -> None:
    remaining = [session for session in sessions if session.id != deleted_session_id]
    if remaining:
        st.session_state["active_chat_id"] = remaining[0].id
    else:
        st.session_state.pop("active_chat_id", None)


def chat_page(user: UserRecord) -> None:
    settings = get_settings()
    st.title("Chat")
    sessions = repo.list_chat_sessions(user.id)
    active_session = active_chat_session(sessions)
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Sessions")
        if st.button("New chat", use_container_width=True):
            session = repo.create_chat_session(user.id, "New chat")
            st.session_state["active_chat_id"] = session.id
            st.rerun()
        if not sessions:
            st.info("No chat history yet.")
        for session in sessions:
            label = f"{session.title} #{session.id}"
            select_col, delete_col = st.columns([4, 1])
            button_type = "primary" if active_session and active_session.id == session.id else "secondary"
            if select_col.button(label, key=f"session_{session.id}", type=button_type, use_container_width=True):
                st.session_state["active_chat_id"] = session.id
                st.rerun()
            if delete_col.button("Delete", key=f"delete_session_{session.id}", use_container_width=True):
                repo.delete_chat_session(session.id, user.id)
                activate_next_chat_session(sessions, session.id)
                st.success("Chat history deleted.")
                st.rerun()
        if active_session:
            export = repo.export_chat_session(active_session.id, user.id)
            export_data = {
                "session": asdict(export["session"]),
                "messages": [asdict(message) for message in export["messages"]],
            }
            st.download_button(
                "Export JSON",
                data=json.dumps(export_data, indent=2),
                file_name=f"chat_{active_session.id}.json",
                mime="application/json",
                use_container_width=True,
            )

    with right:
        top_k = st.slider("Retrieval top K", 1, 20, settings.top_k_default)
        document_ids = selected_document_ids(user, "chat_doc_filter")
        if active_session:
            messages = repo.list_chat_messages(active_session.id, user.id)
            for message in messages:
                with st.chat_message(message.role):
                    st.write(message.content)
                    if message.citations:
                        with st.expander("Citations"):
                            st.json(json.loads(message.citations))
        else:
            st.info("Start a new chat or ask a question to create one.")

        prompt = st.chat_input("Ask about your documents")
        if prompt:
            session_id = active_session.id if active_session else ensure_chat_session(user, document_ids)
            repo.update_chat_session_scope(session_id, user.id, document_ids)
            repo.add_chat_message(session_id, user.id, "user", prompt)
            with st.chat_message("user"):
                st.write(prompt)
            with st.chat_message("assistant"):
                try:
                    if settings.streaming_enabled:
                        stream, citations, _ = stream_answer_question(
                            user_id=user.id,
                            query=prompt,
                            top_k=top_k,
                            document_ids=document_ids,
                            settings=settings,
                        )
                        answer = st.write_stream(stream)
                    else:
                        answer, citations, _ = answer_question(
                            user_id=user.id,
                            query=prompt,
                            top_k=top_k,
                            document_ids=document_ids,
                            settings=settings,
                        )
                        st.write(answer)
                    repo.add_chat_message(session_id, user.id, "assistant", str(answer), citations)
                    if citations:
                        with st.expander("Citations"):
                            st.json(citations)
                except Exception as exc:
                    st.error(f"Chat failed: {exc}")


def settings_page(user: UserRecord) -> None:
    settings = get_settings()
    st.title("Settings")
    st.subheader("Runtime")
    st.code(
        "\n".join(
            [
                f"LLM_PROVIDER={settings.llm_provider}",
                f"CHAT_MODEL={settings.chat_model}",
                f"EMBEDDING_MODEL={settings.embedding_model}",
                f"OLLAMA_BASE_URL={settings.ollama_base_url}",
                f"OLLAMA_CHAT_MODEL={settings.ollama_chat_model}",
                f"OLLAMA_EMBEDDING_MODEL={settings.ollama_embedding_model}",
                f"CHUNK_SIZE={settings.chunk_size}",
                f"CHUNK_OVERLAP={settings.chunk_overlap}",
                f"TOP_K_DEFAULT={settings.top_k_default}",
                f"STREAMING_ENABLED={settings.streaming_enabled}",
                f"SQLITE_PATH={settings.sqlite_path}",
                f"QDRANT_HOST={settings.qdrant_host}",
                f"QDRANT_PORT={settings.qdrant_port}",
                f"QDRANT_COLLECTION={settings.qdrant_collection_prefix}{user.id}",
            ]
        )
    )
    st.subheader("Account")
    st.write(f"Username: `{user.username}`")
    st.write(f"Email: `{user.email}`")
    st.caption("Edit `.env` and restart the container to change providers or model settings.")


def main() -> None:
    init_state()
    user = current_user()
    if not user:
        login_register_page()
        return

    sidebar(user)
    dashboard_tab, upload_tab, search_tab, chat_tab, settings_tab = st.tabs(
        ["Dashboard", "Upload Documents", "Search", "Chat", "Settings"]
    )
    with dashboard_tab:
        dashboard_page(user)
    with upload_tab:
        upload_page(user)
    with search_tab:
        search_page(user)
    with chat_tab:
        chat_page(user)
    with settings_tab:
        settings_page(user)


if __name__ == "__main__":
    main()
