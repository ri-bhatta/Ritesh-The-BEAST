import json

# Read your file
try:
    with open('credentials.json', 'r') as f:
        data = json.load(f)
    
    # Convert to a single valid string (Minify)
    # This prevents GitHub from adding weird spaces
    clean_json = json.dumps(data, separators=(',', ':'))
    
    print("\n👇 COPY THE TEXT BELOW (Everything between the dashed lines) 👇\n")
    print("-" * 20)
    print(clean_json)
    print("-" * 20)
    print("\n✅ Paste this EXACT text into GitHub Secrets. It is now bulletproof.")

except Exception as e:
    print(f"❌ Error reading file: {e}")
