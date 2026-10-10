---
updatedAt: 2025-09-03T05:59:45.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate Images with Canvas Inpainting

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

# STEPS TO GET PRESIGNED URL - Request presigned URL for both init image and mask image.
url = "https://cloud.leonardo.ai/api/rest/v1/canvas-init-image"

payload = {
    "initExtension": "jpeg",
    "maskExtension": "jpeg"
}

response = requests.post(url, json=payload, headers=headers)

init_id = response.json()['uploadCanvasInitImage']['initImageId']
mask_id = response.json()['uploadCanvasInitImage']['masksImageId']

print("Get canvas init image URL %s" % response.status_code)
print("initImageId %s" % init_id)
print("maskImageId %s" % mask_id)

# INIT IMAGE UPLOAD - Upload init image via presigned URL
init_fields = json.loads(
    response.json()['uploadCanvasInitImage']['initFields'])
init_url = response.json()['uploadCanvasInitImage']['initUrl']
init_key = response.json()['uploadCanvasInitImage']['initKey']

# For getting the init image later
init_image_id = response.json()['uploadCanvasInitImage']['initImageId']

init_image_file_path = "/workspace/canvasinit.jpg" #replace this with an image file path stored with respect to your script
init_files = {'file': open(init_image_file_path, 'rb')}

init_response = requests.post(init_url, data=init_fields,
                              files=init_files)  # Header is not needed


print("Upload init image via presigned URL: %s" % init_response.status_code)

print("Link to init image https://cdn.leonardo.ai/" + init_key)

# MASK IMAGE UPLOAD - Upload masks image via presigned URL
masks_fields = json.loads(
    response.json()['uploadCanvasInitImage']['masksFields'])
masks_url = response.json()['uploadCanvasInitImage']['masksUrl']
masks_key = response.json()['uploadCanvasInitImage']['masksKey']

# For getting the image later
masks_image_id = response.json()['uploadCanvasInitImage']['masksImageId']

masks_image_file_path = "/workspace/canvasmask.jpg"
masks_files = {'file': open(masks_image_file_path, 'rb')}

mask_response = requests.post(masks_url, data=masks_fields,
                              files=masks_files)  # Header is not needed

print("Upload masks image via presigned URL: %s" % mask_response.status_code)
print("Link to masks image https://cdn.leonardo.ai/" + masks_key)

# GENERATE IMAGE VIA CANVAS INPAINTING
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "prompt": "a bright sun",
    "canvasRequest": True,
    "num_images": 4,
    "init_strength": 0.13, # Inpaint strength 0.87
    "canvasRequestType": "INPAINT",
    "guidance_scale": 7,
    "modelId": "1e60896f-3c26-4296-8ecc-53e2afecc132",  # Leonardo Diffusion XL
    "canvasInitId": init_image_id,
    "canvasMaskId": masks_image_id
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)
print("Generate an image: %s" % response.status_code)

# GET THE GENERATION
generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(45)

response = requests.get(url, headers=headers)

print(response.text)
print("Get the generation of images: %s" % response.status_code)

```

# Import Libraries and set headers

<!-- python@1-12 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated images and videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

Replace <YOUR_API_KEY> with your API key.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Get presigned URL for init and mask image

<!-- python@14-29 -->

This part will return two presigned URLs and respective fields. One for your init image, and the other for the mask image.

Take note of the image extension. Allowed extensions are jpg, jpeg, webp, png.

# Upload Init Image via presigned URL

<!-- python@31-49 -->

This part will upload an init image to the presigned URL returned from the previous step. This is your base image. 

The file extension of the image should match the specified dimension from the previous step. 

The image file is loaded with respect to your script and image file locations. The image must be read in binary.

Do no pass any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Upload Mask Image via Presigned URL

<!-- python@51-68 -->

This part will upload the mask image to the presigned URL returned from the second step

Make sure to upload the mask with the same image dimensions as the init image.  The mask must be a white area on a black background. 

This request will return a 204 success message with no content.

# Generate an Image using Canvas Inpaint

<!-- python@70-88 -->

This part generates an image using the Canvas Inpaint parameters with the init image and mask image ids. 

Note that init strength refers to Inpaint Strength on the Web App, and will be subtracted from 1 to match the correct strength 

Inpainting will only apply to the area where the Mask covers over the Init image. 

This request returns a generation ID for fetching images in the next step.

# Get the generation of Images

<!-- python@90-100 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 45 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.