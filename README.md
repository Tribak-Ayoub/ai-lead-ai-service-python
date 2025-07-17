# AI Phone Lead Qualification Backend

This is the Python FastAPI microservice for AI-powered phone lead qualification, providing:

- Speech-to-Text (STT) using Faster-Whisper  
- Intent Detection using Google Gemini API  
- Text-to-Speech (TTS) using Piper  

---

## 🚀 Features

- Transcribe caller audio to text  
- Detect caller intent via AI  
- Generate spoken AI responses  
- Ready for integration with Asterisk telephony server  

---

## 📁 Project Structure

```

/ai-service-python/
│
├── app/
│   ├── main.py                # FastAPI app entrypoint
│   ├── routers/               # API route handlers
│   ├── services/              # AI model logic (STT, TTS, intent)
│   ├── models/                # Request/response schemas
│   └── core/                  # Config and logging (optional)
├── test\_data/                 # Sample audio files for testing
├── .env.example               # Environment variables template
├── requirements.txt           # Python dependencies
├── run.sh                    # Script to start server
└── README.md                  # This file

````

---

## ⚙️ Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Tribak-Ayoub/ai-lead-ai-service-python.git
   cd ai-lead-ai-service-python
````

2. Create and activate a Python virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env` and fill in your API keys and settings:

   ```bash
   cp .env.example .env
   # Then edit .env with your GEMINI_API_KEY etc.
   ```

---

## 🏃 Running the Server

Start the FastAPI server with hot reload (development mode):

```bash
./run.sh
```

The API will be available at:

```
http://localhost:8000
```

---

## 🛠 API Endpoints

### 1. Speech-to-Text (STT)

* **POST** `/stt/transcribe`
* Upload an audio file, receive the transcribed text.

### 2. Intent Detection

* **POST** `/intent`
* Send transcribed text, receive the detected intent JSON.

### 3. Text-to-Speech (TTS)

* **POST** `/tts/speak`
* Send text, receive audio (WAV/MP3) response.

---

## 🤝 Contributing

Feel free to open issues or pull requests!

---

## ⚠️ Security

* Do **not** commit your `.env` file with API keys.
* Use `.env.example` as a template for others.

---

## 📄 License

This project is licensed under the MIT License.

