from agentic_news import NewsAgent
from dotenv import load_dotenv

def main():
    load_dotenv()
    
    agent = NewsAgent()
    result = agent.run(
        "Get today's news preferences, fetch and summarize articles, "
        "create a news script, convert to speech, and upload the audio."
    )
    print("\nFinal Audio URL:", result)

if __name__ == "__main__":
    main()
