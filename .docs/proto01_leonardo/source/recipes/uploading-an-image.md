---
updatedAt: 2026-01-20T01:24:29.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Upload an Image and Print the Image ID

```python Python
import json
import requests

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

print("Image ID: %s" % image_id)
```

# Get a presigned URL for uploading an image

<!-- python@13-20 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and the image ID.

# Upload image via presigned URL

<!-- python@22-35 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Print the Image ID

<!-- python@37 -->

After successfully uploading the image, the image ID can then be used for Image Guidance, Upscaling, etc.