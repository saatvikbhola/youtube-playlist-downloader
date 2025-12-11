import streamlit as st
import subprocess
import os
import tempfile
from dotenv import load_dotenv

# --- Page Configuration ---
st.set_page_config(
    page_title="Script Runner UI",
    page_icon="🚀",
    layout="wide"
)

# --- App Title and Description ---
st.title("🚀 YouTube Playlist Downloader Interface")
st.markdown("""
This application provides a web interface to run the `main_script.py` downloader. 
Enter your API key and the desired playlist ID, then click start. The console output 
from the script will be displayed below in real-time.
""")

# --- Streamlit UI ---
st.header("⚙️ Configuration")

# Load API key from .env file if it exists, otherwise allow user input
load_dotenv()
api_key_default = os.getenv("API_KEY", "")

api_key = st.text_input(
    "Enter your YouTube API Key", 
    value=api_key_default, 
    type="password",
    help="Your API key is used for the script execution and is not stored."
)
playlist_id = st.text_input(
    "Enter the YouTube Playlist ID", 
    value="PLthKFKAfnaj8D1u7TOUwtYZxbBob_egjV"
)

# --- Main Execution Logic ---
if st.button("▶️ Start Processing", use_container_width=True):
    if not api_key:
        st.error("Please provide a YouTube API Key.")
    elif not playlist_id:
        st.error("Please provide a YouTube Playlist ID.")
    elif not os.path.exists("main_script.py"):
        st.error("Error: `main_script.py` not found in the same directory.")
    else:
        st.info("Starting the download process... The log will appear below.")
        
        # Placeholder for the live log output
        log_placeholder = st.empty()
        log_output = ""

        try:
            # 1. Read the original script's content
            with open("main_script.py", "r") as f:
                script_content = f.read()

            # 2. Dynamically replace the placeholder playlist_id
            modified_content = script_content.replace(
                'playlist_id = ""', 
                f'playlist_id = "{playlist_id}"'
            )

            # 3. Create a temporary file to run
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding='utf-8') as temp_f:
                temp_script_path = temp_f.name
                temp_f.write(modified_content)

            # 4. Set up the environment for the subprocess
            script_env = os.environ.copy()
            script_env["API_KEY"] = api_key
            
            # 5. Run the temporary script as a subprocess
            # The "-u" flag is for unbuffered python output, crucial for live logs
            process = subprocess.Popen(
                ["python", "-u", temp_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Combine stderr and stdout
                text=True,
                env=script_env,
                encoding='utf-8',
                errors='replace'
            )

            # 6. Read and display output in real-time
            for line in iter(process.stdout.readline, ''):
                log_output += line
                log_placeholder.code(log_output, language='log')
            
            process.stdout.close()
            return_code = process.wait()

            if return_code == 0:
                st.success("Script finished successfully!")
            else:
                st.error(f"Script finished with an error (exit code: {return_code}). Check the log for details.")

        except Exception as e:
            st.error(f"An error occurred while trying to run the script: {e}")
        finally:
            # 7. Clean up the temporary file
            if 'temp_script_path' in locals() and os.path.exists(temp_script_path):
                os.remove(temp_script_path)

