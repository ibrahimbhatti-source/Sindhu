from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import requests 
import json
import os

load_dotenv()
BODHAN_API_KEY_FOR_STT=os.getenv("BODHAN_API_KEY")
GROQ_API_KEY=os.getenv("GROQ_API_KEY")
X_API_Key=os.getenv("X_API_Key")

# 1. Creating the FastAPI application
app = FastAPI()


# Register CORS middleware
# Middleware processes requests and responses.
# This particular middleware controls which browser origins can access our backend API.
app.add_middleware(
    CORSMiddleware,
    # Specify which frontend URLs are allowed. We allow both localhost and 127.0.0.1 on port 5500.

    # Allow these frontend server addresses
    allow_origins=["*"],
    # Allow GET and POST requests
    allow_methods=["POST","GET"],

    # Allow request headers from frontend this includes Content Type for audio uploads

    allow_headers=["*"],

    # We are not using browser cookies or credentialed cross-origin requests.

    allow_credentials=False
)

@app.get("/")
def read_index():
    return FileResponse("sindhu_orb_voice.html")

# 2. Creating the endpoint that receives audio

@app.post("/process_audio")
def generate_response(file: UploadFile = File(...)):

    # 3. Reading the audio uploaded by frontend
    input_audio = file.file.read()

    # 4. Get the uploaded audio format (audio/webm)
    # audio_format = file.content_type

    # 5. Pass the audio to the workflow
    def speech_to_text(audio):
        url="https://api.bodhan.ai/v1/audio/transcriptions"

        headers = {
            "Authorization": f"Bearer {BODHAN_API_KEY_FOR_STT.strip()}"
        }

        # giving requests the filename + audio bytes
        files = {"file":("audio.wav", audio)}

        data = {
            "model":"indic-transcribe",
            "language":"sd",
            "vad": True}

        response = requests.post(url=url,headers=headers, files=files, data=data)

        if response.status_code == 200:
            result = response.json()
            print(result)
            return result.get("text")
        else:
             raise HTTPException(
                 status_code=429,
                 detail=f"Voice service is busy. Please try again later. {response.json()}"
             )
                    
    def translate_STE(transcription):
        print(transcription)

        # providing transcription to indic translate for LLM answering 

        # Sending API Request to Indic Translate

        url="https://api.bodhan.ai/v1/chat/completions"

        headers = {
            "Authorization":f"Bearer {"sk-wEsOcLAvNIN3XabHOI49rw"}",

        }

        payload = {
            "model":"indic-translate",
            "messages": [{"role":"user",
                        "content":transcription}],
            "target_language_code":"en",
            "target_script":"native"
        }

        response = requests.post(url=url, headers=headers, json=payload)

        if response.status_code == 200:
            body = response.json()
            print(body["choices"][0]["message"]["content"])
            return body["choices"][0]["message"]["content"]
            
        else:
            raise HTTPException(
                 status_code=502,
                 detail=f"Someting went wrong in translating sindhi to english, Please try later."
             )

    def LLM(translated_text):
        parser = StrOutputParser()
        model = ChatGroq(model="openai/gpt-oss-120b",api_key=GROQ_API_KEY)
        prompt = PromptTemplate(template="""You are 'Sindhu', a helpful, warm, and conversational AI Voice Assistant. Your responses will be read aloud via text-to-speech, so write exactly as a real person speaks.

CONVERSATIONAL & LENGTH RULES:
1. Match the depth of the user's question:
   - For simple, factual, or identity questions (e.g., "What is your name?", "What time is it?"), reply in one short, natural sentence. (Example: "My name is Sindhu.")
   - For broad, open-ended, or complex questions (e.g., "What is the history of Sindh?"), give a clear, engaging summary in 3 to 4 conversational sentences.
2. Never use sentence fragments, bullet points, or robotic shorthand. Always speak in complete, flowing sentences.
3. Avoid symbols, abbreviations, or special characters (like ~, ≈, &, or e.g.) that sound awkward when read aloud. Write out words naturally (say "around five thousand years" instead of "≈5,000 years").
4. Keep your tone friendly, clear, and easy to follow without rambling.
{query}""", input_variables=["query"])

        chain = prompt | model | parser
        
        LLMresponse = chain.invoke({"query":translated_text})
        print(LLMresponse)
        return LLMresponse
    
    def translate_ETS(llm_response):

        # providing LLM response to indic translate to covert the text back to sindh 

        # Sending API Request to Indic Translate

        url="https://api.bodhan.ai/v1/chat/completions"

        headers = {
            "Authorization":f"Bearer {"sk-wEsOcLAvNIN3XabHOI49rw"}"
        }

        payload = {
            "model":"indic-translate",
            "messages": [{"role":"user",
                        "content":llm_response}],
            "target_language_code":"sd",
            "target_script":"native"
        }

        response = requests.post(url=url, headers=headers, json=payload)

        if response.status_code == 200:
            body = response.json()
            print(body["choices"][0]["message"]["content"])
            return body["choices"][0]["message"]["content"]
        else:
            raise HTTPException(
                 status_code=502,
                 detail=f"Someting went wrong in ETS phase, Please try later."
             )

    def text_to_speech(translated_text):

        text = translated_text
        url = "https://yourvoic.com/api/v1/tts/generate"

        payload = {
            "text":text,
            "voice":"Ramesh",
            "language":"sd",
            "model":"aura-prime",
            "speed":1,
            "pitch":1,
            "response_format":"mp3"
        }

        headers = {
            "X-API-Key":"yv_live_4f835e07e1f03cc1a750ff212a03b14fdf0152cf855ebfed",
            "Content-Type": "application/json"
        }

        response = requests.post(url=url, json=payload, headers=headers)

        if response.status_code == 200:
            # st.audio(response.content)
            return response.content
        else:
            raise HTTPException(
                 status_code=502,
                 detail=f"Someting went wrong in TSS, {response.content}"
             )

    chain = RunnableLambda(speech_to_text) | RunnableLambda(translate_STE) | RunnableLambda(LLM) | RunnableLambda(translate_ETS) | RunnableLambda(text_to_speech)

    # Passing the user speech to the first function of the chain (Speech to Text)
    finalresponse = chain.invoke(input_audio)

    # 6. Sending the generated audio back to frontend
    # The browser receives audio bytes, Not JSON
    return Response(
        content=finalresponse,
        media_type="audio/mpeg"
    )
