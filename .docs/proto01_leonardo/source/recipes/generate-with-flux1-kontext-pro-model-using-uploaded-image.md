---
updatedAt: 2025-09-03T05:59:48.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Flux.1-Kontext [pro] Model Using Uploaded Image

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

image_id = response.json()['uploadInitImage']['id'] # For getting the image later

image_file_path = "/workspace/test.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)  # Header is not needed

print("Upload image via presigned URL: %s" % response.status_code)

# Generate image with an init image
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "prompt": "a kangaroo wearing a scarf",
    "modelId": "28aeddf8-bd19-4803-80fc-79602d1a9989",
    "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46",
    "num_images": 1,
    "width": 832,
    "height": 1248,
    "contrastRatio": 0.5,
    "contextImages": [{
        "type": "UPLOADED",
        "id": image_id
    }]
}
response = requests.post(url, json=payload, headers=headers)

print("Generate image with an init image: %s" % response.status_code)

# Get the generated image
generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(20)

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

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@13-20 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via presigned URL

<!-- python@22-34 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate image with an init image

<!-- python@36-54 -->

This part uses the uploaded file as the reference image, to generate a set of new images.

The init_image_id only allows for one image to be used at a time.

This request returns a generation ID for fetching images in the next step.

# Get the generation of Images

<!-- python@56-65 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 20 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.