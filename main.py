import openai
import streamlit as st
from google.cloud import firestore

# OpenAI APIキーの設定
openai.api_key = st.secrets["OpenAIAPI"]["openai_api_key"]

# Firestore設定（環境変数からGCPプロジェクトIDを取得）
GCP_PROJECT = st.secrets["GCP"]["project_id"]
db = firestore.Client(project=GCP_PROJECT)

MODEL_NAME = st.secrets["MODEL_NAME"]["Name"]
MODEL_TEMPERATURE = st.secrets["MODEL_TEMPERATURE"]["TEMPERATURE"]


NEW_CHAT_TITLE = "New Chat"
CHATBOT_USER = "QUIUK"
GCP_PROJECT = "YOUR_GCP_PROJECT"

def create_new_chat():
    st.session_state.displayed_chat_title = NEW_CHAT_TITLE
    st.session_state.displayed_chat_messages = []


def change_displayed_chat(chat_doc):
    # Update titles
    st.session_state.titles = [
        doc.to_dict()["title"] for doc in st.session_state.chats_ref.order_by("created").stream()
    ]

    st.session_state.displayed_chat_ref = chat_doc.reference
    st.session_state.displayed_chat_title = chat_doc.to_dict()["title"]
    st.session_state.displayed_chat_messages = [
        msg.to_dict()
        for msg in chat_doc.reference.collection("messages").order_by("timestamp").stream()
    ]


def run():

    if "user" not in st.session_state:
        st.session_state.user = CHATBOT_USER

    if "chats_ref" not in st.session_state:
        db = firestore.Client(project=GCP_PROJECT)
        user_ref = db.collection("users").document(st.session_state.user)
        st.session_state.chats_ref = user_ref.collection("chats")

    if "titles" not in st.session_state:
        st.session_state.titles = [
                doc.to_dict()["title"]
                for doc in st.session_state.chats_ref.order_by("created").stream()
                ]

    if "displayed_chat_ref" not in st.session_state:
        st.session_state.displayed_chat_ref = None

    if "displayed_chat_title" not in st.session_state:
        st.session_state.displayed_chat_title = "New Chat"

    if "displayed_chat_messages" not in st.session_state:
        st.session_state.displayed_chat_messages = []

    # Sidebar
    with st.sidebar:
        new_chat_disable = st.session_state.displayed_chat_title == NEW_CHAT_TITLE
        st.button("新しい会話を始める", on_click=create_new_chat, disabled=new_chat_disable, type="primary")
        st.title("過去の会話履歴")
        for doc in st.session_state.chats_ref.order_by("created").stream():
            data = doc.to_dict()
            st.button(data["title"], on_click=change_displayed_chat, args=(doc, ))

    # Display messages
    for message in st.session_state.displayed_chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input_text := st.chat_input("質問を入力してください"):

        # User
        with st.chat_message("user"):
            st.markdown(user_input_text)

        # Process first message
        if len(st.session_state.displayed_chat_messages) == 0:

            # Create new chat title
            chat_title_prompt = f"""
            あなたは優秀なアシスタントです。ユーザーの質問に最高品質で答えなさい。"""

            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[{'role': 'system', 'content': chat_title_prompt}]
            )
            st.session_state.displayed_chat_title = response['choices'][0]['message']['content']

            # Create new chat on firestore
            _, st.session_state.displayed_chat_ref = st.session_state.chats_ref.add(
                {
                'title': st.session_state.displayed_chat_title,
                'created': firestore.SERVER_TIMESTAMP,
                }
            )

        user_input_data = {
            "role": "user",
            "content": user_input_text,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        st.session_state.displayed_chat_messages.append(user_input_data)
        st.session_state.displayed_chat_ref.collection("messages").add(user_input_data)

        with st.spinner("回答を生成中です..."):
            # Generate llm response
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[
                    {"role":data["role"], "content":data["content"]}
                    for data in st.session_state.displayed_chat_messages
                ]
            )
            assistant_output_text = response['choices'][0]['message']['content']

            # Assistant
            with st.chat_message("assistant"):
                st.markdown(assistant_output_text)
            assistant_output_data = {
                "role": "assistant",
                "content": assistant_output_text,
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            st.session_state.displayed_chat_messages.append(assistant_output_data)
            st.session_state.displayed_chat_ref.collection("messages").add(assistant_output_data)


if __name__ == "__main__":
    run()
