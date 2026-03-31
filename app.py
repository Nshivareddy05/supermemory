import streamlit as st
from memory_agent import LocalMemorySystem

st.set_page_config(page_title="Onyx AI Memory", page_icon="🧠", layout="centered")

# Initialize the memory system only once
@st.cache_resource
def get_memory_system():
    return LocalMemorySystem(threshold=0.3)

system = get_memory_system()

st.title("🧠 Onyx AI Memory System")
st.markdown("Powered by **Streamlit**, **Mistral** (via Ollama), **ChromaDB**, and **Sentence-Transformers**.")

# Custom CSS for styling the memory badge
st.markdown("""
<style>
.cache-badge {
    background-color: #6366f1;
    color: white;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Add welcome message
    st.session_state.messages.append({"role": "assistant", "content": "Hello! I am your local AI memory system. I remember everything we talk about. What's on your mind today?"})

# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("is_cached"):
            st.markdown('<div class="cache-badge">⚡ Retrieved from Memory</div>', unsafe_allow_html=True)

# React to user input
if prompt := st.chat_input("Type your message here..."):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            result = system.query(prompt)
        
        response = result["response"]
        is_cached = result["is_cached"]
        
        st.markdown(response)
        
        if is_cached:
            st.markdown('<div class="cache-badge">⚡ Retrieved from Memory</div>', unsafe_allow_html=True)
            
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response, "is_cached": is_cached})
