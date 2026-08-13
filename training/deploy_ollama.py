import os
import sys
import subprocess
import requests
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gguf", required=True, help="Path to the NoveLaw GGUF file")
    args = parser.parse_args()
    
    gguf_path = Path(args.gguf).resolve()
    if not gguf_path.exists():
        print(f"Error: GGUF file not found at {gguf_path}")
        sys.exit(1)

    print("Checking for Ollama...")
    try:
        subprocess.run(["ollama", "--version"], check=True, capture_output=True)
    except FileNotFoundError:
        print("Ollama is not installed or not in PATH.")
        print("Please download and install it from https://ollama.com/download")
        sys.exit(1)

    print("Checking Ollama service...")
    try:
        requests.get("http://localhost:11434/api/tags")
    except requests.ConnectionError:
        print("Ollama service is not running. Please start Ollama first.")
        sys.exit(1)
        
    modelfile_path = Path(r"d:\Nova Legal\training\Modelfile")
    if not modelfile_path.exists():
        print(f"Error: Modelfile not found at {modelfile_path}")
        sys.exit(1)

    # We need to temporarily update Modelfile with correct absolute path if needed,
    # but Modelfile assumes it's in the same dir. We'll pass the model name.
    
    print("Creating model in Ollama (this might take a minute)...")
    try:
        subprocess.run(["ollama", "create", "novelaw", "-f", str(modelfile_path)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to create model: {e}")
        sys.exit(1)

    print("\nVerifying model with a test query...")
    try:
        res = requests.post("http://localhost:11434/api/generate", json={
            "model": "novelaw",
            "prompt": "What is the capital of India?",
            "stream": False
        })
        print(f"Response: {res.json().get('response', '').strip()}")
        print("\nSuccess! NoveLaw has been deployed.")
        print("You can now run it using: ollama run novelaw")
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    main()
