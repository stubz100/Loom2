---
updatedAt: 2025-09-03T05:59:45.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Image Guidance using multiple ControlNets

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

# STEPS TO UPLOADING IMAGE - Get a presigned URL for uploading an image
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"

payload = {"extension": "jpg"}

response = requests.post(url, json=payload, headers=headers)

print("Get a presigned URL for uploading an image: %s" % response.status_code)

# Upload image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])

url = response.json()['uploadInitImage']['url']

# For getting the image later
uploaded_image_id = response.json()['uploadInitImage']['id']

image_file_path = "/workspace/test.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)  # Header is not needed

print("Upload image via presigned URL: %s" % response.status_code)

#STEPS TO GENERATE AN IMAGE-  Create a generation
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "height": 768,
    "modelId": "aa77f04e-3eec-4034-9c07-d0f619684628",  # Leonardo Kino XL
    "prompt": "red light streak gradient",
    "width": 1024,
    "num_images": 1,
    "alchemy": True
}

response = requests.post(url, json=payload, headers=headers)

print("Generate an image: %s" % response.status_code)

# Get the generation of images
generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(30)

response = requests.get(url, headers=headers)

print("Get the generation of images: %s" % response.status_code)

generation_image_id = response.json()['generations_by_pk']['generated_images'][0]['id']

# COMBINE BOTH UPLOADED AND GENERATED IMAGES - Generate with multiple Control Nets
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
  "height": 576,
  "modelId": "aa77f04e-3eec-4034-9c07-d0f619684628",# Leonardo Kino XL
  "prompt": "A mesmerizing lady with cascading strands of blonde hair gazes through a misty train window",
  "presetStyle":"CINEMATIC",
  "width": 1024,
  "photoReal": true,
  "photoRealVersion":"v2",
  "alchemy":true,
  "controlnets": [
        {
            "initImageId": uploaded_image_id,
            "initImageType": "UPLOADED",
            "preprocessorId": 133, # Character Reference Id
            "strengthType": "Mid",
        },
        {
            "initImageId": generated_image_id,
            "initImageType": "GENERATED",
            "preprocessorId": 67, # Style Reference Id
            "strengthType": "High",
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)

print("Generation of Images using Multiple ControlNets %s" % response.status_code)

# Get the generation of images
final_generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % final_generation_id

time.sleep(60)

response = requests.get(url, headers=headers)

print(response.text)


```

# Import Libraries and set headers

<!-- python@1-12 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated images and videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

Replace <YOUR_API_KEY> with your API key.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Upload an Image using presigned URL

<!-- python@14-36 -->

This part will upload an image to Leonardo.Ai via a presigned URL.

Notice that in the payload, we specify the file extension of the image we intend to upload.

The image file is loaded with respect to your script and image file locations. The image must be read in binary.

Do no pass any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Create a generation

<!-- python@38-65 -->

This part generates an image with an example API body that can be used as a Style reference in the next step. 

The image Id is then retrieved and gets stored in generation_image_id to be used in the next step.

# Generate with multiple Control Nets as Image Guidance

<!-- python@67-97 -->

This part uses the uploaded file and generated image with multiple ControlNets, to generate a set of new images. View our guides for more preprocessor IDs. 

Ensure initImageType refers to UPLOADED or GENERATED.

This request returns a generation ID for fetching images in the next step.

# Get the generation of Images

<!-- python@99-108 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 60 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.