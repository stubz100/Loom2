---
updatedAt: 2025-11-26T00:54:37.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Nano Banana Model Using Uploaded Image

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

# Generate image with an image reference
url = "https://cloud.leonardo.ai/api/rest/v2/generations"

payload = {
    "model": "gemini-2.5-flash-image",
    "parameters": {
        "width": 1024,
        "height": 1024,
        "prompt": "A koala wearing a hat",
        "quantity": 1,
        "seed": 12345,
        "guidances": {
            "image_reference": [
                {
                    "image": {
                        "id": "%s" % image_id,
                        "type": "UPLOADED" 
										},
										"strength": "MID"
                }
            ]
        },
        "style_ids": [
            "111dc692-d470-4eec-b791-3475abac4c46"
        ],
        "prompt_enhance": "OFF"
    },
    "public": False
}

response = requests.post(url, json=payload, headers=headers)

print("Generate image with an image reference: %s" % response.status_code)

# Get the generated image
generation_id = response.json()['generate']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(30)

response = requests.get(url, headers=headers)

print(response.text)
```

# Import libraries

<!-- python@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated images and videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-12 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace \<YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@14-21 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via presigned URL

<!-- python@23-36 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate image with an image reference

<!-- python@38-71 -->

This part uses the uploaded file as a image reference, to generate a new image.

This request returns a generation ID for fetching a image in the next step.

# Get the generated image

<!-- python@73-80 -->

This part fetches the generated image.

Note that generated image won't be immediately available.

For simplicity, this example sets a 30 second wait time before fetching the video.

For production use cases, use the API's webhook callback feature to receive a message containing the output.