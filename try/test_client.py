import requests
import json
import time

BASE_URL = "http://localhost:5000"

def speak_text(text):
    """Call TTS endpoint to speak the text"""
    try:
        tts_data = {
            'text': text,
            'speaker': 'en_10'
        }
        
        print("🔊 Playing audio...")
        tts_response = requests.post(
            f"{BASE_URL}/tts", 
            json=tts_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if tts_response.status_code == 200:
            print("✅ Audio finished playing")
            return True
        else:
            print(f"❌ TTS Error: {tts_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ TTS call failed: {e}")
        return False

def listen_for_speech():
    """Call STT endpoint to listen for user speech"""
    try:
        print("🎤 Listening for your response... (Speak now)")
        stt_response = requests.get(f"{BASE_URL}/stt")
        
        if stt_response.status_code == 200:
            stt_data = stt_response.json()
            if stt_data['status'] == 'ok':
                transcription = stt_data['transcription']
                print(f"✅ You said: {transcription}")
                return transcription
            else:
                print(f"❌ STT Error: {stt_data.get('message', 'Unknown error')}")
                return None
        else:
            print(f"❌ STT Request Error: {stt_response.text}")
            return None
            
    except Exception as e:
        print(f"❌ STT call failed: {e}")
        return None

def test_interview_flow():
    """Test the complete flexible interview flow with TTS and STT"""
    
    try:
        # Start interview
        print("🚀 Starting Flexible Interview System")
        print("💡 The interview will continue until you say 'stop', 'end', or 'finish'")
        print("📊 You will receive comprehensive feedback at the end")
        print("-" * 70)
        
        start_response = requests.post(f"{BASE_URL}/api/start-interview")
        
        if start_response.status_code != 200:
            print(f"❌ Error starting interview: {start_response.text}")
            return
        
        start_data = start_response.json()
        session_id = start_data['session_id']
        
        # Speak and show the first question
        print(f"📋 Session ID: {session_id}")
        speak_text(start_data['message'])
        print(f"🤖 AI: {start_data['message']}")
        print(f"🔢 Questions asked: {start_data['question_number']}")
        print("💡 Say 'stop', 'end', or 'finish' to end the interview and get feedback")
        print("-" * 70)
        
        # Continue with responses
        while True:
            # Listen for user's speech response
            user_input = listen_for_speech()
            
            if user_input is None:
                print("🔄 Failed to get speech input. Please try typing your response:")
                user_input = input("💬 Type your response: ")
            
            if user_input.lower() in ['quit', 'exit']:
                break
            
            response_data = {
                'session_id': session_id,
                'response': user_input
            }
            
            respond_response = requests.post(
                f"{BASE_URL}/api/respond", 
                json=response_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if respond_response.status_code != 200:
                print(f"❌ Error: {respond_response.text}")
                break
            
            response_data = respond_response.json()
            
            if response_data.get('status') == 'completed':
                # Speak and show the final message
                speak_text(response_data['message'])
                print(f"🤖 AI: {response_data['message']}")
                
                print("\n🎯" + "="*60)
                print("📊 COMPREHENSIVE FEEDBACK")
                print("="*60)
                
                # Speak a brief summary of feedback
                speak_text("Interview completed. Here is your feedback summary.")
                print(f"\n{response_data['feedback']}")
                print(f"\n📈 Interview Summary:")
                print(f"   Total questions asked: {response_data['total_questions_asked']}")
                print(f"   Duration: {response_data['duration_minutes']} minutes")
                print("🎉 Interview completed! Thank you!")
                break
            else:
                # Speak and show the next question
                speak_text(response_data['message'])
                print(f"🤖 AI: {response_data['message']}")
                print(f"🔢 Questions asked so far: {response_data['question_number']}")
                print("-" * 70)
                
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure the server is running on port 5000.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_interview_flow()