---
updatedAt: 2025-10-28T02:05:00.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Veo3.1 720p 8s Using Start and End Frame

```shell Shell
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

# Get a presigned URL for uploading the start frame image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

payload = {"extension": "jpg"}

response = requests.post(url, json=payload, headers=headers)

print("Get a presigned URL for uploading START frame image: %s" % response.status_code)

fields = json.loads(response.json()['uploadInitImage']['fields'])
url = response.json()['uploadInitImage']['url']
start_image_id = response.json()['uploadInitImage']['id']

image_file_path = "/project/workspace/start.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)
print("Upload START frame image via presigned URL: %s" % response.status_code)


# Get a presigned URL for uploading the end frame image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

payload = {"extension": "jpg"}

response = requests.post(url, json=payload, headers=headers)

print("Get a presigned URL for uploading END frame image: %s" % response.status_code)

fields = json.loads(response.json()['uploadInitImage']['fields'])
url = response.json()['uploadInitImage']['url']
end_image_id = response.json()['uploadInitImage']['id']

image_file_path = "/project/workspace/end.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)
print("Upload END frame image via presigned URL: %s" % response.status_code)


# Generate video with start and end frame images
url = "https://cloud.leonardo.ai/api/rest/v1/generations-image-to-video"

payload = {
    "prompt": "YOUR PROMPT",
    "imageId": start_image_id,
    "imageType": "UPLOADED",
    "endFrameImage": {
        "id": end_image_id,
        "type": "UPLOADED"
    },
    "resolution": "RESOLUTION_720",
    "duration": 8,
    "height": 720,
    "width": 1280,
    "model": "VEO3_1"
}

response = requests.post(url, json=payload, headers=headers)
print("Generate video with start and end frame images: %s" % response.status_code)


# Get the generated video
generation_id = response.json()['motionVideoGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(120)

response = requests.get(url, headers=headers)

print(response.text)
```

# Import libraries

<!-- shell@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- shell@5-12 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- shell@14-21 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload the start frame image via presigned URL

<!-- shell@23-31 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Get a presigned URL for uploading an image

<!-- shell@34-41 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload the end frame image via presigned URL

<!-- shell@43-51 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate video with the init image

<!-- shell@54-73 -->

This part uses the uploaded file as a starting and end frame, to generate a new video.

This request returns a generation ID for fetching a video in the next step.

# Get the generated video

<!-- shell@76-85 -->

This part fetches the Veo3.1 video.

Note that generated video won't be immediately available.

For simplicity, this example sets a 120 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.