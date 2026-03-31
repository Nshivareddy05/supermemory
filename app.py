import streamlit as st
import json
from memory_agent import LocalMemorySystem
import db
import utils

st.set_page_config(page_title="Onyx AI Memory", page_icon="🧠", layout="wide")

# Initialize the memory system only once
@st.cache_resource
def get_memory_system():
    return LocalMemorySystem(threshold=0.3)

system = get_memory_system()

# CSS for styling the memory badges
st.markdown("""
<style>
.badge-memory {
    background-color: #6366f1;
    color: white;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
    display: inline-block;
}
.badge-fact {
    background-color: #10b981;
    color: white;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: bold;
    display: inline-block;
}
</style>
""", unsafe_allow_html=True)

# Application State Initialization
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

# Sidebar Setup
with st.sidebar:
    st.title("Settings & Chats")
    
    # New Chat Button
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.current_session_id = db.create_session("New Chat")
        st.rerun()
        
    st.divider()
    
    # Previous Chats Section
    st.subheader("Previous Chats")
    sessions = db.get_all_sessions()
    
    if not sessions:
        st.caption("No previous chats.")
    else:
        for s in sessions:
            title = s["title"] if s["title"] else "Chat"
            # Highlight current session
            btn_type = "primary" if s["id"] == st.session_state.current_session_id else "secondary"
            if st.button(f"💬 {title}", key=f"session_{s['id']}", type=btn_type, use_container_width=True):
                st.session_state.current_session_id = s["id"]
                st.rerun()

    st.divider()

    # Facts Database Management
    st.subheader("Facts Engine")
    with st.expander("Manage Facts", expanded=False):
        fact_q = st.text_input("Question / Trigger:")
        fact_a = st.text_area("Answer / Fact:")
        if st.button("Add Fact", use_container_width=True):
            if fact_q and fact_a:
                system.add_fact(fact_q, fact_a)
                st.success("Fact added!")
            else:
                st.error("Please fill both fields.")
        
        st.markdown("---")
        st.markdown("**Stored Facts**")
        all_facts = system.get_all_facts()
        if not all_facts:
            st.caption("No facts yet.")
        else:
            for fact in all_facts:
                st.markdown(f"**Q:** {fact['question']}")
                st.markdown(f"**A:** {fact['answer']}")
                if st.button("Delete", key=f"del_{fact['id']}", help="Delete Fact"):
                    system.delete_fact(fact['id'])
                    st.rerun()
                st.markdown("---")

    st.divider()

    # Import / Export
    st.subheader("Data Portability")
    with st.expander("Import / Export", expanded=False):
        # Export
        data = utils.export_all_data(system)
        json_data = json.dumps(data)
        st.download_button("📩 Download Backup", data=json_data, file_name="onyx_memory_backup.json", mime="application/json", use_container_width=True)
        
        # Import
        uploaded_file = st.file_uploader("Upload Backup JSON", type=["json"])
        if uploaded_file is not None:
            if st.button("Upload & Merge"):
                try:
                    import_data = json.load(uploaded_file)
                    utils.import_all_data(system, import_data)
                    st.success("Data imported successfully!")
                    st.session_state.current_session_id = None # Reset view
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to import: {str(e)}")


# Main Chat Interface
if st.session_state.current_session_id is None:
    # Auto-create if none exists
    st.session_state.current_session_id = db.create_session("New Chat")

st.title("🧠 Onyx AI Memory System")
st.markdown("Persistent Chats • Facts Database • Semantic Caching")

# Fetch messages for current session
messages = db.get_messages(st.session_state.current_session_id)

# If new session, show welcome (temporarily without saving to db to avoid clutter)
if not messages:
    st.chat_message("assistant").markdown("Hello! I am your local AI memory system. I remember our chats and your specific facts. What's on your mind today?")

# Render history
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("source") == "fact":
            st.markdown('<div class="badge-fact">⚡ Retrieved from Facts Database</div>', unsafe_allow_html=True)
        elif message.get("source") == "memory":
            st.markdown('<div class="badge-memory">⚡ Retrieved from Memory Cache</div>', unsafe_allow_html=True)

# Handle user input
if prompt := st.chat_input("Type your message here..."):
    
    # Save user message to SQLite
    db.add_message(st.session_state.current_session_id, "user", prompt, source=None)

    # Rename session if it's the first message
    if len(messages) == 0:
        title = prompt[:30] + "..." if len(prompt) > 30 else prompt
        db.rename_session(st.session_state.current_session_id, title)
    
    # Render user prompt immediately
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            result = system.query(prompt)
        
        response = result["response"]
        source = result.get("source", "ollama")
        
        st.markdown(response)
        
        if source == "fact":
             st.markdown('<div class="badge-fact">⚡ Retrieved from Facts Database</div>', unsafe_allow_html=True)
        elif source == "memory":
             st.markdown('<div class="badge-memory">⚡ Retrieved from Memory Cache</div>', unsafe_allow_html=True)
            
        # Add assistant response to DB
        db.add_message(st.session_state.current_session_id, "assistant", response, source=source)
        st.rerun()
