---
updatedAt: 2026-02-10T06:03:10.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Edit with Kling O3 using Video Reference

```python Python
import json
import requests
import time

api_key = "<YOUR_API_KEY>"
authorization = "Bearer %s" % api_key

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": authorization
}

# Generate video
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "kling-video-o-3",
    "public": False,
    "parameters": {
      "prompt": "A serene mountain landscape with flowing clouds",
      "duration": 3,
      "width": 1920,
      "height": 1080,
      "mode": "RESOLUTION_1080",
      "motion_has_audio": True
  	}
}

response = requests.post(url, json=payload, headers=headers)

print("Generate video: %s" % response.status_code)
print(response.text)

# Get the generated video
generation_id = response.json()['generate']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(300)

response = requests.get(url, headers=headers)

print("Get the generated video: %s" % response.status_code)
print(response.text)

# Get the video ID to be used for video reference
video_id = response.json()['generations_by_pk']['generated_images'][0]['id']

# Edit the generated video
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "kling-video-o-3",
    "public": False,
    "parameters": {
    "prompt": "Make the video an evening scene",
      "duration": 3,
      "width": 1920,
      "height": 1080,
      "mode": "RESOLUTION_1080",
      "motion_has_audio": True,
      "guidances": {
        "video_reference_base": [
          {
            "video": {
              "id": "%s" % video_id,
              "type": "GENERATED"
            }
          }
        ]
  	 }
  }
}

response = requests.post(url, json=payload, headers=headers)

print("Edit the video: %s" % response.status_code)
print(response.text)

# Get the edited video
generation_id = response.json()['generate']['generationId']

time.sleep(300)

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

response = requests.get(url, headers=headers)

print(response.text)
```

# Import libraries

<!-- python@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-12 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace \<YOUR_API_KEY> with your API key.

# Generate video

<!-- python@14-33 -->

Generated an initial video

# Get the generated video

<!-- python@35-48 -->

Get the generated video to get the video ID.

# Edit the generated video

<!-- python@50-79 -->

Make another video generation call, this time passing the video ID as video reference.

# Get the edited video

<!-- python@81-90 -->

Finally, get the edited video.