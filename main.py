import dotenv
dotenv.load_dotenv()
import asyncio
import time
import streamlit as st
from agents import Agent, Runner, SQLiteSession, WebSearchTool

if "agent" not in st.session_state:
    st.session_state["agent"] = Agent(
        name="My Life Coach Agent",
        instructions = """
        너는 매우 휼륭한 라이프 코치야. 
        
        너는 아래의 툴에 접근할 수 있어.
        - Web Search Tool: 사용자가 동기부여 콘텐츠, 자기 개발 팁, 습관 형성 조언등을 물어볼 때, 먼저 Web 검색을 통해서 조언이나 해당 정보들을 찾아줘.
        """,
        tools=[WebSearchTool(),],
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

        if "type" in message and message["type"] == "web_search_call":
            with st.chat_message("ai"):
                st.write("🔍 Searching the web...")


def update_status(status_container, event):
    status_messages = {
        'response.web_search_call.completed': ("✅ Web search completed", "complete"),
        'response.web_search_call.in_progress': ("🔍 Starting web search...", "running"),
        'response.web_search_call.searching': ("🔍 Web search in progress...", "running"),
        # 'response.completed': (" ", "complete"),
    }

    if event in status_messages:
        label, state = status_messages[event]
        status_container.update(label=label, state=state)


asyncio.run(paint_history())


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
                    text_placeholder.write(response)
                elif event.data.type == "response.completed":
                    status_container.update(label=f"웹 검색: {event.data.response.output[0].action.query}", state="complete")    


prompt = st.chat_input("Write a message for your assistant")

if prompt:
    with st.chat_message("human"):
        st.write(prompt)
    asyncio.run(run_agent(prompt))

with st.sidebar:
    reset = st.button("Reset Memory")
    if reset:
        asyncio.run(session.clear_session())
    st.write(asyncio.run(session.get_items()))
