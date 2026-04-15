import dotenv
dotenv.load_dotenv()
from openai import OpenAI
import asyncio
import time
import base64
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool, FileSearchTool

client = OpenAI()

VECTOR_STORE_ID = "vs_69df9a2a87888191855c23beb71d7369"


if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="My Life Coach Agent",
        instructions = """
        You are a helpful life coach assistant. You will help the user with any questions or problems they have, and provide advice and guidance to help them improve their life. 
        You can also use the tools at your disposal to find information and resources to help the user. Always be empathetic, supportive, and encouraging in your responses.
        You have access to the followign tools:
            - Web Search Tool: After searching through the file's content, use it to perform a web search so you can provide tailored advice that answers my questions.
            - File Search Tool: Please refer to the file containing my personal goals before giving me any advice. Use this tool to search for any information related to my personal goals, which are stored in the file vector store. Always refer to this file when giving me advice, and use the information in it to help me achieve my goals.
        """,
        tools=[
            WebSearchTool(),
            FileSearchTool(
                vector_store_ids=[VECTOR_STORE_ID],
                max_num_results=3,
            )
        ],
    )
agent = st.session_state["agent"]


if "session" not in st.session_state:
    st.session_state["session"] = SQLiteSession(
        "chat-history", 
        "chat-healthy-agent-memory.db"
        )
session = st.session_state["session"]


async def paint_history():
    messages = await session.get_items()
    for message in messages:
        if "role" in message:
            with st.chat_message(message["role"]):
                if message["role"] == "user":
                    st.write(message["content"])
                else:
                    if message["type"] == "message":
                        st.write(message["content"][0]["text"])

        if "type" in message:
            if message["type"] == "web_search_call":
                with st.chat_message("ai"):
                    st.write("🔍 Searching the web...")

            elif message["type"] == "file_search_call":
                with st.chat_message("ai"):
                    st.write("📂 Searching your files...")



asyncio.run(paint_history())



def update_status(status_container, event):
    status_messages = {
        'response.web_search_call.completed': ("✅ Web search completed", "complete"),
        'response.web_search_call.in_progress': ("🔍 Starting web search...", "running"),
        'response.web_search_call.searching': ("🔍 Web search in progress...", "running"),

        'response.file_search_call.completed': ("✅ File search completed", "complete"),
        'response.file_search_call.in_progress': ("📂 Starting file search...", "running"),
        'response.file_search_call.searching': ("📂 File search in progress...", "running"),
        'response.completed': (" ", "complete"),
    }


    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


async def run_agent(message):
    with st.chat_message("ai"):
        status_container = st.status("⏳", expanded=False)
        text_placeholder = st.empty()
        response = ""

        stream = Runner.run_streamed(agent, message, session=session)
        
        async for event in stream.stream_events():
            if event.type == "raw_response_event":
                update_status(status_container, event.data.type)

                if event.data.type == "response.output_text.delta":
                    response += event.data.delta
                    text_placeholder.write(response.replace("$", "\$"))
                # elif event.data.type == "response.completed":
                #     status_container.update(label=f"웹 검색: {event.data.response.output[0].action.query}", state="complete")    


prompt = st.chat_input(
    "Write a message for your assistant",
    accept_file=True,
    file_type=["txt", "pdf", "jpg", "jpeg", "png"],
    )

if prompt:

    for file in prompt.files:
        if file.type.startswith("text/"):
            with st.chat_message("ai"):
                with st.status("⏳ uploading file...") as status:
                    uploaded_file = client.files.create(
                        file=(file.name, file.getvalue()),
                        purpose="user_data",
                    )
                    status.update(label="⏳ Attaching file...")
                    client.vector_stores.files.create(
                        vector_store_id=VECTOR_STORE_ID,
                        file_id=uploaded_file.id
                    )
                    status.update(label="✅ File uploaded", state="complete")
        elif file.type.startwith("image/"):
            file_bytes = file.getvalue()
            base64_data = base64.b64encode(file_bytes).decode("utf-8")
            data_uri = f"data:{file.type};base64,{base64_data}"
            session.add_items(
                [
                    {
                        "role":"user",
                        "content": [
                            {
                                "type": "input_image",
                                "detail": "auto",
                                "image_url": data_uri,
                            }
                        ]
                    }
                ]
            )
            status.update(label="✅ Image uploaded", state="complete")


    if prompt.text:
        with st.chat_message("human"):
            st.write(prompt.text)
        asyncio.run(run_agent(prompt.text))

with st.sidebar:
    reset = st.button("Reset Memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
