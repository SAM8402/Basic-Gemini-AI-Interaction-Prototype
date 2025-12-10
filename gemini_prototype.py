"""
Gemini AI Integration Prototype
A voice and camera interactive AI assistant using Google's Gemini API.
"""

import os
import sys
import base64
import tempfile
from io import BytesIO

import cv2
import speech_recognition as sr
import pyttsx3
import win32com.client
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class GeminiVoiceCameraAssistant:
    """
    An AI assistant that:
    1. Listens to user's voice and converts to text
    2. Captures an image from webcam
    3. Sends both to Gemini API
    4. Speaks the response aloud
    """

    def __init__(self, api_key: str = None):
        """Initialize the assistant with necessary components."""
        # Configure Gemini API
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass it to the constructor."
            )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash-lite")

        # Initialize speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        # Initialize text-to-speech engine (Windows SAPI)
        self.speaker = win32com.client.Dispatch("SAPI.SpVoice")
        self.speaker.Rate = 0  # Normal speed (range: -10 to 10)
        self.speaker.Volume = 100

        # Initialize camera
        self.camera = None

        print("Gemini Voice & Camera Assistant initialized successfully!")

    def _configure_tts(self):
        """Configure text-to-speech settings."""
        # Set speech rate (words per minute)
        self.tts_engine.setProperty('rate', 175)
        # Set volume (0.0 to 1.0)
        self.tts_engine.setProperty('volume', 0.9)
        # Get available voices and set a natural one
        voices = self.tts_engine.getProperty('voices')
        if voices:
            # Try to use a female voice if available (usually sounds more natural)
            for voice in voices:
                if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break

    def speak(self, text: str):
        """Convert text to speech and play it."""
        print(f"\n[Assistant]: {text}")
        try:
            # Clean text for better speech
            clean_text = text.replace("*", "").replace("#", "").replace("_", "")
            clean_text = clean_text.replace("\n", ". ").replace("  ", " ").strip()

            # Use persistent SAPI speaker instance
            self.speaker.Speak(clean_text)
        except Exception as e:
            print(f"[TTS Error]: {e}")

    def listen(self) -> str:
        """
        Listen to user's voice and convert to text.
        Returns the transcribed text or None if failed.
        """
        print("\n[Listening...] Speak now!")

        with self.microphone as source:
            # Adjust for ambient noise
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

            try:
                # Listen for audio with timeout
                audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=15)
                print("[Processing speech...]")

                # Convert speech to text using Google's free API
                text = self.recognizer.recognize_google(audio)
                print(f"[You said]: {text}")
                return text

            except sr.WaitTimeoutError:
                print("[Timeout] No speech detected.")
                return None
            except sr.UnknownValueError:
                print("[Error] Could not understand the audio.")
                return None
            except sr.RequestError as e:
                print(f"[Error] Speech recognition service error: {e}")
                return None

    def capture_image(self) -> Image.Image:
        """
        Capture a single frame from the webcam.
        Returns a PIL Image or None if failed.
        """
        print("\n[Capturing image from camera...]")

        # Initialize camera if not already done
        if self.camera is None:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                print("[Error] Could not open camera.")
                return None

        # Allow camera to warm up and capture a frame
        for _ in range(5):  # Skip first few frames for camera to adjust
            ret, frame = self.camera.read()

        ret, frame = self.camera.read()

        if not ret:
            print("[Error] Could not capture image.")
            return None

        # Convert BGR (OpenCV) to RGB (PIL)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(frame_rgb)

        print("[Image captured successfully!]")
        return image

    def save_captured_image(self, image: Image.Image, filename: str = "captured_image.jpg"):
        """Save the captured image to a file for debugging."""
        filepath = os.path.join(os.path.dirname(__file__), filename)
        image.save(filepath)
        print(f"[Image saved to: {filepath}]")

    def send_to_gemini(self, text: str, image: Image.Image) -> str:
        """
        Send text and image to Gemini API and get response.
        Returns the response text or None if failed.
        """
        print("\n[Sending to Gemini AI...]")

        try:
            # Create the prompt
            prompt = f"""You are a helpful AI assistant that can see through a camera and hear the user.
The user just said: "{text}"

Please respond to their question or statement. If they asked about what you can see,
describe what's visible in the image. Give a natural, conversational response that
addresses both what they said and what you observe in the image if relevant.

Keep your response concise but helpful (2-4 sentences)."""

            # Send to Gemini with both text and image
            response = self.model.generate_content([prompt, image])

            if response and response.text:
                return response.text.strip()
            else:
                return "I'm sorry, I couldn't generate a response."

        except Exception as e:
            print(f"[Error] Gemini API error: {e}")
            return f"I encountered an error while processing: {str(e)}"

    def process_interaction(self):
        """
        Main interaction flow:
        1. Listen to user
        2. Capture image
        3. Send to Gemini
        4. Speak response
        """
        # Step 1: Listen to user's voice
        user_text = self.listen()
        if not user_text:
            self.speak("I didn't catch that. Could you please repeat?")
            return False

        # Step 2: Capture image from camera
        image = self.capture_image()
        if not image:
            self.speak("I'm having trouble with the camera. Let me try to respond without the image.")
            # Try to respond with just text if camera fails
            try:
                response = self.model.generate_content(user_text)
                self.speak(response.text if response else "I couldn't process your request.")
            except Exception as e:
                self.speak(f"Sorry, I encountered an error: {str(e)}")
            return False

        # Optional: Save the captured image for debugging
        self.save_captured_image(image)

        # Step 3: Send to Gemini
        response = self.send_to_gemini(user_text, image)

        # Step 4: Speak the response
        self.speak(response)

        return True

    def run(self):
        """Run the assistant in a continuous loop."""
        self.speak("Hello! I'm your Gemini AI assistant. I can see through your camera and hear you. Say 'exit' or 'quit' to stop.")

        while True:
            try:
                # Listen for user input
                user_text = self.listen()

                if not user_text:
                    self.speak("I didn't catch that. Please try again, or say 'exit' to quit.")
                    continue

                # Check for exit commands
                if user_text.lower() in ['exit', 'quit', 'stop', 'bye', 'goodbye']:
                    self.speak("Goodbye! Have a great day!")
                    break

                # Capture image
                image = self.capture_image()
                if not image:
                    self.speak("I'm having trouble accessing the camera.")
                    continue

                # Save image for debugging
                self.save_captured_image(image)

                # Get response from Gemini
                response = self.send_to_gemini(user_text, image)

                # Speak the response
                self.speak(response)

            except KeyboardInterrupt:
                print("\n[Interrupted by user]")
                self.speak("Goodbye!")
                break
            except Exception as e:
                print(f"[Error]: {e}")
                self.speak("I encountered an error. Let's try again.")

    def cleanup(self):
        """Release resources."""
        if self.camera is not None:
            self.camera.release()
        cv2.destroyAllWindows()
        print("\n[Resources cleaned up]")


def main():
    """Main entry point."""
    print("=" * 60)
    print("  GEMINI AI VOICE & CAMERA ASSISTANT PROTOTYPE")
    print("=" * 60)

    # Check for API key (loaded from .env file)
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("\n[ERROR] GEMINI_API_KEY not found!")
        print("Please add your API key to the .env file:")
        print("  GEMINI_API_KEY=your_api_key_here")
        print("\nGet your API key at: https://makersuite.google.com/app/apikey")
        sys.exit(1)

    print(f"\n[OK] API key loaded from .env file")

    try:
        # Initialize and run the assistant
        assistant = GeminiVoiceCameraAssistant(api_key=api_key)
        assistant.run()
    except ValueError as e:
        print(f"\n[Configuration Error]: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Error]: {e}")
        sys.exit(1)
    finally:
        if 'assistant' in locals():
            assistant.cleanup()


if __name__ == "__main__":
    main()
