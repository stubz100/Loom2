---
updatedAt: 2026-02-10T00:33:48.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Video Editing with Image Reference using Kling O1 Model

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

# ------------------------------------------------------------
# Generate video
# ------------------------------------------------------------
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "kling-video-o-1",
    "public": False,
    "parameters": {
        "prompt": "A cat and a football on a cloud",
        "duration": 5,
        "mode": "RESOLUTION_1080",
        "prompt_enhance": "OFF",
        "width": 1920,
        "height": 1080
    }
}

response = requests.post(url, json=payload, headers=headers)
print("Generate base video: %s" % response.status_code)

base_generation_id = response.json()["generate"]["generationId"]

# ------------------------------------------------------------
# Get the generated video
# ------------------------------------------------------------
url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % base_generation_id

time.sleep(180)

response = requests.get(url, headers=headers)
print("Get base generation: %s" % response.status_code)

video_image_id = response.json()["generations_by_pk"]["generated_images"][0]["id"]
base_video_mp4_url = response.json()["generations_by_pk"]["generated_images"][0]["motionMP4URL"]

print("Base Video Image ID: %s" % video_image_id)
print("Base Video MP4 URL: %s" % base_video_mp4_url)

# ------------------------------------------------------------
# Get a presigned URL for uploading an image
# ------------------------------------------------------------
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
payload = {"extension": "jpg"}

response = requests.post(url, json=payload, headers=headers)
print("Get presigned URL: %s" % response.status_code)

fields = json.loads(response.json()["uploadInitImage"]["fields"])
upload_url = response.json()["uploadInitImage"]["url"]
image_id = response.json()["uploadInitImage"]["id"]

image_file_path = "/project/workspace/your-image.jpg"
files = {"file": open(image_file_path, "rb")}

response = requests.post(upload_url, data=fields, files=files)  # Header is not needed
print("Upload image: %s" % response.status_code)

# ------------------------------------------------------------
# Edit the generated video with image reference
# ------------------------------------------------------------
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "kling-video-o-1",
    "public": False,
    "parameters": {
        "prompt": "Add @Image1 to the background",
        "duration": 5,
        "mode": "RESOLUTION_1080",
        "prompt_enhance": "OFF",
        "width": 1920,
        "height": 1080,
        "guidances": {
            "image_reference": [
                {
                    "image": {
                        "id": "%s" % image_id,
                        "type": "UPLOADED"
                    }
                }
            ],
            "video_reference_base": [
                {
                    "video": {
                        "id": "%s" % video_image_id,
                        "type": "GENERATED"
                    }
                }
            ]
        }
    }
}

response = requests.post(url, json=payload, headers=headers)
print("Edit video: %s" % response.status_code)

edit_generation_id = response.json()["generate"]["generationId"]

# ------------------------------------------------------------
# Get the edited video
# ------------------------------------------------------------
url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % edit_generation_id

time.sleep(240)

response = requests.get(url, headers=headers)
print("Get edited generation: %s" % response.status_code)

edited_video_mp4_url = response.json()["generations_by_pk"]["generated_images"][0]["motionMP4URL"]
print("Edited Video MP4 URL: %s" % edited_video_mp4_url)
```

# Import libraries

<!-- python@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-11 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace \<YOUR_API_KEY> with your API key.

# Generate Video

<!-- python@14-35 -->

Generate a video.  
The response will contain a generationId attribute that you will need in the next step.

# Get the generated video

<!-- python@37-51 -->

This part fetches the video.

Note that generated video won't be immediately available.

For simplicity, this example sets a 180 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Upload image references

<!-- python@54-70 -->

This part requests presigned URLs from Leonardo.Ai and uses those to upload image references.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This request will return fields, presigned URL, and image ID.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

When upload is successful, the request will return a 204 success message with no content.

# Edit the generated video with image reference

<!-- python@73-111 -->

This part uses the uploaded files as image references to edit the generated video.

This request returns a generation ID for fetching a video in the next step.

# Get the generated video

<!-- python@114-124 -->

This part fetches the video.

Note that generated video won't be immediately available.

For simplicity, this example sets a 240 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.