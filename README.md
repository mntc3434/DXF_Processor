# DXF Structural Drawing Processor

A Python-based tool designed to automate structural drawing enhancements, including reinforcement annotations, auto-dimensioning, and labeling for DXF files.

## 🚀 Overview

This tool reads an input DXF file (structural skeleton), detects the geometry bounds, and adds:
- **Reinforcement (Rebar)**: Annotations on the `IRON` layer.
- **Dimensions**: Automatic linear dimensions on all sides of the structure in the `DIM` layer.
- **Labels**: Structural titles and references in the `TXT` layer.
- **Layer Management**: Automatically sets up standard layers with specific colors.

## 🚀 Quick Start (Running the Code)

If you are a new user, follow these steps to run the code immediately:

1. **Open your Terminal** (Command Prompt or PowerShell).
2. **Navigate to the project folder**:
   ```bash
   cd d:\samri_project
   ```
3. **Install the requirements**:
   ```bash
   pip install ezdxf
   ```
4. **Run the processor on all input files**:
   ```bash
   python dfx_pro.py input test_result
   ```
5. **View your results**: Open the `test_result` folder to see the processed DXF files.

---

## 🛠️ Installation

1. **Python**: Ensure you have Python 3.7+ installed.
2. **Dependencies**: Install the required library using pip:
   ```bash
   pip install ezdxf
   ```

## 📂 Project Structure

- `dfx_pro.py`: The core processing engine.
- `evaluate_results.py`: Automated testing and comparison suite.
- `input/`: Place your raw DXF files here.
- `output/`: Contains the ground truth files (True results) for comparison.
- `test_result/`: Where the script saves its processed output.
- `evaluation_report.txt`: A summary report of the latest evaluation run.

## 📖 Usage

### 1. Process a Single File
To process one drawing and save it to a specific location:
```bash
python dfx_pro.py input/your_drawing.dxf test_result/output_drawing.dxf
```

### 2. Batch Process a Folder
To process all DXF files in a folder:
```bash
python dfx_pro.py input test_result
```

### 3. Run Full Evaluation
To process all files and compare them against the ground truth in the `output` folder:
```bash
python evaluate_results.py
```
This will generate `evaluation_report.txt` with detailed match statistics.

## 📊 Evaluation Logic

The evaluation script compares the **Test Result** against the **Ground Truth** using three metrics:
1. **Layer Presence**: Checks if the required structural layers exist.
2. **Entity Counts**: Compares the number of entities in each layer (e.g., matching the number of dimensions).
3. **Accuracy**: Reports percentage differences to help fine-tune the processor's accuracy.

## ⚙️ Calibration

The processor is calibrated to the following standards:
- **Text Height**: 10 units.
- **Layer Colors**: Red (Rebar), Yellow (Dimensions), Cyan (Labels).
- **Diameter Symbol**: Uses `%%c` (standard AutoCAD format).
