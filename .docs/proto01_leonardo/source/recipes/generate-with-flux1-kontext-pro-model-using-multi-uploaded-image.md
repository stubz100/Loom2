---
updatedAt: 2025-09-04T00:49:59.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Flux.1-Kontext [pro] Model Using Multi Uploaded Images

```python Python
import json
import requests
import time

api_key = "API_KEY"
authorization = "Bearer %s" % api_key

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": authorization
}

# ---------- Upload 1 ----------
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
payload = {"extension": "jpg"}
response = requests.post(url, json=payload, headers=headers)
print("Get a presigned URL for uploading image 1:", response.status_code)

fields = json.loads(response.json()['uploadInitImage']['fields'])
upload_url_1 = response.json()['uploadInitImage']['url']
image_id_1 = response.json()['uploadInitImage']['id']  # keep this separately for image 1

image_file_path = "test01.jpg"
with open(image_file_path, 'rb') as f:
    files = {'file': f}
    # Uploading to the presigned URL does not require headers
    up = requests.post(upload_url_1, data=fields, files=files)
    print("Upload image 1 via presigned URL:", up.status_code)

# ---------- Upload 2 ----------
url = "https://cloud.leonardo.ai/api/rest/v1/init-image"
payload = {"extension": "jpg"}
response = requests.post(url, json=payload, headers=headers)
print("Get a presigned URL for uploading image 2:", response.status_code)

fields = json.loads(response.json()['uploadInitImage']['fields'])
upload_url_2 = response.json()['uploadInitImage']['url']
image_id_2 = response.json()['uploadInitImage']['id']  # keep this separately for image 2

image_file_path = "test02.jpg"
with open(image_file_path, 'rb') as f:
    files = {'file': f}
    # Uploading to the presigned URL does not require headers
    up = requests.post(upload_url_2, data=fields, files=files)
    print("Upload image 2 via presigned URL:", up.status_code)

# ---------- Generation ----------
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "prompt": "a man on a sofa with an orange can",  
    "modelId": "28aeddf8-bd19-4803-80fc-79602d1a9989",
    "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46",
    "num_images": 1,
    "width": 832,
    "height": 1248,  
    "contrastRatio": 0.5,
    "contextImages": [
        {"type": "UPLOADED", "id": image_id_1},
        {"type": "UPLOADED", "id": image_id_2}
    ]
}

response = requests.post(url, json=payload, headers=headers)
print("Generate image with init images:", response.status_code)

data = response.json()
generation_id = data["sdGenerationJob"]["generationId"]

# ---------- Poll the generation result (simple wait then fetch) ----------
url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id
time.sleep(40)
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

<!-- python@13-22 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload the first image via presigned URL

<!-- python@24-29 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Get a presigned URL for uploading an image

<!-- python@31-39 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload the second image via presigned URL

<!-- python@41-46 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate image with the init image

<!-- python@48-69 -->

This part uses the uploaded file as the reference image, to generate a set of new images.

This request returns a generation ID for fetching images in the next step.

# Get the generation of Images

<!-- python@71-75 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 20 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.