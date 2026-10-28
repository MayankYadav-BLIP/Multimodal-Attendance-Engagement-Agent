# Multimodal Attendance & Engagement System

A Python-based web application designed to support attendance management and classroom engagement analysis using computer vision and multimodal data processing.

## Overview

The Multimodal Attendance & Engagement System combines face detection, face recognition, facial landmark analysis, and audio-based processing to assist with attendance tracking and engagement monitoring.

The application provides a web interface for managing attendance sessions and processing relevant visual and audio inputs. Its modular architecture makes it easier to maintain, test, and extend the system.

## Features

- **Face Detection:** Detects faces from visual input using computer vision models.
- **Face Recognition:** Supports face recognition for attendance-related workflows.
- **Facial Landmark Detection:** Processes facial landmarks for visual analysis.
- **Head-Pose Analysis:** Uses facial landmarks to support head-pose estimation.
- **Audio Processing:** Includes modules for audio-related analysis.
- **Engagement Analysis:** Supports analysis of visual and audio cues related to engagement.
- **Web Interface:** Provides a browser-based interface for interacting with the application.
- **Attendance Sessions:** Supports creating and saving attendance sessions.
- **Modular Architecture:** Separates application logic into Python modules for easier maintenance and development.

*Feature availability and analysis results depend on the implementation, input quality, and configured models.*

## Technology Stack

- **Programming Language:** Python
- **Web Framework:** Flask
- **Computer Vision:** OpenCV
- **Face Analysis:** MediaPipe and ONNX-based models
- **Frontend:** HTML, CSS, JavaScript
- **Data Storage:** SQLite, where configured
- **Development Environment:** Visual Studio Code
- **Version Control:** Git and GitHub

## Project Structure

```text
Multimodal-Attendance-Agent/
│
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── models/
│   ├── face_detector.tflite
│   ├── face_landmarker.task
│   ├── face_detector_yunet.onnx
│   └── face_recognizer_sface.onnx
│
├── modules/
│   ├── head_pose.py
│   ├── recognition.py
│   └── vision.py
│
├── static/
│   └── Frontend assets
│
├── templates/
│   └── HTML templates
│
├── test_audio.py
└── test_engagement.py
```

*Note: This structure shows the main files identified in the project. Additional files may exist inside the folders.*

## Installation and Setup

### Prerequisites

Install the following before running the application:

- Python 3.12
- Git
- Visual Studio Code (recommended)

### 1. Clone the Repository

After publishing the project to GitHub, run:

```bash
git clone https://github.com/MayankYadav-BLIP/Multimodal-Attendance-Engagement-Agent.git
cd Multimodal-Attendance-Engagement-Agent
```

### 2. Create a Virtual Environment

**Windows PowerShell:**

```powershell
py -3.12 -m venv .venv
```

### 3. Activate the Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, you can run the environment's Python executable directly instead.

### 4. Install Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Run the Application

```powershell
python app.py
```

Open the local address displayed in the terminal. For a typical Flask development server, this may be:

```text
http://127.0.0.1:5000
```

The exact address depends on the application's configuration.

## Testing

The project includes scripts for testing audio and engagement-related functionality:

```powershell
python test_audio.py
python test_engagement.py
```

Run these scripts from the project root after installing the required dependencies. Their successful execution depends on the configured models, available inputs, and implementation requirements.

## Potential Applications

- Classroom attendance assistance
- Educational engagement research
- Computer vision experimentation
- Multimodal data processing
- Academic projects and demonstrations

## Limitations

- Recognition accuracy may vary with lighting, camera quality, viewing angle, and occlusion.
- Audio analysis may be affected by background noise and recording quality.
- Engagement indicators are estimates and should not be treated as definitive measures of attention, understanding, or emotion.
- The application requires compatible dependencies and model files.
- Results should be reviewed before being used for consequential attendance or educational decisions.

## Future Enhancements

- Develop a dashboard for attendance statistics and engagement trends.
- Add downloadable attendance reports.
- Improve recognition performance under varied environmental conditions.
- Expand audio and visual analysis capabilities.
- Add role-based access control for administrators and instructors.
- Improve data privacy, consent management, and secure storage.
- Evaluate model performance using representative test data.

## Privacy and Responsible Use

This project may process facial images, audio, and attendance records. Use it only with appropriate consent and authorization.

- Avoid publishing real student records, facial images, or private audio recordings.
- Never commit API keys, passwords, or other secrets.
- Restrict access to collected data and remove it when no longer needed.
- Verify model licenses and applicable data-protection requirements before deployment.
- Treat engagement estimates as experimental indicators rather than definitive judgments about individuals.

## License

A license has not yet been specified for this project. Before distributing the project publicly, review the licenses and redistribution conditions of the code, dependencies, and model files, and choose an appropriate license for your own contributions.

## Author

**Project:** Multimodal Attendance & Engagement System

Developed as an academic and practical project exploring computer vision, audio processing, attendance management, and engagement analysis.
