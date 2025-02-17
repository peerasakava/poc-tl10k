# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-genai",
# ]
# ///
from google import genai
from google.genai import types
import pathlib

import os

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

# Use local PDF file
filepath = pathlib.Path('downloads/META_10-K.pdf')

prompt = "Extract the revenue of META from the 10-K filing. by focusing on 'Revenue by Source' and 'Revenue by Geography' on latest year only. then return in markdown table format."
response = client.models.generate_content(
  model="gemini-2.0-flash",
  contents=[
      types.Part.from_bytes(
        data=filepath.read_bytes(),
        mime_type='application/pdf',
      ),
      prompt])

print(response.text)