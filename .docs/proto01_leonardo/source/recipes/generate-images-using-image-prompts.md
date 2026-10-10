---
updatedAt: 2025-09-03T05:59:39.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images Using Image Prompts

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

print(response.status_code)

# Upload image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])

url = response.json()['uploadInitImage']['url']

image_id = response.json()['uploadInitImage']['id']  # For getting the image later

image_file_path = "/workspace/test.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files) # Header is not needed

print(response.status_code)

# Generate with an image prompt
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "height": 512,
    "modelId": "6bef9f1b-29cb-40c7-b9df-32b51c1f67d3", # Setting model ID to Leonardo Creative
    "prompt": "An oil painting of a cat",
    "width": 512,
    "imagePrompts": [image_id] # Accepts an array of image IDs
}

response = requests.post(url, json=payload, headers=headers)

print(response.status_code)

# Get the generation of images
generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(20)

response = requests.get(url, headers=headers)

print(response.text)
```

# Import libraries

<!-- python@1-3 -->

This example uses json, requests, and time libraries.

# Set the API key in the header

<!-- python@5-12 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@14-21 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via presigned URL

<!-- python@23-35 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate with an image prompt

<!-- python@37-50 -->

This part makes a simple request to create a generation of images with the uploaded image as image prompt.

Notice that the imagePrompts attribute accepts an array of image IDs.

This request returns a generation ID for fetching images in the next step.

# Get the generation of images

<!-- python@52-61 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 20 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.