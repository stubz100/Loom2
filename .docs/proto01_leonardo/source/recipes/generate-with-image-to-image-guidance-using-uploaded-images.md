---
updatedAt: 2025-09-03T05:59:40.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Image to Image Guidance using Uploaded Images

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

image_file_path = "/workspace/test.jpg"
files = {'file': open(image_file_path, 'rb')}

response = requests.post(url, data=fields, files=files)  # Header is not needed

print("Upload image via presigned URL: %s" % response.status_code)


# Generate with Image to Image
url = "https://cloud.leonardo.ai/api/rest/v1/generations"

payload = {
    "height": 512,
    "modelId": "1e60896f-3c26-4296-8ecc-53e2afecc132", # Setting model ID to Leonardo Diffusion XL
    "prompt": "An oil painting of a cat",
    "width": 512,
    "init_image_id": image_id,  # Only allows for one Image
    "init_strength": 0.5  # Must float between 0.1 and 0.9
}

response = requests.post(url, json=payload, headers=headers)

print("Generation of Images using Image to Image %s" % response.status_code)

# Get the generation of images
generation_id = response.json()['sdGenerationJob']['generationId']

url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id

time.sleep(20)

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

async function uploadAndGenerate() {
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

    // Step 3: Generate Image to Image
    url = "https://cloud.leonardo.ai/api/rest/v1/generations";
    payload = {
      height: 512,
      modelId: "1e60896f-3c26-4296-8ecc-53e2afecc132", // Leonardo Diffusion XL
      prompt: "An oil painting of a cat",
      width: 512,
      init_image_id: imageId, // Use uploaded image ID
      init_strength: 0.5, // Must be between 0.1 and 0.9
    };

    response = await axios.post(url, payload, { headers: HEADERS });
    console.log("Generation of Images using Image to Image:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to create generation request");
    }

    let generationId = response.data.sdGenerationJob.generationId;
    console.log("Generation ID:", generationId);

    // Step 4: Wait and get the generated images
    url = `https://cloud.leonardo.ai/api/rest/v1/generations/${generationId}`;

    console.log("Waiting for image generation to complete...");
    await new Promise((resolve) => setTimeout(resolve, 20000)); // Wait 20 seconds

    response = await axios.get(url, { headers: HEADERS });

    console.log("Generated Image Response:", response.data);

  } catch (error) {
    console.error("Error:", error.response ? error.response.data : error.message);
  }
}

uploadAndGenerate();
```

# Import libraries

<!-- python@1-3 -->
<!-- node@1-3 -->

This example uses requests and time libraries.

Note: The time library is used to add wait times in between steps. This is because generated images and videos won't be immediately available. For simplicity, this example sets a fixed wait time before fetching the output.

For production use cases, use the API's webhook callback feature to receive a message containing the output.

# Set the API key in the header

<!-- python@5-12 -->
<!-- node@5 -->

This part sets the API key in the header. This header will be used in the succeeding API calls. Replace <YOUR_API_KEY> with your API key.

# Get a presigned URL for uploading an image

<!-- python@14-21 -->
<!-- node@18-35 -->

This part requests a presigned URL from Leonardo.Ai.

Notice that in the payload, we specify the file extension of the image we intend to upload.

This step will return fields, presigned URL, and image ID for use in the next step.

# Upload image via pres37-50igned URL

<!-- python@23-36 -->

This part extracts the fields, presigned URL, and image ID from the previous step.

The image file is loaded with respect to your script and image file locations.

Notice that the image ID is stored in a variable for use in the next step.

Notice that we are not passing any headers to the request. Adding authorization headers may cause authentication errors.

This request will return a 204 success message with no content.

# Generate with Image to Image

<!-- python@39-54 -->
<!-- node@52-71 -->

This part uses the uploaded file as an Image to Image Guidance, to generate a set of new images.

The init_image_id only allows for one image to be used in Image to Image Guidance.

This request returns a generation ID for fetching images in the next step.

# Get the generation of Images

<!-- python@55-65 -->
<!-- node@73-81 -->

This part fetches the images.

Note that generated images won't be immediately available. For simplicity, this example sets a 20 second wait time before fetching the images.

For production use cases, use the API's webhook callback feature to receive a message containing the output.