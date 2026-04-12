from sentence_transformers import SentenceTransformer
import os

# Optional: Disable that annoying PostHog telemetry here too
os.environ["ANONYMIZED_TELEMETRY"] = "False"

def main():
    print("⏳ Connecting to Hugging Face to download 'all-MiniLM-L6-v2'...")
    try:
        # This line triggers the download
        model = SentenceTransformer("all-MiniLM-L6-v2")
        print("✅ Success! The model is now cached on your computer.")
        print("🚀 You can now close this and run your main FastAPI server.")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("\n💡 TIP: If you're at BMIT, try using your mobile data hotspot.")

if __name__ == "__main__":
    main()