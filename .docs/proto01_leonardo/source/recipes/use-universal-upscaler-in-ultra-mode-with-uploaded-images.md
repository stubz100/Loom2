---
updatedAt: 2025-09-03T05:59:44.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Use Universal Upscaler in Ultra Mode with Uploaded Images

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

print(response.text)

print("Get a presigned URL for uploading an image: %s" % response.status_code)

# Upload image via presigned URL
fields = json.loads(response.json()['uploadInitImage']['fields'])

url = response.json()['uploadInitImage']['url']

print("Presigned URL: %s" % url)

# For getting the image later
image_id = response.json()['uploadInitImage']['id']

image_file_path = "/workspaces/workspace/4kimage.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)  # Header is not needed

print("Upload image via presigned URL: %s" % response.status_code)


# Create upscale with Universal Upscaler
url = "https://cloud.leonardo.ai/api/rest/v1/variations/universal-upscaler"

payload = {
    "ultraUpscaleStyle": "ARTISTIC",
    "creativityStrength": 5,
    "detailContrast": 5,
    "similarity": 5,
    "upscaleMultiplier": 1.5,
    "initImageId": image_id
}


response = requests.post(url, json=payload, headers=headers)

print(response.text)
print("Universal Upscaler variation: %s" % response.status_code)

# Get upscaled image via variation Id
variation_id = response.json()['universalUpscaler']['id']

url = "https://cloud.leonardo.ai/api/rest/v1/variations/%s" % variation_id

time.sleep(60)

response = requests.get(url, headers=headers)

print(response.text)

```

```node Node
const axios = require("axios");
const fs = require("fs");
const FormData = require("form-data");

const API_KEY = "<YOUR_API_KEY>";
const AUTHORIZATION = `Bearer ${API_KEY}`;

const HEADERS = {
  accept: "application/json",
  "content-type": "application/json",
  authorization: AUTHORIZATION,
};

const IMAGE_FILE_PATH = "image.jpeg";

async function uploadImageAndUpscale() {
  try {
    // Step 1: Get a presigned URL for uploading an image
    let url = "https://cloud.leonardo.ai/api/rest/v1/init-image";
    let payload = { extension: "jpg" };

    let response = await axios.post(url, payload, { headers: HEADERS });

    console.log("Presigned URL Response:", response.data);

    if (response.status !== 200) {
      throw new Error("Failed to get presigned URL");
    }

    let fields = JSON.parse(response.data.uploadInitImage.fields);
    let presignedUrl = response.data.uploadInitImage.url;
    let imageId = response.data.uploadInitImage.id;

    console.log("Presigned URL:", presignedUrl);
    console.log("Image ID:", imageId);

    // Step 2: Upload image via presigned URL
    let formData = new FormData();
    Object.keys(fields).forEach((key) => formData.append(key, fields[key]));
    formData.append("file", fs.createReadStream(IMAGE_FILE_PATH));

    response = await axios.post(presignedUrl, formData, {
      headers: { ...formData.getHeaders() },
    });

    console.log("Upload image via presigned URL:", response.status);

    if (response.status !== 204) {
      throw new Error("Failed to upload image");
    }

    // Step 3: Create upscale with Universal Upscaler
    url = "https://cloud.leonardo.ai/api/rest/v1/variations/universal-upscaler";

    payload = {
      ultraUpscaleStyle: "REALISTIC",
      creativityStrength: 5,
      detailContrast: 5,
      similarity: 5,
      upscaleMultiplier: 1.5,
      initImageId: imageId,
    };

    response = await axios.post(url, payload, { headers: HEADERS });

    console.log("Universal Upscaler Response:", response.data);

    if (response.status !== 200) {
      throw new Error("Failed to create upscale request");
    }

    let variationId = response.data.universalUpscaler.id;
    console.log("Variation ID:", variationId);

    // Step 4: Wait and get upscaled image via variation ID
    url = `https://cloud.leonardo.ai/api/rest/v1/variations/${variationId}`;

    console.log("Waiting for upscale to complete...");
    await new Promise((resolve) => setTimeout(resolve, 60000)); // Wait 60 seconds

    response = await axios.get(url, { headers: HEADERS });

    console.log("Upscaled Image Response:", response.data);

  } catch (error) {
    console.error("Error:", error.response ? error.response.data : error.message);
  }
}

uploadImageAndUpscale();
```

# Import libraries

<!-- python@1-4 -->
<!-- node@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated images and videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-12 -->
<!-- node@5-6 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@14-23 -->
<!-- node@18-35 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via presigned URL

<!-- python@25-40 -->
<!-- node@37-50 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Upscale with Universal Upscaler

<!-- python@43-59 -->
<!-- node@52-73 -->

This part uses the uploaded init image and creates an upscaled image via the Universal Upscaler.

creativityStrength refers to how 'creative' the AI will be on the original image. The higher it is, the more variation will be applied.

The response will contain a variation Id that you will need in the next step.

# Get upscaled image using variation ID

<!-- python@61-70 -->
<!-- node@75-83 -->

This part fetches the upscaled image using the variation id returned from the previous call.

Note that generated images won't be immediately available. For simplicity, this example sets a 60 second wait time before fetching the images.