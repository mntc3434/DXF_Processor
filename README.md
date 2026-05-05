# SAMRI — Structural DXF Processor (AI Powered)

A premium Python-based tool for automated structural drawing annotations. It uses a **HuggingFace AI model** to intelligently add reinforcement (rebar), dimensions, and labels by matching against ground-truth references.

---

## 🎨 Features
- **Modern Web UI**: Easy-to-use interface for uploading and processing drawings.
- **AI Matching**: Automatically finds the most similar structural pattern using sentence embeddings.
- **Automated Output**: No need to specify output paths; the system handles it for you.
- **Detailed Analytics**: Real-time reports on similarity scores and layer additions.

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the UI (Recommended)
Launch the web-based dashboard to process files visually:
```bash
python -m streamlit run app.py
```

### 3. CLI Usage (Automated)
If you prefer the command line, simply provide the input file. The output will be automatically saved to the `result/` folder:
```bash
python processor.py "input/your_drawing.dxf"
```

---

## 📂 Project Structure
- `app.py`: The Streamlit web dashboard.
- `processor.py`: The AI processing engine.
- `input/`: Raw input DXF files.
- `output/`: Ground-truth reference files (Knowledge Base).
- `result/`: Automatically generated processed output.

---

## 🛠️ Requirements
- Python 3.9+
- `ezdxf`
- `sentence-transformers` (AI model)
- `streamlit` (UI)
- `numpy`
