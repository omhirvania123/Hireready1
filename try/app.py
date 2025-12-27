from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import uuid
from datetime import datetime
import torch
from omegaconf import OmegaConf
import urllib.request
import sounddevice as sd
import pyttsx3

# AssemblyAI imports
import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    StreamingSessionParameters,
    TerminationEvent,
    TurnEvent,
)
import logging
from typing import Type
import threading
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Please set GEMINI_API_KEY in your .env file")

genai.configure(api_key=GEMINI_API_KEY)

# Configure AssemblyAI
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY', '8be40cb90d054beeb10bd8ca8ce00b0e')
aai.settings.api_key = ASSEMBLYAI_API_KEY

# Use the available models from your test
GEMINI_MODELS = [
    'models/gemini-2.0-flash',  # Fast and reliable
    'models/gemini-2.0-flash-001',
    'models/gemini-flash-latest',  # Always points to latest flash
    'models/gemini-pro-latest',    # Always points to latest pro
    'models/gemini-2.0-flash-lite',
    'models/gemini-2.5-flash'
]

# Interview configuration - No fixed question limit
INTERVIEW_CONFIG = {
    "position": "Software Engineer",
    "duration": "flexible",
    "difficulty": "intermediate"
}

# Enhanced System prompt for the AI interviewer
SYSTEM_PROMPT = f"""
You are an expert technical interviewer conducting an interview for a {INTERVIEW_CONFIG['position']} position. 

CRITICAL GUIDELINES:
1. ALWAYS start with asking for the candidate's introduction and which role they have applied for
2. There is NO fixed number of questions - continue until the candidate asks to stop
3. Each question should build upon the previous responses - make it conversational and contextual
4. After the introduction question, ask technical questions based on:
   - Their mentioned skills and experience
   - The role they applied for
   - Their previous answers
5. Ask one question at a time and wait for their response
6. Provide brief, constructive feedback after each answer (1-2 sentences only)
7. Questions should be {INTERVIEW_CONFIG['difficulty']} level and CONCISE
8. Cover topics like: programming concepts, algorithms, data structures, system design, problem-solving
9. Make the interview flow naturally like a real conversation
10. When the candidate says they want to stop or end the interview, provide brief overall feedback
11. KEEP QUESTIONS AND FEEDBACK BRIEF AND TO THE POINT - maximum 2 sentences each
12. Avoid long explanations and detailed examples

Remember: Always personalize questions based on what the candidate has told you about themselves.
The interview continues until the candidate explicitly asks to stop.
"""

# Initialize TTS models
print("🔄 Initializing TTS models...")
url = "https://raw.githubusercontent.com/snakers4/silero-models/master/models.yml"
urllib.request.urlretrieve(url, "latest_silero_models.yml")

models = OmegaConf.load("latest_silero_models.yml")

language = "en"
model_id = "v3_en"
device = torch.device("cpu")

model, _ = torch.hub.load(
    repo_or_dir="snakers4/silero-models",
    model="silero_tts",
    language=language,
    speaker=model_id,
)
model.to(device)

engine = pyttsx3.init()

# AssemblyAI Streaming Variables
is_streaming = False
stream_lock = threading.Lock()
stop_event = threading.Event()
client_instance = None
transcribed_text = ""
transcription_complete = False
last_audio_time = 0

# ========== INTERVIEW SESSION CLASS ==========

class InterviewSession:
    def __init__(self, session_id, interview_data=None):
        self.session_id = session_id
        self.conversation_history = []
        self.question_count = 0
        self.start_time = datetime.now()
        self.is_completed = False
        
        # Store interview metadata from form
        self.interview_data = interview_data or {}
        self.role = self.interview_data.get('role', 'Software Engineer')
        self.level = self.interview_data.get('level', 'intermediate')
        self.techstack = self.interview_data.get('techstack', [])
        self.interview_type = self.interview_data.get('type', 'Technical')
        self.questions = self.interview_data.get('questions', [])
        
        self.candidate_info = {
            'applied_role': self.role,  # Pre-fill with form data
            'introduction': '',
            'skills_mentioned': list(self.techstack) if isinstance(self.techstack, list) else [],
            'experience_level': self.level,
            'communication_score': 0,
            'technical_score': 0,
            'key_strengths': [],
            'areas_for_improvement': []
        }
        self.all_questions_answers = []  # Store all Q&A for feedback
        self.topic_coverage = {
            'algorithms': 0,
            'data_structures': 0,
            'system_design': 0,
            'coding': 0,
            'problem_solving': 0,
            'technical_concepts': 0
        }
        
        # Generate system prompt with interview data
        system_prompt = self._generate_system_prompt()
        self.add_message("system", system_prompt)
    
    def _generate_system_prompt(self):
        """Generate system prompt based on interview metadata"""
        techstack_str = ", ".join(self.techstack) if isinstance(self.techstack, list) else str(self.techstack)
        
        # Build questions context - CRITICAL for question scope
        questions_context = ""
        if self.questions and len(self.questions) > 0:
            questions_list = "\n".join([f"{i+1}. {q}" for i, q in enumerate(self.questions)])
            questions_context = f"""

═══════════════════════════════════════════════════════════════
PREPARED QUESTIONS FOR THIS INTERVIEW (MANDATORY SCOPE):
═══════════════════════════════════════════════════════════════
You have {len(self.questions)} prepared questions. You MUST ask questions ONLY from this list or variations/clarifications based on these questions.

{questions_list}

CRITICAL: All your questions MUST be directly related to these {len(self.questions)} prepared questions. You can:
- Ask these questions in natural conversation flow
- Adapt them based on candidate's previous answers
- Ask follow-up questions related to these topics
- BUT NEVER ask questions outside this scope or unrelated topics
═══════════════════════════════════════════════════════════════
"""
        else:
            questions_context = f"""

═══════════════════════════════════════════════════════════════
QUESTION SCOPE - NO PREPARED QUESTIONS PROVIDED
═══════════════════════════════════════════════════════════════
Since no specific questions were provided, you must generate questions STRICTLY based on:
- Position: {self.role}
- Level: {self.level}
- Technologies: {techstack_str}
- Type: {self.interview_type}

ALL questions MUST be relevant to these specific criteria above.
═══════════════════════════════════════════════════════════════
"""
        
        return f"""
You are an expert technical interviewer conducting an interview for a {self.role} position at {self.level} level. 

═══════════════════════════════════════════════════════════════
INTERVIEW CARD DETAILS (MANDATORY SCOPE - DO NOT DEVIATE):
═══════════════════════════════════════════════════════════════
- Position/Role: {self.role}
- Experience Level: {self.level}
- Required Technologies: {techstack_str}
- Interview Type: {self.interview_type}
{questions_context}

CRITICAL QUESTION SCOPE RULES:
1. ALL questions MUST be based ONLY on the interview card details above
2. Questions MUST relate to: {self.role} position, {self.level} level concepts, {techstack_str} technologies
3. Interview type focus: {self.interview_type} questions
4. DO NOT ask questions outside this scope
5. DO NOT ask about unrelated technologies, roles, or topics
6. Every question must align with at least one of: role, level, technology, or prepared questions
═══════════════════════════════════════════════════════════════

INTERVIEW FLOW GUIDELINES:
1. START with asking the candidate to introduce themselves (name, background, experience)
2. DO NOT ask about the role, level, or technologies - these are already known from the form
3. After introduction, proceed directly to ask questions STRICTLY from the interview card scope above
4. There is NO fixed number of questions - continue until the candidate asks to stop
5. Each question should build upon the previous responses - make it conversational and contextual
6. Ask one question at a time and wait for their response
7. Provide brief, constructive feedback after each answer (1-2 sentences only)
8. Questions should be {self.level} level and CONCISE
9. Make the interview flow naturally like a real conversation
10. When the candidate says they want to stop or end the interview, provide brief overall feedback
11. KEEP QUESTIONS AND FEEDBACK BRIEF AND TO THE POINT - maximum 2 sentences each
12. Avoid long explanations and detailed examples

ANTI-REPETITION RULES (CRITICAL):
- NEVER repeat or echo back the candidate's response
- NEVER repeat your previous question
- NEVER summarize what they said unless absolutely necessary for context
- Simply acknowledge briefly (1 sentence) and move to the next question
- Your responses should ONLY contain: brief feedback + new question (2-3 sentences total)
- Do NOT say things like "You mentioned..." or "Based on your answer about..." - just respond naturally

Remember: The candidate has already scheduled this interview with these specific requirements. 
ALL questions must be within the scope of: {self.role} role, {self.level} level, {techstack_str} technologies, and {self.interview_type} focus.
DO NOT deviate from this scope.
"""
        
    def add_message(self, role, content):
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def extract_candidate_info(self, response):
        """Extract candidate information from their responses"""
        response_lower = response.lower()
        
        # Extract role information
        if "applied for" in response_lower or "role" in response_lower:
            self.candidate_info['applied_role'] = response
        
        # Extract introduction and experience
        if "introduction" in response_lower or "name" in response_lower or "experience" in response_lower:
            self.candidate_info['introduction'] = response
            
            # Extract experience level
            experience_indicators = {
                'junior': ['junior', 'entry level', 'fresh graduate', '0-2 years', 'starting my career'],
                'mid-level': ['mid level', 'intermediate', '2-5 years', '3-5 years', 'few years of experience'],
                'senior': ['senior', 'lead', '5+ years', 'extensive experience', 'many years']
            }
            
            for level, indicators in experience_indicators.items():
                if any(indicator in response_lower for indicator in indicators):
                    self.candidate_info['experience_level'] = level
                    break
        
        # Extract technical skills
        tech_skills = [
            'python', 'java', 'javascript', 'typescript', 'react', 'node', 'angular', 'vue',
            'aws', 'azure', 'docker', 'kubernetes', 'sql', 'nosql', 'mongodb', 'redis',
            'rest', 'graphql', 'ci/cd', 'git', 'agile', 'scrum', 'machine learning',
            'data structures', 'algorithms', 'system design', 'microservices'
        ]
        
        found_skills = [skill for skill in tech_skills if skill in response_lower]
        if found_skills:
            self.candidate_info['skills_mentioned'].extend(found_skills)
            self.candidate_info['skills_mentioned'] = list(set(self.candidate_info['skills_mentioned']))
    
    def add_qa_pair(self, question, answer):
        """Store question-answer pair for feedback"""
        self.all_questions_answers.append({
            'question': question,
            'answer': answer,
            'timestamp': datetime.now().isoformat()
        })

# Store active interview sessions
interview_sessions = {}

# ========== ASSEMBLYAI EVENT HANDLERS ==========

def on_begin(self: Type[StreamingClient], event: BeginEvent):
    print(f"Session started: {event.id}")

def on_turn(self: Type[StreamingClient], event: TurnEvent):
    global transcribed_text, transcription_complete, last_audio_time
    
    # Update last audio time whenever we get any transcript
    last_audio_time = time.time()
    
    # Skip empty transcripts
    if event.transcript.strip():
        print(f"Transcribed: {event.transcript} ({event.end_of_turn})")
        transcribed_text = event.transcript

    if event.end_of_turn and not event.turn_is_formatted:
        params = StreamingSessionParameters(
            format_turns=True,
        )
        self.set_params(params)
    
    # Mark transcription as complete when we have a full turn
    if event.end_of_turn and event.transcript.strip():
        transcription_complete = True

def on_terminated(self: Type[StreamingClient], event: TerminationEvent):
    print(f"Session terminated: {event.audio_duration_seconds} seconds of audio processed")

def on_error(self: Type[StreamingClient], error: StreamingError):
    print(f"Error occurred: {error}")

class ControlledMicrophoneStream:
    """Wrapper for MicrophoneStream with start/stop control"""
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.mic_stream = None
        
    def __iter__(self):
        self.mic_stream = aai.extras.MicrophoneStream(sample_rate=self.sample_rate)
        return self
    
    def __next__(self):
        global is_streaming, last_audio_time
        
        # Check if we should stop
        if stop_event.is_set():
            if self.mic_stream:
                try:
                    self.mic_stream.close()
                except:
                    pass
            raise StopIteration
        
        with stream_lock:
            if not is_streaming:
                if self.mic_stream:
                    try:
                        self.mic_stream.close()
                    except:
                        pass
                raise StopIteration
        
        # Get next audio chunk
        try:
            # Update last audio time when we get audio data
            chunk = next(self.mic_stream)
            last_audio_time = time.time()
            return chunk
        except StopIteration:
            raise

# ========== UTILITY FUNCTIONS ==========

def find_working_model():
    """Find a working Gemini model from the available list"""
    print("🔍 Searching for working model...")
    
    for model_name in GEMINI_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            # Test with a simple prompt
            response = model.generate_content("Say 'Hello' in one word.")
            if response.text:
                print(f"✅ Successfully connected to model: {model_name}")
                return model_name
        except Exception as e:
            print(f"❌ Model {model_name} failed: {e}")
            continue
    
    # If no predefined model works, try to find any available model
    try:
        models = genai.list_models()
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                try:
                    test_model = genai.GenerativeModel(model.name)
                    response = test_model.generate_content("Test")
                    if response.text:
                        print(f"✅ Successfully connected to available model: {model.name}")
                        return model.name
                except:
                    continue
    except Exception as e:
        print(f"Error searching for models: {e}")
    
    return None

# Find and set the working model
WORKING_MODEL = find_working_model()
if not WORKING_MODEL:
    raise Exception("No working Gemini model found. Please check your API key and region.")

print(f"🎯 Using model: {WORKING_MODEL}")

def generate_overall_feedback(conversation_history, candidate_info, qa_pairs):
    """Generate brief comprehensive feedback after interview ends"""
    try:
        model = genai.GenerativeModel(WORKING_MODEL)
        
        # Prepare conversation summary for feedback
        qa_summary = "\n".join([f"Q: {qa['question']}\nA: {qa['answer']}\n" for qa in qa_pairs])
        
        feedback_prompt = f"""
As an expert technical interviewer, analyze the following interview and provide comprehensive feedback. Be objective and balanced in your assessment.

Candidate Information:
{json.dumps(candidate_info, indent=2)}

Interview Conversation Summary:
{qa_summary}

Please provide structured feedback in the following format:

1. Technical Proficiency (Score /100):
- Knowledge of core concepts
- Problem-solving capability
- Code/system design understanding

2. Communication & Soft Skills (Score /100):
- Clarity of explanations
- Question understanding
- Professional interaction

3. Overall Assessment:
- Top 3 Strengths
- Top 3 Areas for Improvement
- Final Recommendation

Remember:
- Be specific with examples from their answers
- Balance constructive criticism with positive feedback
- Focus on actionable improvements
- Keep the feedback professional and objective
- Overall length should not exceed 200 words

Format the response as a clear, well-structured assessment that would be valuable for both the candidate and hiring team.
"""

        response = model.generate_content(feedback_prompt)
        return response.text.strip() if response.text else "Thank you for your time. We appreciate your participation in this interview."
    
    except Exception as e:
        print(f"Feedback generation error: {e}")
        return "Thank you for completing the interview. Your responses have been recorded and will be reviewed by our team."

def generate_ai_response(conversation_history, is_final_feedback=False, interview_session=None):
    """Generate response using Gemini API with contextual awareness"""
    try:
        # Create model with working model name
        model = genai.GenerativeModel(WORKING_MODEL)
        
        # Extract conversation context without full repetition
        # Get key topics mentioned but not full responses
        topic_summary = ""
        last_user_msg = None
        
        # Find last user message (candidate's response)
        for msg in reversed(conversation_history):
            if msg['role'] == 'user':
                last_user_msg = msg['content']
                break
        
        # Build topic summary from conversation (without full text)
        topics_mentioned = []
        for msg in conversation_history:
            if msg['role'] == 'user' and msg['content']:
                # Extract key topics/technologies mentioned (simple approach)
                content_lower = msg['content'].lower()
                if any(word in content_lower for word in ['react', 'node', 'python', 'javascript', 'java', 'sql', 'database']):
                    topics_mentioned.append("technical experience")
                if 'experience' in content_lower or 'worked' in content_lower:
                    topics_mentioned.append("work experience")
        
        topic_summary = ", ".join(set(topics_mentioned[:3])) if topics_mentioned else "general background"
        
        if is_final_feedback:
            # Generate farewell message when interview ends
            prompt = "The candidate has decided to end the interview. Please provide a brief polite closing message thanking them for their time. Keep it to one sentence. Do NOT repeat any previous conversation."
            response = model.generate_content(prompt)
        else:
            # Build enhanced prompt with role context and question scope
            role_context = ""
            question_scope = ""
            
            if interview_session:
                techstack_str = ", ".join(interview_session.techstack) if isinstance(interview_session.techstack, list) else str(interview_session.techstack)
                role_context = f"\n\nINTERVIEW CARD SCOPE (MANDATORY):\n- Role: {interview_session.role}\n- Level: {interview_session.level}\n- Technologies: {techstack_str}\n- Type: {interview_session.interview_type}"
                
                # Add question scope reminder
                if interview_session.questions and len(interview_session.questions) > 0:
                    question_scope = f"\n\nQUESTION SCOPE: You have {len(interview_session.questions)} prepared questions. Your next question MUST be:\n- From the prepared questions list, OR\n- A follow-up/clarification related to those questions, OR\n- Related to {interview_session.role} role, {interview_session.level} level, and {techstack_str} technologies\n\nDO NOT ask questions outside this scope!"
                else:
                    question_scope = f"\n\nQUESTION SCOPE: Your next question MUST be related to:\n- {interview_session.role} position\n- {interview_session.level} level concepts\n- {techstack_str} technologies\n- {interview_session.interview_type} interview focus\n\nDO NOT ask questions outside this scope!"
            
            # Build prompt that provides context but prevents repetition
            if last_user_msg:
                # Check if this is the first response after introduction/confirmation
                # Count how many exchanges have happened
                user_responses = [msg for msg in conversation_history if msg['role'] == 'user']
                is_after_confirmation = len(user_responses) == 1
                
                if is_after_confirmation:
                    # This is after introduction and confirmation - acknowledge and start technical questions
                    prompt = f"""You are conducting a technical interview. The candidate has just introduced themselves and confirmed the interview details (role, level, tech stack, number of questions).

{role_context}{question_scope}

IMPORTANT: They have confirmed the interview details. Now start asking TECHNICAL questions based on the interview card scope above.

Your response should:
1. Briefly acknowledge their introduction and confirmation (1 sentence)
2. Ask your FIRST technical question based on the interview card scope
3. Maximum 2-3 sentences total
4. Question MUST be within the scope: {interview_session.role if interview_session else 'role'}, {interview_session.level if interview_session else 'level'}, and technologies listed above

Start with your first technical question now:"""
                else:
                    # Regular follow-up question
                    prompt = f"""You are conducting a technical interview. The candidate just responded to your question.

{role_context}{question_scope}

CRITICAL ANTI-REPETITION RULES:
1. NEVER repeat what the candidate just said - assume you already know their answer
2. NEVER echo back phrases like "you mentioned..." or "based on your answer..."
3. NEVER repeat your previous question
4. Simply acknowledge briefly (1 short sentence) and ask the NEXT new question
5. Maximum 2-3 sentences total: brief acknowledgment + new question
6. Keep it natural and forward-moving
7. REMEMBER: Next question MUST be within the interview card scope above

GOOD example: "Good point. What's your approach to testing this?"
BAD example: "Based on your answer about React hooks, you mentioned useState. Tell me about React hooks..." (DON'T DO THIS)

Now respond with brief acknowledgment and next question (must be within scope):"""
            else:
                # This shouldn't happen, but fallback
                prompt = f"""You are conducting a technical interview. The candidate has just introduced themselves.

{role_context}{question_scope}

Ask your first technical question. The question MUST be:
- Within the interview card scope listed above
- Related to {interview_session.role if interview_session else 'the position'} role
- Appropriate for {interview_session.level if interview_session else 'the'} level
- Keep it to 1-2 sentences
- Do NOT repeat what they said in their introduction
- Do NOT ask questions outside the scope"""

            response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        else:
            return "Thank you for that response. Let me ask you another question based on what you've shared."
    
    except Exception as e:
        print(f"Gemini API Error: {str(e)}")
        # Contextual fallback responses
        fallback_responses = [
            "Thank you for sharing that. What would you say is the most challenging aspect?",
            "I appreciate your response. Could you elaborate briefly?",
            "That's interesting. What factors would you consider?",
        ]
        import random
        return random.choice(fallback_responses)

def should_end_interview(user_input):
    """Check if user wants to end the interview"""
    end_phrases = [
        "end interview",
        "stop interview",
        "finish interview",
        "conclude interview",
        "that's all",
        "i'm done",
        "let's end",
        "let's stop",
        "can we stop",
        "can we end",
        "wrap up",
        "finish up",
        "no more",
        "thank you that's it",
        "we can stop here",
        "end the session"
    ]
    user_input_lower = user_input.lower()
    return any(phrase in user_input_lower for phrase in end_phrases)

# ========== ASSEMBLYAI SPEECH FUNCTIONS ==========

def monitor_silence_timeout(timeout_seconds=5):
    """Monitor for silence timeout and stop STT if no audio detected"""
    global is_streaming, last_audio_time
    
    start_time = time.time()
    last_audio_time = start_time
    
    while is_streaming and not stop_event.is_set():
        current_time = time.time()
        silence_duration = current_time - last_audio_time
        
        # Check if we've exceeded the silence timeout
        if silence_duration >= timeout_seconds:
            print(f"🕒 No speech detected for {timeout_seconds} seconds. Auto-stopping STT.")
            stop_speech_recognition_internal()
            break
        
        # Check if total session time exceeds a reasonable limit (30 seconds)
        total_duration = current_time - start_time
        if total_duration >= 30:  # Maximum 30 seconds per STT session
            print("🕒 Maximum STT session time reached (30 seconds). Auto-stopping.")
            stop_speech_recognition_internal()
            break
        
        time.sleep(0.1)  # Check every 100ms

def stop_speech_recognition_internal():
    """Internal function to stop speech recognition"""
    global is_streaming, stop_event, client_instance
    
    print("🛑 Auto-stopping speech recognition...")
    
    with stream_lock:
        is_streaming = False
    
    stop_event.set()
    
    # Force disconnect immediately
    if client_instance:
        try:
            client_instance.disconnect(terminate=True)
        except:
            pass

def start_speech_recognition():
    """Start AssemblyAI speech recognition and return transcribed text"""
    global is_streaming, stop_event, client_instance, transcribed_text, transcription_complete, last_audio_time
    
    # Reset variables
    transcribed_text = ""
    transcription_complete = False
    stop_event.clear()
    last_audio_time = time.time()
    
    with stream_lock:
        is_streaming = True
    
    print("\n[Starting AssemblyAI speech recognition...]")
    print("⏰ STT will auto-stop after 5 seconds of silence")
    
    # Start silence monitoring in a separate thread
    timeout_monitor_thread = threading.Thread(target=monitor_silence_timeout, args=(5,), daemon=True)
    timeout_monitor_thread.start()
    
    client = StreamingClient(
        StreamingClientOptions(
            api_key=ASSEMBLYAI_API_KEY,
            api_host="streaming.assemblyai.com",
        )
    )
    
    client_instance = client

    client.on(StreamingEvents.Begin, on_begin)
    client.on(StreamingEvents.Turn, on_turn)
    client.on(StreamingEvents.Termination, on_terminated)
    client.on(StreamingEvents.Error, on_error)

    client.connect(
        StreamingParameters(
            sample_rate=16000,
            format_turns=True
        )
    )

    try:
        # Use the controlled microphone stream
        controlled_stream = ControlledMicrophoneStream(sample_rate=16000)
        client.stream(controlled_stream)
            
    except Exception as e:
        if not stop_event.is_set():  # Only print error if not intentionally stopped
            print(f"\n[Error during streaming: {e}]")
    finally:
        # Small delay to ensure everything is processed
        time.sleep(0.1)
        
        try:
            if not stop_event.is_set():
                client.disconnect(terminate=True)
        except:
            pass
        
        print("\n[Speech recognition session ended]")
    
    # Reset flags
    with stream_lock:
        is_streaming = False
    stop_event.clear()
    client_instance = None
    
    return transcribed_text

# ========== FLASK ROUTES ==========

@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "Hello from Silero TTS")
    speaker = data.get("speaker", "en_10")
    sample_rate = 24000

    # Generate audio
    audio = model.apply_tts(
        text=text,
        speaker=speaker,
        sample_rate=sample_rate,
        put_accent=True,
        put_yo=True,
    )

    # Play audio automatically
    sd.play(audio, sample_rate)
    sd.wait()

    return jsonify({"status": "ok", "text": text, "speaker": speaker})

@app.route("/stt", methods=["GET"])
def stt():
    """Speech-to-text using AssemblyAI streaming with auto-stop on silence"""
    try:
        print("🎤 Starting speech recognition... (Speak now)")
        print("⏰ Will auto-stop after 5 seconds of silence")
        
        transcribed_text = start_speech_recognition()
        
        if transcribed_text:
            print(f"✅ Transcribed: {transcribed_text}")
            return jsonify({"status": "ok", "transcription": transcribed_text})
        else:
            return jsonify({"status": "error", "message": "No speech detected"})
            
    except Exception as e:
        print(f"STT Error: {str(e)}")
        return jsonify({"status": "error", "message": f"Speech recognition error: {str(e)}"})

@app.route("/stt/stop", methods=["POST"])
def stop_stt():
    """Stop ongoing speech recognition"""
    global is_streaming, stop_event, client_instance
    
    print("🛑 Stopping speech recognition...")
    
    with stream_lock:
        is_streaming = False
    
    stop_event.set()
    
    # Force disconnect immediately
    if client_instance:
        try:
            client_instance.disconnect(terminate=True)
        except:
            pass
    
    return jsonify({"status": "ok", "message": "Speech recognition stopped"})

@app.route('/api/start-interview', methods=['POST'])
def start_interview():
    """Start a new interview session"""
    try:
        print("🚀 Starting new interview session...")
        
        # Get interview data from request (if provided)
        data = request.get_json() or {}
        interview_data = {
            'role': data.get('role', 'Software Engineer'),
            'level': data.get('level', 'intermediate'),
            'techstack': data.get('techstack', []),
            'type': data.get('type', 'Technical'),
            'questions': data.get('questions', [])
        }
        
        print(f"📋 Interview data: Role={interview_data['role']}, Level={interview_data['level']}, Tech={interview_data['techstack']}")
        
        session_id = str(uuid.uuid4())
        interview_session = InterviewSession(session_id, interview_data)
        interview_sessions[session_id] = interview_session
        
        # Generate initial greeting asking for introduction
        initial_response = generate_initial_greeting(interview_session)
        interview_session.add_message("assistant", initial_response)
        interview_session.question_count += 1
        
        print(f"✅ Interview session started: {session_id}")
        print(f"📝 First question: {initial_response}")
        
        return jsonify({
            'session_id': session_id,
            'message': initial_response,
            'question_number': interview_session.question_count,
            'status': 'started',
            'has_question_limit': False
        })
    
    except Exception as e:
        print(f"❌ Error starting interview: {str(e)}")
        return jsonify({'error': f'Failed to start interview: {str(e)}'}), 500

def generate_initial_greeting(interview_session):
    """Generate initial greeting asking for introduction and confirmation of interview details"""
    try:
        role = interview_session.role
        level = interview_session.level
        techstack_str = ", ".join(interview_session.techstack) if isinstance(interview_session.techstack, list) else str(interview_session.techstack)
        interview_type = interview_session.interview_type
        num_questions = len(interview_session.questions) if interview_session.questions else 0
        
        # Generate greeting asking for introduction AND confirmation
        greeting = f"""Hello! Welcome to your interview. To get started, could you please:
1. Introduce yourself - tell me your name, your background, and any relevant experience
2. Confirm the interview details: the role ({role}), difficulty level ({level}), tech stack ({techstack_str}), and number of questions ({num_questions} questions)

Please share your introduction and confirm these details."""
        
        return greeting
    
    except Exception as e:
        print(f"Error generating initial greeting: {str(e)}")
        role = interview_session.role
        level = interview_session.level
        techstack_str = ", ".join(interview_session.techstack) if isinstance(interview_session.techstack, list) else str(interview_session.techstack)
        num_questions = len(interview_session.questions) if interview_session.questions else 0
        return f"""Hello! Welcome to your interview. To get started, could you please:
1. Introduce yourself - tell me your name, your background, and any relevant experience
2. Confirm the interview details: the role ({role}), difficulty level ({level}), tech stack ({techstack_str}), and number of questions ({num_questions} questions)

Please share your introduction and confirm these details."""

@app.route('/api/respond', methods=['POST'])
def respond_to_question():
    """Process candidate's response and get next question or end interview"""
    try:
        data = request.json
        session_id = data.get('session_id')
        candidate_response = data.get('response', '').strip()
        
        print(f"📨 Received response for session {session_id}: {candidate_response[:50]}...")
        
        if not session_id or session_id not in interview_sessions:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        if not candidate_response:
            return jsonify({'error': 'Response is required'}), 400
        
        interview_session = interview_sessions[session_id]
        
        # Check if interview is completed
        if interview_session.is_completed:
            return jsonify({'error': 'Interview already completed'}), 400
        
        # Check if user wants to end the interview
        if should_end_interview(candidate_response):
            print(f"🏁 Ending interview session: {session_id}")
            interview_session.is_completed = True
            
            # Store the last question-answer pair if available
            if interview_session.conversation_history and len(interview_session.conversation_history) >= 2:
                last_question = interview_session.conversation_history[-2]['content'] if interview_session.conversation_history[-2]['role'] == 'assistant' else "Introduction question"
                interview_session.add_qa_pair(last_question, candidate_response)
            
            # Generate overall feedback
            feedback = generate_overall_feedback(
                interview_session.conversation_history,
                interview_session.candidate_info,
                interview_session.all_questions_answers
            )
            
            # Add final message
            farewell_message = generate_ai_response(interview_session.conversation_history, is_final_feedback=True, interview_session=interview_session)
            interview_session.add_message("assistant", farewell_message)
            
            return jsonify({
                'session_id': session_id,
                'message': farewell_message,
                'feedback': feedback,
                'question_number': interview_session.question_count,
                'total_questions_asked': interview_session.question_count,
                'status': 'completed',
                'is_final_message': True,
                'candidate_info': interview_session.candidate_info,
                'duration_minutes': round((datetime.now() - interview_session.start_time).total_seconds() / 60, 2)
            })
        
        # Extract candidate information from response
        interview_session.extract_candidate_info(candidate_response)
        
        # Store the previous question and current answer for feedback
        if interview_session.conversation_history and interview_session.conversation_history[-1]['role'] == 'assistant':
            last_question = interview_session.conversation_history[-1]['content']
            interview_session.add_qa_pair(last_question, candidate_response)
        
        # Add candidate's response to history
        interview_session.add_message("user", candidate_response)
        
        # Generate next question with contextual awareness
        ai_response = generate_ai_response(interview_session.conversation_history, interview_session=interview_session)
        interview_session.add_message("assistant", ai_response)
        interview_session.question_count += 1
        
        print(f"🤖 Next question: {ai_response}")
        
        return jsonify({
            'session_id': session_id,
            'message': ai_response,
            'question_number': interview_session.question_count,
            'status': 'in_progress',
            'candidate_info': interview_session.candidate_info,
            'has_question_limit': False
        })
    
    except Exception as e:
        print(f"❌ Error processing response: {str(e)}")
        return jsonify({'error': f'Failed to process response: {str(e)}'}), 500

@app.route('/api/end-interview/<session_id>', methods=['POST'])
def end_interview(session_id):
    """End an interview session manually"""
    if session_id not in interview_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    interview_session = interview_sessions[session_id]
    
    if not interview_session.is_completed:
        interview_session.is_completed = True
        
        # Generate overall feedback
        feedback = generate_overall_feedback(
            interview_session.conversation_history,
            interview_session.candidate_info,
            interview_session.all_questions_answers
        )
        
        # Generate farewell message
        farewell_message = "Thank you for your participation in this interview. The session has been concluded."
        
        return jsonify({
            'message': farewell_message,
            'feedback': feedback,
            'session_id': session_id,
            'status': 'ended',
            'total_questions_asked': interview_session.question_count,
            'candidate_info': interview_session.candidate_info,
            'duration_minutes': round((datetime.now() - interview_session.start_time).total_seconds() / 60, 2)
        })
    
    return jsonify({'error': 'Interview already completed'}), 400

@app.route('/api/interview-status/<session_id>', methods=['GET'])
def get_interview_status(session_id):
    """Get current status of an interview session"""
    if session_id not in interview_sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    interview_session = interview_sessions[session_id]
    
    return jsonify({
        'session_id': session_id,
        'question_number': interview_session.question_count,
        'is_completed': interview_session.is_completed,
        'start_time': interview_session.start_time.isoformat(),
        'duration_minutes': round((datetime.now() - interview_session.start_time).total_seconds() / 60, 2),
        'candidate_info': interview_session.candidate_info,
        'has_question_limit': False
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'service': 'Interview API',
        'model': WORKING_MODEL
    })

@app.route('/api/models', methods=['GET'])
def get_models():
    """Get available models"""
    try:
        models = genai.list_models()
        available_models = []
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                available_models.append(model.name)
        return jsonify({'available_models': available_models, 'current_model': WORKING_MODEL})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== HOME ROUTE ==========

@app.route("/")
def home():
    return jsonify({
        "message": "Speech and Interview Server is running!",
        "routes": {
            "POST /tts": "Convert text to speech",
            "GET /stt": "Convert microphone speech to text",
            "POST /stt/stop": "Stop ongoing speech recognition",
            "POST /api/start-interview": "Start a new interview session",
            "POST /api/respond": "Respond to interview question",
            "GET /api/interview-status/<session_id>": "Get interview status",
            "POST /api/end-interview/<session_id>": "End interview session",
            "GET /api/health": "Health check",
            "GET /api/models": "Get available models"
        }
    })

# ========== RUN SERVER ==========

if __name__ == "__main__":
    port = 5000
    print(f"🚀 Combined Speech and Interview Server running at http://127.0.0.1:{port}")
    print(f"🎯 Using Gemini model: ")
    print(f"🎤 Using AssemblyAI for speech recognition")
    print("⏰ STT Auto-stop: 5 seconds of silence")
    print("📝 Available endpoints:")
    print("   GET  /")
    print("   POST /tts")
    print("   GET  /stt")
    print("   POST /stt/stop")
    print("   POST /api/start-interview")
    print("   POST /api/respond")
    print("   GET  /api/interview-status/<session_id>")
    print("   POST /api/end-interview/<session_id>")
    print("   GET  /api/health")
    print("   GET  /api/models")
    print("\n✨ Features:")
    print("   - Text-to-Speech (TTS) with Silero")
    print("   - Speech-to-Text (STT) with AssemblyAI Streaming")
    print("   - Auto-stop after 5 seconds of silence")
    print("   - AI-powered interview sessions with Gemini")
    print("   - No question limit - interview continues until you stop")
    print("   - Automatic brief feedback at the end")
    
    app.run(host="0.0.0.0", port=port, debug=True)