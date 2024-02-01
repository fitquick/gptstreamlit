# 必要なライブラリのインポート
import streamlit as st
import openai
import firebase_admin
from firebase_admin import credentials, firestore

# Firestoreの初期化
cred = credentials.Certificate('path/to/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Streamlitの秘密管理機能を使用してOpenAI APIキーを設定
openai.api_key = st.secrets["OpenAIAPI"]["openai_api_key"]

# Firestore設定（環境変数からGCPプロジェクトIDを取得）
GCP_PROJECT = st.secrets["GCP"]["project_id"]
db = firestore.Client(project=GCP_PROJECT)

# Streamlitアプリケーションの設定
st.title("QUICKFIT BOT")
st.write("Quick fitに関するQ&A AIBOT")

# CSSを使ってStreamlitのデフォルトのUIを非表示にする
HIDE_ST_STYLE = """
                <style>
                div[data-testid="stToolbar"], div[data-testid="stDecoration"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                </style>
"""
st.markdown(HIDE_ST_STYLE, unsafe_allow_html=True)

# 定数定義
USER_NAME = "user"
ASSISTANT_NAME = "assistant"
NEW_CHAT_TITLE = "New Chat"

# ChatGPTのレスポンスをストリーム形式で取得する関数
def response_chatgpt(user_msg: str, past_messages: list):
    messages_to_send = past_messages + [{"role": "user", "content": user_msg}]
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # 例としてgpt-3.5-turboを使用します。実際にはモデル名を適切に設定してください。
        messages=messages_to_send,
        stream=True,
    )
    return response

# Firestoreでの新しいチャット作成機能
def create_new_chat():
    st.session_state.displayed_chat_title = NEW_CHAT_TITLE
    st.session_state.displayed_chat_messages = []

# 表示中のチャットを変更する機能
def change_displayed_chat(chat_doc):
    st.session_state.displayed_chat_ref = chat_doc.reference
    st.session_state.displayed_chat_title = chat_doc.to_dict()["title"]
    st.session_state.displayed_chat_messages = [
        msg.to_dict() for msg in chat_doc.reference.collection("messages").order_by("timestamp").stream()
    ]

# メイン関数
def run():
    if "user" not in st.session_state:
        st.session_state.user = CHATBOT_USER

    if "chats_ref" not in st.session_state:
        user_ref = db.collection("users").document(st.session_state.user)
        st.session_state.chats_ref = user_ref.collection("chats")

    if "titles" not in st.session_state:
        st.session_state.titles = [doc.to_dict()["title"] for doc in st.session_state.chats_ref.order_by("created").stream()]

    if "displayed_chat_ref" not in st.session_state:
        st.session_state.displayed_chat_ref = None

    if "displayed_chat_title" not in st.session_state:
        st.session_state.displayed_chat_title = NEW_CHAT_TITLE

    if "displayed_chat_messages" not in st.session_state:
        st.session_state.displayed_chat_messages = []

    # サイドバーの設定
    with st.sidebar:
        new_chat_disable = st.session_state.displayed_chat_title == NEW_CHAT_TITLE
        st.button("新しい会話を始める", on_click=create_new_chat, disabled=new_chat_disable)
        st.title("過去の会話履歴")
        for doc in st.session_state.chats_ref.order_by("created").stream():
            data = doc.to_dict()
            st.button(data["title"], on_click=change_displayed_chat, args=(doc,))

    # チャットメッセージの表示
    for message in st.session_state.displayed_chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ユーザー入力の処理
    if user_input_text := st.chat_input("質問を入力してください"):
        # ユーザーメッセージの表示
        with st.chat_message(USER_NAME):
            st.write(user_input_text)

        # 新しいチャットが始まる場合の処理
        if len(st.session_state.displayed_chat_messages) == 0:
            chat_title_prompt = f"会話のタイトルを考えてください。ユーザーの入力: {user_input_text}"
            response = openai.ChatCompletion.create(
                model=MODEL_NAME,
                messages=[{"role": "system", "content": chat_title_prompt}]
            )
            st.session_state.displayed_chat_title = response.choices[0].message.content

            # Firestoreに新しいチャットを作成
            _, st.session_state.displayed_chat_ref = st.session_state.chats_ref.add({
                'title': st.session_state.displayed_chat_title,
                'created': firestore.SERVER_TIMESTAMP,
            })

        # ユーザーメッセージをFirestoreに保存
        user_input_data = {
            "role": "user",
            "content": user_input_text,
            "timestamp": firestore.SERVER_TIMESTAMP
        }
        st.session_state.displayed_chat_messages.append(user_input_data)
        st.session_state.displayed_chat_ref.collection("messages").add(user_input_data)

        # アシスタントのレスポンスをストリーム形式で取得し、表示
        response = response_chatgpt(user_input_text, st.session_state["messages"])
        assistant_msg = ""
        for chunk in response.iter_content():
            if "data" in chunk:
                assistant_msg += chunk["data"]
                with st.chat_message(ASSISTANT_NAME):
                    st.write(assistant_msg)
            if "choices" in chunk and chunk["choices"][0]["finish_reason"] is not None:
                break


            # アシスタントのメッセージをFirestoreに保存
            assistant_output_data = {
                "role": "assistant",
                "content": assistant_output_text,
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            st.session_state.displayed_chat_messages.append(assistant_output_data)
            st.session_state.displayed_chat_ref.collection("messages").add(assistant_output_data)

if __name__ == "__main__":
    run()
