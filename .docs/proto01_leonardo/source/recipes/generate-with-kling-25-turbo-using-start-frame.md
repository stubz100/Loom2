---
updatedAt: 2025-10-28T02:04:50.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Kling 2.5 Turbo Using Start Frame

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

# Get a presigned URL for uploading an image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

payload = {"extension": "jpg"}

response = requests.post(url, json=payload, headers=headers)

print("Get a presigned URL for uploading an image: %s" % response.status_code)

# Upload image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])

url = response.json()['uploadInitImage']['url']

# For getting the image later
image_id = response.json()['uploadInitImage']['id']

image_file_path = "/project/workspace/test.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)  # Header is not needed

print("Upload image via presigned URL: %s" % response.status_code)

# Generate video with an init image
url = "https://cloud.leonardo.ai/api/rest/v1/generations-image-to-video"

payload = {
    "prompt":"A lone car drives down an empty desert highway at golden hour, the sun low on the horizon, casting long shadows and warm tones. Dust kicks up behind the vehicle as it gradually disappears into the glowing distance. Epic wide-angle cinematic shot with a shallow depth of field, rich color grading, and a sense of quiet freedom. Filmic look, 4K resolution, anamorphic lens flare, slow panning camera motion.",
    "imageId" : image_id,
    "imageType": "UPLOADED",
    "duration": 5,
    "height": 1080,
    "width": 1920,
    "resolution": "RESOLUTION_1080",
    "model": "KLING2_5"

}

response = requests.post(url, json=payload, headers=headers)

print("Generate video with an init image: %s" % response.status_code)

# Get the generated video
generation_id = response.json()['motionVideoGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(600)

response = requests.get(url, headers=headers)

print(response.text)

```

# Import libraries

<!-- python@1-4 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-13 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@14-22 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via presigned URL

<!-- python@23-37 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate video with an init image

<!-- python@38-55 -->

This part uses the uploaded file as a starting frame, to generate a new video.

The ImageId only allows for one image to be used as a starting frame.

This request returns a generation ID for fetching a video in the next step.

# Get the generated video

<!-- python@57-66 -->

This part fetches the Kling 2.5 Turbo video.

Note that generated video won't be immediately available.

For simplicity, this example sets a 120 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.