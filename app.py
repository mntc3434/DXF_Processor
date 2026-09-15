import streamlit as st
from pathlib import Path
import time
.........................................
# Simple Page Config
st.set_page_config(page_title="SAMRI DXF", layout="wide")

# This must be at the top to ensure the UI renders immediately
st.title("🏗️ SAMRI: Structural DXF Processor")

# Lazy loading of heavy modules
def load_heavy_stuff():
    from processor import process, PRETRAINED_MODEL
    from sentence_transformers import SentenceTransformer
    return process, PRETRAINED_MODEL, SentenceTransformer

def main():
    st.info("AI-Powered Structural Detailing & Annotation")
    
    col1, col2 = st.columns([1, 2])

    with col1:
        st.write("### 📂 1. Upload Drawing")
        uploaded_file = st.file_uploader("Upload DXF", type=["dxf"])
        
        if uploaded_file:
            st.success(f"Uploaded: {uploaded_file.name}")
            
            if st.button("🚀 PROCESS DRAWING", type="primary"):
                with st.status("Initializing AI engine...") as status:
                    # Load modules inside the button click to keep UI fast
                    process_func, model_name, transformer_class = load_heavy_stuff()
                    
                    status.update(label=f"Loading AI Model ({model_name})...", state="running")
                    model = transformer_class(model_name)
                    
                    status.update(label="Analyzing DXF geometry...", state="running")
                    
                    # Save temp
                    temp_path = Path("temp") / uploaded_file.name
                    temp_path.parent.mkdir(exist_ok=True)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    report = process_func(str(temp_path), model_data=model)
                    
                    if report["success"]:
                        status.update(label="Processing complete!", state="complete")
                        st.session_state["report"] = report
                    else:
                        status.update(label="Error occurred", state="error")
                        st.error(report["error"])

    with col2:
        if "report" in st.session_state:
            res = st.session_state["report"]
            st.success(f"### ✅ Success: {uploaded_file.name}")
            
            # Metrics
            st.metric("AI Similarity", f"{res['similarity']:.2%}")
            st.metric("Added Entities", f"{res['added_entities']:,}")
            
            st.divider()
            
            # Download
            with open(res["output_path"], "rb") as f:
                st.download_button(
                    "📥 DOWNLOAD PROCESSED DXF",
                    f,
                    file_name=Path(res["output_path"]).name,
                    use_container_width=True
                )
        else:
            st.write("---")
            st.info("Upload a file on the left and click 'Process' to see results here.")

if __name__ == "__main__":
    main()
