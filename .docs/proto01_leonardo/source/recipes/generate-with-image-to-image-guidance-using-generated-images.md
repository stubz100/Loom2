---
updatedAt: 2025-09-03T05:59:40.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Generate with Image to Image Guidance using Generated Images

```shell Shell
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
 "height": 512,
  "modelId": "1e60896f-3c26-4296-8ecc-53e2afecc132",
  "prompt": "An oil painting of a cat",
  "width": 512
}
'

# Wait for a few seconds for images to be generated

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
     
# Select an image id from generated images
     
curl --request POST \
     --url https://cloud.leonardo.ai/api/rest/v1/generations \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>' \
     --header 'content-type: application/json' \
     --data '
{
  "height": 512,
  "modelId": "1e60896f-3c26-4296-8ecc-53e2afecc132",
  "prompt": "An oil painting of an orange cat",
  "width": 512,
  "init_generation_image_id": "<YOUR_GENERATED_IMAGE_ID>",
  "init_strength": 0.5 
}
'

# Wait for a few seconds for images to be generated

curl --request GET \
     --url https://cloud.leonardo.ai/api/rest/v1/generations/<YOUR_GENERATION_ID> \
     --header 'accept: application/json' \
     --header 'authorization: Bearer <YOUR_API_KEY>'
```

```node Node
const axios = require("axios");

const API_KEY = "<YOUR_API_KEY>";
const AUTHORIZATION = `Bearer ${API_KEY}`;

const HEADERS = {
  accept: "application/json",
  "content-type": "application/json",
  authorization: AUTHORIZATION,
};

async function generateAndGuideImage() {
  try {
    // Step 1: Generate an Initial Image
    let url = "https://cloud.leonardo.ai/api/rest/v1/generations";
    let payload = {
      height: 512,
      modelId: "1e60896f-3c26-4296-8ecc-53e2afecc132", // Leonardo Diffusion XL
      prompt: "An oil painting of a cat",
      width: 512,
    };

    let response = await axios.post(url, payload, { headers: HEADERS });

    console.log("Generate initial image:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to create initial image generation request");
    }

    let generationId = response.data.sdGenerationJob.generationId;
    console.log("Initial Generation ID:", generationId);

    // Step 2: Wait before fetching the generated image
    url = `https://cloud.leonardo.ai/api/rest/v1/generations/${generationId}`;

    console.log("Waiting for initial image generation to complete...");
    await new Promise((resolve) => setTimeout(resolve, 20000)); // Wait 20 seconds

    response = await axios.get(url, { headers: HEADERS });

    console.log("Retrieve initial generated image:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to fetch initial generated image details");
    }

    let generatedImageId = response.data.generations_by_pk.generated_images[0].id;
    console.log("Selected Image ID for guidance:", generatedImageId);

    // Step 3: Generate a New Image Using the First Generated Image as a Guide
    url = "https://cloud.leonardo.ai/api/rest/v1/generations";
    payload = {
      height: 512,
      modelId: "1e60896f-3c26-4296-8ecc-53e2afecc132",
      prompt: "An oil painting of an orange cat",
      width: 512,
      init_generation_image_id: generatedImageId, // Use previously generated image
      init_strength: 0.5, // Must be between 0.1 and 0.9
    };

    response = await axios.post(url, payload, { headers: HEADERS });

    console.log("Generate guided image using previous image:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to create guided image generation request");
    }

    let guidedGenerationId = response.data.sdGenerationJob.generationId;
    console.log("Guided Image Generation ID:", guidedGenerationId);

    // Step 4: Wait and Fetch the Guided Generated Image
    url = `https://cloud.leonardo.ai/api/rest/v1/generations/${guidedGenerationId}`;

    console.log("Waiting for guided image generation to complete...");
    await new Promise((resolve) => setTimeout(resolve, 20000)); // Wait 20 seconds

    response = await axios.get(url, { headers: HEADERS });

    console.log("Retrieve guided generated image:", response.status);

    if (response.status !== 200) {
      throw new Error("Failed to fetch guided generated image details");
    }

    console.log("Guided Image Details:", response.data);

  } catch (error) {
    console.error("Error:", error.response ? error.response.data : error.message);
  }
}

// Run the function
generateAndGuideImage();
```

# Create a generation of images

<!-- shell@1-13 -->
<!-- node@14-32 -->

This command creates a generation of images using an example body.

To use this command, first replace <YOUR_API_KEY> with your API key. Then, run it in your terminal.

The response will contain a generationId attribute that you will need in the next step.

# Get the generation of images

<!-- shell@15-21 -->
<!-- node@34-49 -->

To fetch your images, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.

The response will contain an array of generated images that contain an image 'id'.

# Generate an Image using Image to Image Guidance

<!-- shell@22-37 -->
<!-- node@51-71 -->

This creates a generation of image using Image to Image guidance. Insert the previously generated image 'id' in <YOUR_GENERATED_IMAGE_ID>. The init_strength must float between 0.1 and 0.9.

Notice that the model is set to a specific model ID corresponding to the Leonardo Diffusion XL model. You can use any platform model or your own custom model by setting modelId.

The response will contain a generationId attribute that you will need in the next step.

# Get the genration of images made using Image to Image Guidance

<!-- shell@40-45 -->
<!-- node@73-87 -->

To fetch your images made using Image to Image Guidance, replace <YOUR_GENERATION_ID> in the URL with the generationId acquired from the previous step.